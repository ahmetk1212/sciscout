"""Cerebras API istemcisi — OpenAI uyumlu, sadece `gemma-4-31b` kullaniriz.

Modeller: gpt-oss-120b, gemma-4-31b, zai-glm-4.7
gemma-4-31b standard 'content' field döndürür (diğerleri 'reasoning').
"""

from __future__ import annotations

from typing import Optional

from .base import LLMClient, LLMMessage, LLMResponse


class CerebrasClient(LLMClient):
    provider = "cerebras"
    default_model = "gemma-4-31b"
    base_url = "https://api.cerebras.ai/v1/chat/completions"

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        import httpx

        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(self.base_url, json=payload, headers=headers)
            if r.status_code != 200:
                return LLMResponse(
                    text=f"[Cerebras error {r.status_code}]: {r.text[:200]}",
                    model=self.model,
                )
            body = r.json()

        msg = body.get("choices", [{}])[0].get("message", {})
        # Önce content dene (gemma-4-31b), sonra reasoning (gpt-oss/glm)
        text = msg.get("content") or msg.get("reasoning") or ""
        usage = body.get("usage", {})
        return LLMResponse(text=text, model=self.model, usage=usage, raw=body)
