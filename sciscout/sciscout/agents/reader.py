"""Okuma agent'ı — adım 2.

Görev: Araştırma ajanının seçtiği makalelerin tam metnini/özetini getirir.
PDF varsa PyMuPDF ile indirip metne çevirir. Yoksa HTML scrape eder.
Eğer makale özeti yeterliyse, özetle yetinir (akıllı mod).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from ..llm.base import LLMMessage
from ..sources.arxiv import ArxivSource
from ..sources.web import WebSource

if TYPE_CHECKING:
    from .graph import ResearchState

logger = logging.getLogger("sciscout.agents.reader")


SYSTEM_PROMPT = """You are an expert scientific reader. For each document provided,
write a structured summary in Turkish (unless the user writes in English).

Output format for each source (max 250 words):
  ## <title>
  - **Yazar(lar)**:
  - **Yıl**:
  - **Yayın/Tür**:
  - **Ana bulgu/bulus**:
  - **Metod**:
  - **Sınırlar / notlar**:

Do not invent facts. Only summarize what is in the document.
Stop reading and return what you have if context limit is near."""


async def reader_agent(state: "ResearchState") -> "ResearchState":
    """Seçilen dokümanları oku, her biri için özet yaz."""
    selected = state.get("selected_documents", [])
    if not selected:
        state["summaries"] = []
        return state

    settings = state.get("settings")
    router = state.get("router")

    arxiv_source = ArxivSource()
    web_source = WebSource()

    # 1) Tam metin/abstract toplama
    enriched = []
    for doc in selected[:10]:  # en fazla 10 döküman
        text = doc.abstract or doc.snippet or ""
        # Akıllı: abstract yeterliyse PDF indirme; yoksa indir
        if (
            settings
            and settings.pdf_read
            and doc.pdf_url
            and len(text) < 200
            and doc.source == "arxiv"
        ):
            try:
                full = await arxiv_source.fetch_full(doc)
                if full:
                    text = full[:15000]
            except Exception as e:
                logger.warning(f"PDF okuma hatası ({doc.url}): {e}")

        if doc.source == "web" and len(text) < 200:
            try:
                full = await web_source.fetch_full(doc)
                if full:
                    text = full[:10000]
            except Exception:
                pass

        # Wikipedia zaten fetch_full yaptı (arama sırasında)
        if doc.source == "wikipedia" and doc.abstract:
            text = doc.abstract

        enriched.append(
            {
                "title": doc.title,
                "url": doc.url,
                "source": doc.source,
                "authors": doc.authors,
                "published": doc.published,
                "text": text[:15000],
            }
        )

    state["enriched_documents"] = enriched

    # 2) LLM ile her döküman için özet üret
    if not router:
        state["summaries"] = [_fallback_summary(d) for d in enriched]
        return state

    summaries = []
    for d in enriched:
        user_msg = (
            f"Title: {d['title']}\n"
            f"Source: {d['source']}\n"
            f"Published: {d['published'] or '?'}\n"
            f"Content:\n{d['text'][:8000]}\n\n"
            f"Write a structured summary."
        )
        try:
            resp = await router.chat(
                [
                    LLMMessage(role="system", content=SYSTEM_PROMPT),
                    LLMMessage(role="user", content=user_msg),
                ],
                temperature=0.2,
                max_tokens=800,
            )
            summaries.append(
                {
                    "title": d["title"],
                    "url": d["url"],
                    "source": d["source"],
                    "summary": resp.text,
                }
            )
        except Exception as e:
            logger.warning(f"LLM özet hatası ({d['url']}): {e}")
            summaries.append(_fallback_summary(d))

    state["summaries"] = summaries
    return state


def _fallback_summary(d: dict) -> dict:
    """LLM yoksa basıt metin kesme."""
    text = d.get("text", "")
    return {
        "title": d.get("title", ""),
        "url": d.get("url", ""),
        "source": d.get("source", ""),
        "summary": text[:400] + ("..." if len(text) > 400 else ""),
    }
