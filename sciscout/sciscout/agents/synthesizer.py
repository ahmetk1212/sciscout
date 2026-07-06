"""Sentez agent'ı — adım 3.

Görev: Özetleri alır, kullanıcı sorusunu yanıtlar. Bilimsel/mühendislik
tarzı, kaynak referanslarıyla, ITALIN Türkçe (sorgu Türkçe ise).
Son adım — kullanıcıya gösterilen nihai cevaptır.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..llm.base import LLMMessage

if TYPE_CHECKING:
    from .graph import ResearchState

logger = logging.getLogger("sciscout.agents.synthesizer")


SYSTEM_PROMPT = """You are SciScout, a senior scientific and engineering research assistant.

You synthesize findings from multiple sources into a comprehensive response.

Style:
- Match the user's language (Turkish if Turkish question, English otherwise).
- Use clear, structured scientific prose.
- For science questions, include:
  - Brief background (1-2 sentences)
  - Latest findings (numbered list with [^n] citations)
  - Open questions / next steps
- For engineering problems, include:
  - Problem framing
  - Possible approaches (with pros/cons)
  - Practical recommendations (recommended approach + alternatives)
- Always cite sources with [^n] footnote markers; list them at the end.
- Be thorough but not flowery. Use technical precision.
- NEVER invent paper citations. Only cite from the provided summaries.
- If sources contradict, mention both and note uncertainty.
- If no good sources were found, say so honestly and suggest queries."""


async def synthesizer_agent(state: "ResearchState") -> "ResearchState":
    """Özetlerden nihai sentez cevabı üret."""
    question = state["question"]
    summaries = state.get("summaries", [])
    router = state.get("router")

    if not summaries:
        state["answer"] = (
            "Üzgünüm, bu soru için yeterli güvenilir kaynak bulunamadı. "
            "Lütfen sorguyu daha spesifik hale getirin veya farklı anahtar "
            "kelimelerle tekrar deneyin."
        )
        state["citations"] = []
        return state

    # Kaynak listesini üret
    citations_block = "\n".join(
        f"[^{i}] {s['title']} — {s['source']}\n    {s['url']}" for i, s in enumerate(summaries, 1)
    )

    # Özetlerin text hali
    summaries_block = "\n\n---\n\n".join(
        f"### Source {i}: {s['title']}\nURL: {s['url']}\nSource type: {s['source']}\n\n{s['summary']}"
        for i, s in enumerate(summaries, 1)
    )

    user_msg = (
        f"USER QUESTION:\n{question}\n\n"
        f"SUMMARIES FROM {len(summaries)} SOURCES:\n{summaries_block}\n\n"
        f"Write a rigorous scientific synthesis. Include [^n] citations. "
        f"At the end, list '## Kaynaklar' (or '## Sources' if English) with full URLs."
    )

    if not router:
        state["answer"] = summaries_block
        state["citations"] = [{"n": i, **s} for i, s in enumerate(summaries, 1)]
        return state

    try:
        # Streaming kullanmak için döngü; burada sadece nihai kullanırız
        resp_text = ""
        async for token in router.stream(
            [
                LLMMessage(role="system", content=SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_msg),
            ],
            temperature=0.4,
            max_tokens=4000,
        ):
            resp_text += token
        state["answer"] = resp_text or summaries_block
    except Exception as e:
        logger.warning(f"Sentez LLM hatası: {e}")
        state["answer"] = summaries_block

    state["citations"] = [{"n": i, **s} for i, s in enumerate(summaries, 1)]
    return state
