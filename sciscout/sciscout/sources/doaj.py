"""DOAJ (Directory of Open Access Journals) kaynak modülü.

Ücretsiz, anahtar gerektirmez. Açık erişim dergilerindeki tam metin makaleler.
Dokümantasyon: https://doaj.org/api/v1/docs
"""

from __future__ import annotations

import httpx

from .base import Document, Source


DOAJ_SEARCH = "https://doaj.org/api/search/articles"


class DOAJSource(Source):
    name = "doaj"

    def __init__(self, max_results: int = 6, timeout: float = 12.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        params = {"search": query, "pageSize": max_results, "page": 1}
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.get(DOAJ_SEARCH, params=params)
                if r.status_code != 200:
                    return []
                body = r.json()
            except Exception:
                return []

        docs: list[Document] = []
        for item in body.get("results", [])[:max_results]:
            bib = item.get("bibjson", {})
            title = bib.get("title") or ""
            abstract = bib.get("abstract") or ""
            authors = [a.get("name") for a in (bib.get("author", []) or []) if a.get("name")]
            links = bib.get("link", [])
            url = ""
            for link in links:
                if link.get("type") == "fulltext":
                    url = link.get("url", "")
                    break
            journal_info = bib.get("journal", {}) or {}
            docs.append(
                Document(
                    title=title,
                    url=url or f"https://doaj.org/search?source={query.replace(' ', '+')}",
                    snippet=abstract[:300],
                    source=self.name,
                    authors=authors,
                    published=bib.get("year") or None,
                    doi=bib.get("doi") or None,
                    abstract=abstract or None,
                    extra={
                        "journal": journal_info.get("title"),
                        "publisher": journal_info.get("publisher"),
                        "license": (bib.get("license") or [{"url": ""}])[0].get("url"),
                    },
                )
            )
        return docs
