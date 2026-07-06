"""Groq istemcisi — OpenAI SDK ile uyumlu REST API.

Ücretsiz modeller: llama-3.3-70b-versatile, llama-3.1-8b-instant,
mixtral-8x7b-32768.
"""

from __future__ import annotations

from typing import Optional

from .base import LLMClient, LLMMessage, LLMResponse


class GroqClient(LLMClient):
    provider = "groq"
    default_model = "llama-3.3-70b-versatile"
    base_url = "https://api.groq.com/openai/v1/chat/completions"

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
                    text=f"[Groq error {r.status_code}]: {r.text[:200]}",
                    model=self.model,
                )
            body = r.json()

        text = body.get("choices", [{}])[0].get("message", {}).get("content", "")
        usage = body.get("usage", {})
        return LLMResponse(text=text, model=self.model, usage=usage, raw=body)

    async def stream(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ):
        import httpx

        payload = {
            "model": self.model,
            "messages": [m.to_dict() for m in messages],
            "temperature": temperature,
            "stream": True,
        }
        if max_tokens:
            payload["max_tokens"] = max_tokens
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=120.0) as client:
            async with client.stream("POST", self.base_url, json=payload, headers=headers) as r:
                async for line in r.aiter_lines():
                    if line.startswith("data: "):
                        data = line[6:]
                        if data.strip() == "[DONE]":
                            break
                        import json

                        try:
                            chunk = json.loads(data)
                            delta = chunk["choices"][0].get("delta", {}).get("content")
                            if delta:
                                yield delta
                        except Exception:
                            continue
