"""Google Gemini istemcisi (google-generativeai).

Ücretsiz katman: gemini-2.0-flash, gemini-2.5-flash, gemini-1.5-pro.
"""

from __future__ import annotations

from typing import Optional

from .base import LLMClient, LLMMessage, LLMResponse


class GeminiClient(LLMClient):
    provider = "gemini"
    default_model = "gemini-2.0-flash"

    def __init__(self, api_key: str, model: Optional[str] = None):
        super().__init__(api_key, model)
        import google.generativeai as genai

        self._genai = genai
        genai.configure(api_key=api_key)
        self._model = genai.GenerativeModel(self.model)

    async def chat(
        self,
        messages: list[LLMMessage],
        temperature: float = 0.3,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        # Gemini SDK sync; asyncio thread executor kullanırız.
        import asyncio

        loop = asyncio.get_event_loop()
        # 1 system + diğer[sıralı] şeklinde Gemini 'contents' formatına çevr
        system = next((m for m in messages if m.role == "system"), None)
        contents = []
        for m in messages:
            if m.role == "system":
                continue
            role = "user" if m.role == "user" else "model"
            contents.append({"role": role, "parts": [m.content]})

        gen_config = {"temperature": temperature}
        if max_tokens:
            gen_config["max_output_tokens"] = max_tokens

        # System prompt'u tools'a geçmek için ilk mesajın başına ekliyoruz
        if system:
            if contents and contents[0]["role"] == "user":
                contents[0]["parts"][0] = f"{system.content}\n\n---\n\n{contents[0]['parts'][0]}"
            else:
                contents.insert(0, {"role": "user", "parts": [system.content]})

        def _run() -> str:
            try:
                resp = self._model.generate_content(contents, generation_config=gen_config)
                return resp.text or ""
            except Exception as e:
                return f"[Gemini error: {e}]"

        text = await loop.run_in_executor(None, _run)
        return LLMResponse(text=text, model=self.model)
