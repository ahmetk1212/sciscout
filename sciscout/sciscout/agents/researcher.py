"""Araştırma agent'ı — adım 1.

Görev: Kullanıcının sorusu → alaka düzeyi yüksek kaynaklarda ara.
Tüm kaynak modüllerini paralel çağırır, sonuçları puanlar, en iyi N taneyi seçer.
Sentez agent'ına hangi kaynakların "okunması" gerektiğini söyler.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import TYPE_CHECKING

from ..llm.base import LLMMessage
from ..sources import (
    ADSSource,
    ArxivSource,
    DOAJSource,
    EuropePMCSource,
    ForumsSource,
    GitHubSource,
    GoogleScholarSource,
    PubMedSource,
    SemanticScholarSource,
    StackOverflowSource,
    WebSource,
    WikipediaSource,
)

if TYPE_CHECKING:
    from .graph import ResearchState

logger = logging.getLogger("sciscout.agents.researcher")


SYSTEM_PROMPT = """You are a senior academic researcher selecting the most relevant
sources for a scientific/engineering question.

You receive a list of candidate documents from multiple sources:
- arXiv (preprints, physics/CS/math/engineering)
- Semantic Scholar (peer-reviewed papers)
- PubMed (biology/medicine)
- Europe PMC (biomedical open access)
- NASA ADS (astrophysics/cosmology)
- DOAJ (open access journals)
- Wikipedia (background concepts)
- GitHub (engineering implementations)
- StackExchange/Q&A (engineering problems)
- Google Scholar (broad coverage, often abstract-only)
- Reddit forums (community discussion)
- Web (Tavily search of trusted domains)

Eliminate ONLY:
- Exact duplicates of the same paper (keep one).
- Completely off-topic snippets with no relation to the question.
- Commercial / blog spam (NEVER trust untrusted URLs).

Be GENEROUS in selection — prefer more sources if relevant. Select AT MOST 10 documents.
Prioritize:
1) Recent peer-reviewed papers (arXiv/Semantic Scholar/PubMed/Europe PMC/ADS)
2) Wikipedia articles if the question asks for a concept background
3) GitHub repos / StackExchange for engineering implementation questions
4) Forum/web sources for "what's new / latest discoveries" questions
5) DOAJ for open-access full-text papers

Output STRICT JSON with two arrays:
  {
    "selected": [ { "url": "<url>", "why": "<1 sentence>" }, ... ],
    "ignored":  [ { "url": "<url>", "why": "<1 sentence>" }, ... ]
  }

Select AT MOST 6 documents. Prioritize:
1) Recent peer-reviewed papers (arXiv/Semantic Scholar/PubMed)
2) Wikipedia articles if the question asks for a concept background
3) GitHub repos / StackExchange for engineering implementation questions
4) Forum/web sources for "what's new / latest discoveries" questions

Be concise."""


async def researcher_agent(state: "ResearchState") -> "ResearchState":
    """Araştırma agent'ı: kaynakları topla, LLM ile seç."""
    question = state["question"]
    settings = state.get("settings")
    router = state.get("router")

    max_papers = settings.max_papers_per_query if settings else 6
    max_web = settings.max_web_results if settings else 4

    # 0) Türkçe/Almanca vb. olabilir → akademik kaynaklar için İngilizce'ye çevir
    search_query = question
    if router:
        try:
            q_resp = await router.chat(
                [
                    LLMMessage(
                        role="system",
                        content=(
                            "You translate a research question to an English search query. "
                            "Output ONLY the English search terms, no quotes, no explanation, no preamble. "
                            "Keep technical terms. Max 8 words."
                        ),
                    ),
                    LLMMessage(role="user", content=question),
                ],
                temperature=0.1,
                max_tokens=100,
            )
            translated = q_resp.text.strip().strip('"').strip()
            # Hata metni kontrolü
            if (
                translated
                and len(translated) > 3
                and not translated.startswith("[")
                and "error" not in translated.lower()
            ):
                search_query = translated
                state["search_query"] = search_query
                logger.info(f"Çevrilen sorgu: {search_query}")
            else:
                logger.warning(f"Çeviri başarısız (dropdown): {translated[:80]}")
        except Exception as e:
            logger.warning(f"Sorgu çeviri hatası: {e}")

    # Tüm kaynaklar paralel çalışır (12 kaynak)
    settings_cfg = state.get("settings")
    ads_key = getattr(settings_cfg, "nasa_ads_api_key", "") if settings_cfg else ""
    sources = {
        "arxiv": ArxivSource(max_results=max_papers),
        "semantic_scholar": SemanticScholarSource(max_results=max_papers),
        "pubmed": PubMedSource(max_results=4),
        "europe_pmc": EuropePMCSource(max_results=4),
        "wikipedia": WikipediaSource(max_results=3),
        "github": GitHubSource(max_results=4),
        "stackoverflow": StackOverflowSource(max_results=4),
        "scholar": GoogleScholarSource(max_results=4),
        "forums": ForumsSource(max_results=4),
        "web": WebSource(max_results=max_web),
        "doaj": DOAJSource(max_results=4),
        "nasa_ads": ADSSource(max_results=6, api_key=ads_key),
    }

    async def run(name, src):
        try:
            return name, await src.search(search_query)
        except Exception as e:
            logger.warning(f"Kaynak {name} hatası: {e}")
            return name, []

    results = await asyncio.gather(*[run(n, s) for n, s in sources.items()])
    all_docs = []
    per_source = {}
    for name, docs in results:
        per_source[name] = len(docs)
        all_docs.extend(docs)

    state["raw_documents"] = all_docs
    state["per_source_counts"] = per_source

    if not all_docs:
        state["selected_documents"] = []
        return state

    # LLM ile en iyi kaynakları seç
    router = state.get("router")
    if not router:
        state["selected_documents"] = all_docs[:6]
        return state

    candidates_text = _format_candidates(all_docs[:40])
    user_msg = f"QUESTION:\n{question}\n\nCANDIDATE DOCUMENTS:\n{candidates_text}\n\nReturn STRICT JSON. Select up to 10."

    try:
        resp = await router.chat(
            [
                LLMMessage(role="system", content=SYSTEM_PROMPT),
                LLMMessage(role="user", content=user_msg),
            ],
            temperature=0.2,
            max_tokens=3000,
        )
        selected_urls = _parse_selection(resp.text)
        url_to_doc = {d.url: d for d in all_docs}
        selected = []
        for url in selected_urls:
            if url in url_to_doc:
                selected.append(url_to_doc[url])
        if not selected:
            # Fallback: ilk 10
            selected = all_docs[:10]
        state["selected_documents"] = selected
    except Exception as e:
        logger.warning(f"Araştırma agent LLM hatası: {e}")
        state["selected_documents"] = all_docs[:6]

    return state


def _format_candidates(docs) -> str:
    lines = []
    for i, d in enumerate(docs, 1):
        snippet = (d.snippet or "")[:150].replace("\n", " ")
        lines.append(
            f"[{i}] source={d.source}\n    title={d.title}\n    url={d.url}\n    "
            f"authors={', '.join(d.authors[:3])}\n    published={d.published or '?'}\n    "
            f"snippet={snippet}"
        )
    return "\n\n".join(lines)


def _parse_selection(text: str) -> list[str]:
    """LLM'ın JSON'undan URL listesini çıkar."""
    # Markdown code fence olabilir
    t = text.strip()
    if t.startswith("```"):
        # json\n...\n```
        t = t.split("```")[1]
        if t.lower().startswith("json"):
            t = t[4:]
    try:
        data = json.loads(t)
        return [item["url"] for item in data.get("selected", [])]
    except Exception:
        # Regex fallback
        import re

        return re.findall(r'"url"\s*:\s*"([^"]+)"', text)
