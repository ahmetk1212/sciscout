"""Wikipedia + Wikidata kaynak modülü.

Wikipedia REST API: https://en.wikipedia.org/api/rest_v1/
- /search/page : arama
- /summary/{title} : sayfanın özeti
Ücretsiz, anahtar gerekmez.
"""

from __future__ import annotations

import httpx

from .base import Document, Source


WIKI_SEARCH = "https://en.wikipedia.org/w/rest.php/v1/search/page"
WIKI_SUMMARY = "https://en.wikipedia.org/api/rest_v1/summary/{title}"
WIKIDATA_SEARCH = "https://www.wikidata.org/w/api.php"


class WikipediaSource(Source):
    name = "wikipedia"

    def __init__(self, max_results: int = 5, lang: str = "en", timeout: float = 10.0):
        super().__init__(max_results=max_results)
        self.lang = lang
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        headers = {"User-Agent": "SciScout/0.1 (educational-agent)"}
        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            try:
                r = await client.get(
                    WIKI_SEARCH,
                    params={
                        "q": query,
                        "limit": max_results,
                    },
                )
                r.raise_for_status()
            except Exception:
                return []

        docs: list[Document] = []
        for p in r.json().get("pages", [])[:max_results]:
            title = p.get("title") or p.get("key", "")
            if not title:
                continue
            snippet = p.get("excerpt", "") or ""
            url = f"https://en.wikipedia.org/wiki/{p.get('key', title.replace(' ', '_'))}"
            docs.append(
                Document(
                    title=title,
                    url=url,
                    snippet=_strip_html(snippet),
                    source=self.name,
                    extra={"page_id": p.get("id")},
                )
            )

        # İlk dokümanın tam özetini de yükle
        for d in docs:
            text = await self.fetch_full(d)
            if text:
                d.abstract = text
        return docs

    async def fetch_full(self, doc: Document) -> str | None:
        title = doc.title.replace(" ", "_")
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.get(
                    WIKI_SUMMARY.format(title=title),
                    headers={"User-Agent": "SciScout/0.1 (educational-agent)"},
                )
                r.raise_for_status()
            except Exception:
                return None
        body = r.json()
        return body.get("extract") or None


def _strip_html(s: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(s, "html.parser").get_text(" ", strip=True)
