"""LLM Yönlendirici (Router). Çok sağlayıcılı, hata düşüşü (fallback) yapar.

Akış (varsayılan: Groq ana, çünkü Gemini ücretsiz kotası çabuk bitiyor):
  1. Primary (Groq Llama 3.3 70B) — ana akıl yürütme, sentez
  2. Fast (Cerebras Gemma 4 31B) — çeviri/kısa sorgular
  3. Fallback (Gemini 2.5-flash) — kota dolumunda yedek
  4. OpenRouter — son çare (eğer varsa)

Neden: Gemini ücretsiz kotası günlük düşük. Groq günlük çok yüksek ücretsiz kota.
"""

from __future__ import annotations

import logging
import re
from typing import AsyncIterator, Optional

from ..config import get_settings
from .base import LLMClient, LLMMessage, LLMResponse
from .gemini import GeminiClient
from .groq_client import GroqClient
from .openrouter import OpenRouterClient
from .cerebras import CerebrasClient

logger = logging.getLogger("sciscout.llm.router")


_ERROR_PATTERNS = [
    re.compile(r"\[(?:Gemini|Groq|OpenRouter|Cerebras)\s*error", re.I),
    re.compile(r"429 You exceeded", re.I),
    re.compile(r"quota exceeded", re.I),
    re.compile(r"^Invalid operation", re.I),
    re.compile(r"RESOURCE_EXHAUSTED", re.I),
    re.compile(r"rate.?limit", re.I),
]


def _is_error_text(text: str) -> bool:
    if not text:
        return True
    for p in _ERROR_PATTERNS:
        if p.search(text):
            return True
    return False


class LLMRouter:
    """Çok sağlayıcılı, akıllı düşüşlü (fallback) yönlendirici.

    Kullanım:
        router = LLMRouter()
        resp = await router.chat(messages)
        async for token in router.stream(messages): ...
    """

    def __init__(self):
        s = get_settings()

        # Tüm sağlayıcıları oluştur (varsa)
        self.gemini: Optional[LLMClient] = None
        self.groq: Optional[LLMClient] = None
        self.cerebras: Optional[LLMClient] = None
        self.openrouter: Optional[LLMClient] = None

        if s.gemini_api_key:
            # Gemini modelini SCI_MODEL_PRIMARY içindeki "gemini:xxx" veya fallback'ten al
            gmodel = "gemini-2.5-flash"
            for spec in (s.model_primary, s.model_fallback):
                if spec.startswith("gemini:"):
                    gmodel = spec.split(":", 1)[1]
                    break
            self.gemini = GeminiClient(s.gemini_api_key, gmodel)
        if s.groq_api_key:
            # Groq modelini SCI_MODEL_PRIMARY içindeki "groq:xxx" veya fast
            gmodel = "llama-3.3-70b-versatile"
            for spec in (s.model_primary, s.model_fast):
                if spec.startswith("groq:"):
                    gmodel = spec.split(":", 1)[1]
                    break
            self.groq = GroqClient(s.groq_api_key, gmodel)
        if s.cerebras_api_key:
            # Cerebras modelini "cerebras:xxx" den al
            m = "gemma-4-31b"
            for spec in (s.model_fast, s.model_primary, s.model_fallback):
                if spec.startswith("cerebras:"):
                    m = spec.split(":", 1)[1]
                    break
            self.cerebras = CerebrasClient(s.cerebras_api_key, m)
        if s.openrouter_api_key:
            m = (
                s.model_fallback.split(":", 1)[1]
                if ":" in s.model_fallback
                else "meta-llama/llama-3.3-70b-instruct:free"
            )
            self.openrouter = OpenRouterClient(s.openrouter_api_key, m)

        # birincil: SCI_MODEL_PRIMARY değerine göre seç
        self.primary = self._match_provider(s.model_primary)
        # Fast: mümkünse Cerebras, değilse Groq
        self.fast = self.cerebras or self.groq

        # Fallback zinciri: primary -> others
        self._ordered: list[LLMClient] = []
        if self.primary:
            self._ordered.append(self.primary)
        for c in (self.groq, self.cerebras, self.gemini, self.openrouter):
            if c and c not in self._ordered:
                self._ordered.append(c)

        self._fast_prefixes = (
            "search",
            "find",
            "lookup",
            "summarize",
            "short",
            "translate",
            "ara",
            "cevir",
            "çevir",
        )

    def _match_provider(self, spec: str) -> Optional[LLMClient]:
        """spec string'ine göre sağlayıcı seç."""
        if not spec:
            return None
        spec_low = spec.lower()
        if spec_low.startswith("groq:") or "llama" in spec_low and "gemini" not in spec_low:
            return self.groq
        if spec_low.startswith("cerebras:") or "gemma" in spec_low:
            return self.cerebras
        if spec_low.startswith("gemini:"):
            return self.gemini
        if spec_low.startswith("openrouter:"):
            return self.openrouter
        # Varsayılan: Groq (çünkü Gemini kotası çabuk bitiyor)
        return self.groq or self.cerebras or self.gemini or self.openrouter

    def has_any(self) -> bool:
        return bool(self._ordered)

    def _build_chain(self, query: str, use_primary: bool = True) -> list[LLMClient]:
        if not self._ordered:
            return []
        order = list(self._ordered)
        # Hızlı tercih — fast varsayılan sıralamaya gelmeden önce fast'ı öne al
        if use_primary and query and self.fast and self.fast is not self.primary:
            q = query.lower().strip()
            if any(q.startswith(p) for p in self._fast_prefixes):
                order = [self.fast] + [c for c in order if c is not self.fast]
        if (not use_primary) and self.fast:
            order = [self.fast] + [c for c in order if c is not self.fast]
        # Dedup (identity)
        seen, result = set(), []
        for c in order:
            if id(c) not in seen:
                seen.add(id(c))
                result.append(c)
        return result

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
        use_primary: bool = True,
    ) -> LLMResponse:
        query = next((m.content for m in messages if m.role == "user"), "")
        chain = self._build_chain(query, use_primary=use_primary)
        if not chain:
            raise RuntimeError("Hiçbir LLM API anahtarı yapılandırılmamış.")

        last_err = ""
        for i, client in enumerate(chain):
            try:
                resp = await client.chat(messages, temperature, max_tokens)
                if _is_error_text(resp.text):
                    last_err = resp.text[:200]
                    logger.warning(
                        f"[{client.provider}/{client.model}] soft hata → "
                        f"{'sonraki' if i < len(chain) - 1 else 'başka sağlayıcı yok'}"
                    )
                    continue
                return resp
            except Exception as e:
                last_err = str(e)[:200]
                logger.warning(f"[{client.provider}/{client.model}] exception: {last_err}")
                continue
        return LLMResponse(
            text=f"[Tüm sağlayıcılar başarısız. Son hata: {last_err}]",
            model="error",
        )

    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        query = next((m.content for m in messages if m.role == "user"), "")
        chain = self._build_chain(query, use_primary=True)

        last_err = ""
        for i, client in enumerate(chain):
            try:
                saw_token = False
                async for token in client.stream(messages, temperature, max_tokens):
                    saw_token = True
                    yield token
                if saw_token:
                    return
                logger.warning(f"[{client.provider}] hiç token dönmedi")
            except Exception as e:
                last_err = str(e)[:200]
                logger.warning(f"Stream hatası ({client.provider}): {last_err}")
                continue
        yield f"[Tüm sağlayıcılar stream için başarısız. Son hata: {last_err}]"
