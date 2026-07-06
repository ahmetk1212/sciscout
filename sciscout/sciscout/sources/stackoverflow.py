"""StackExchange API kaynak modülü.
Tüm Stack Exchange sitelerinde arama yapar (stackoverflow, physics, math, dsp, vb.).
Ücretsiz, anahtar gerekmez, ama rate-limit için Application-Key gerekiyor (opsiyonel).

Dokümantasyon: https://api.stackexchange.com/docs
"""

from __future__ import annotations

import httpx

from .base import Document, Source


# İlgili Stack Exchange siteleri
STACK_SITES = [
    "stackoverflow",
    "physics",
    "math",
    "dsp",
    "electronics",
    "chemistry",
    "biology",
    "scicomp",
    "mathoverflow",
    "cstheory",
    "ai",
    "mechanical",
    "engineering",
]


class StackOverflowSource(Source):
    name = "stackoverflow"

    def __init__(self, max_results: int = 6, timeout: float = 12.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        site = kwargs.get("site", None)
        sites = [site] if site else STACK_SITES

        results: list[Document] = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for s in sites:
                params = {
                    "pagesize": max_results,
                    "order": "desc",
                    "sort": "relevance",
                    "intitle": query,
                    "site": s,
                    "filter": "default",
                }
                try:
                    r = await client.get(
                        "https://api.stackexchange.com/2.3/similar",
                        params=params,
                    )
                    if r.status_code != 200:
                        continue
                except Exception:
                    continue
                for item in r.json().get("items", [])[: self.max_results]:
                    results.append(self._make_doc(item, s))

        # Relevance skoruna göre sırala (accepted > yüksek puan)
        results.sort(key=lambda d: d.relevance_score or 0, reverse=True)
        return results[:max_results]

    def _make_doc(self, item: dict, site: str) -> Document:
        accepted = item.get("is_answered") or False
        return Document(
            title=item.get("title", ""),
            url=item.get("link", ""),
            snippet=(item.get("excerpt") or item.get("body_markdown") or "")[:300],
            source=f"stackexchange:{site}",
            published=(item.get("last_activity_date", "") or "")[:10] or None,
            citation_count=item.get("score"),
            relevance_score=float(item.get("score", 0)),
            extra={
                "accepted": accepted,
                "answered": item.get("is_answered", False),
                "tags": item.get("tags", []),
                "site": site,
            },
        )
