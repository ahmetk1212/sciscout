"""Ana araştırma döngüsü (ResearchGraph).

3-ajan akışı (geleneksel Python döngüsü):
  START -> researcher -> reader -> synthesizer -> END
Her agent ResearchState dict'ini okur ve günceller.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Optional, TypedDict

from ..config import Settings, get_settings
from ..llm.router import LLMRouter
from ..sources.base import Document
from .reader import reader_agent
from .researcher import researcher_agent
from .synthesizer import synthesizer_agent

logger = logging.getLogger("sciscout.agents.graph")


class ResearchState(TypedDict, total=False):
    question: str
    search_query: str
    raw_documents: list[Document]
    selected_documents: list[Document]
    enriched_documents: list[dict]
    summaries: list[dict]
    answer: str
    citations: list[dict]
    per_source_counts: dict
    settings: Optional[Settings]
    router: Optional[LLMRouter]


class ResearchGraph:
    """3-ajan döngüsü orchestrator."""

    def __init__(self, settings: Optional[Settings] = None, router: Optional[LLMRouter] = None):
        self.settings = settings or get_settings()
        self.router = router or LLMRouter()

    async def run(self, question: str) -> ResearchState:
        """Question -> nihai cevap. Agent'ları sırayla çalıştırır."""
        if not self.router.has_any():
            raise RuntimeError("Hiç LLM API anahtarı yok. .env dosyasını kontrol et.")

        state: ResearchState = {
            "question": question,
            "settings": self.settings,
            "router": self.router,
        }
        steps = [
            ("researcher", researcher_agent),
            ("reader", reader_agent),
            ("synthesizer", synthesizer_agent),
        ]

        for name, agent in steps:
            logger.info(f"⏳ Agent: {name}")
            try:
                state = await agent(state)
                logger.info(f"✓ Agent bitti: {name}")
            except Exception as e:
                logger.error(f"Agent {name} hatası: {e}", exc_info=True)
                state[f"_error_{name}"] = str(e)

        return state


async def run_research(question: str) -> ResearchState:
    """Test ve CLI için convenience wrapper."""
    graph = ResearchGraph()
    return await graph.run(question)


def sync_run_research(question: str) -> ResearchState:
    """Sync wrapper (CLI'da çağrılır)."""
    return asyncio.run(run_research(question))
