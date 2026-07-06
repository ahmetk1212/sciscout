"""Semantic Scholar kaynak modülü.

Dokümantasyon: https://api.semanticscholar.org/api-docs/graph
Ücretsiz, anahtar gerekmez (rate-limit 100 istek/5dk).
"""

from __future__ import annotations

import httpx

from ..config import get_settings
from .base import Document, Source


S2_API = "https://api.semanticscholar.org/graph/v1/paper/search"

# Default fields — sadece aramada dönecek alanlar
SEARCH_FIELDS = ",".join(
    [
        "paperId",
        "externalIds",
        "title",
        "abstract",
        "authors",
        "year",
        "publicationDate",
        "citationCount",
        "openAccessPdf",
        "url",
        "venue",
    ]
)


class SemanticScholarSource(Source):
    name = "semantic_scholar"

    def __init__(self, max_results: int = 8, timeout: float = 15.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        params = {
            "query": query,
            "limit": min(max_results, 100),
            "fields": SEARCH_FIELDS,
            "year": kwargs.get("year", ""),
        }
        headers = {"User-Agent": "SciScout/0.1 (research-agent)"}
        settings = get_settings()
        if settings.semantic_scholar_api_key:
            headers["x-api-key"] = settings.semantic_scholar_api_key

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.get(S2_API, params=params, headers=headers)
                if r.status_code == 429:
                    return []
                r.raise_for_status()
            except Exception:
                return []
        return self._parse_response(r.json())

    def _parse_response(self, body: dict) -> list[Document]:
        docs: list[Document] = []
        for p in body.get("data", []) or []:
            try:
                authors = [a.get("name") for a in (p.get("authors") or []) if a.get("name")]
                external_ids = p.get("externalIds") or {}
                doi = external_ids.get("DOI")
                pdf_url = None
                oa = p.get("openAccessPdf")
                if isinstance(oa, dict):
                    pdf_url = oa.get("url")
                docs.append(
                    Document(
                        title=p.get("title", ""),
                        url=p.get("url")
                        or f"https://www.semanticscholar.org/paper/{p.get('paperId', '')}",
                        snippet=(p.get("abstract") or "")[:300],
                        source=self.name,
                        authors=authors,
                        published=str(p.get("publicationDate") or p.get("year") or "")[:10] or None,
                        doi=doi,
                        pdf_url=pdf_url,
                        abstract=p.get("abstract"),
                        citation_count=p.get("citationCount"),
                    )
                )
            except Exception:
                continue
        return docs
