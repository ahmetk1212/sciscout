"""LLM istemcileri için ortak arayüz.

Tüm sağlayıcılar (Gemini, Groq, OpenRouter) LLMClient'ten türetilir ve:
  - chat(messages) -> str          (basit metin cevap)
  - stream(messages) -> AsyncIter  (token-token akış)
  - count_tokens(text) -> int      (yaklaşık token sayısı)
sağlar.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import AsyncIterator, Literal, Optional


Role = Literal["system", "user", "assistant"]


@dataclass
class LLMMessage:
    role: Role
    content: str
    name: Optional[str] = None

    def to_dict(self) -> dict:
        d = {"role": self.role, "content": self.content}
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class LLMResponse:
    text: str
    model: str
    usage: dict = field(default_factory=dict)
    raw: Optional[object] = None


class LLMClient(ABC):
    """Tüm LLM sağlayıcıları için ortak arayüz."""

    provider: str = "base"
    default_model: str = ""

    def __init__(self, api_key: str, model: Optional[str] = None):
        if not api_key:
            raise ValueError(f"{self.provider} API anahtarı boş")
        self.api_key = api_key
        self.model = model or self.default_model

    @abstractmethod
    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> AsyncIterator[str]:
        """Varsayılan: stream yok, sadece nihai cevabı verir."""
        resp = await self.chat(messages, temperature, max_tokens)
        yield resp.text

    def count_tokens(self, text: str) -> int:
        """Yaklaşık token sayısı (her sağlayıcı override edebilir)."""
        return int(len(text) / 4)
