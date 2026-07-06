"""OpenRouter istemcisi — tek API ile 100+ model.
Ücretsiz modeller: meta-llama/llama-3.3-70b-instruct:free,
mistralai/mistral-7b-instruct:free, vb.
"""

from __future__ import annotations

from typing import Optional

from .base import LLMClient, LLMMessage, LLMResponse


class OpenRouterClient(LLMClient):
    provider = "openrouter"
    default_model = "meta-llama/llama-3.3-70b-instruct:free"
    base_url = "https://openrouter.ai/api/v1/chat/completions"

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
            "HTTP-Referer": "https://github.com/local/sciscout",
            "X-Title": "SciScout",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            r = await client.post(self.base_url, json=payload, headers=headers)
            if r.status_code != 200:
                return LLMResponse(
                    text=f"[OpenRouter error {r.status_code}]: {r.text[:200]}",
                    model=self.model,
                )
            body = r.json()
        text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = body.get("usage", {})
        return LLMResponse(text=text, model=self.model, usage=usage, raw=body)
