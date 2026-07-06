"""NASA ADS (Astrophysics Data System) kaynak modülü.

NASA ADS, astrofizik/kozmoloji makaleleri için en kapsamlı kaynak.
Ücretsiz API: https://ui.adsabs.harvard.edu/help/api/api-binding.php
Anahtar gerekli: https://ui.adsabs.harvard.edu/user/settings/token
Ücretsiz tier cömert (yeterli günlük sorgu).

Ek olarak anahtar yoksa parsed HTML search fallback çalışır (sınırlı).
"""

from __future__ import annotations

import httpx

from .base import Document, Source


ADS_API = "https://api.adsabs.harvard.edu/v1/search/query"


class ADSSource(Source):
    name = "nasa_ads"

    def __init__(self, max_results: int = 8, timeout: float = 12.0, api_key: str = ""):
        super().__init__(max_results=max_results)
        self.timeout = timeout
        self.api_key = api_key

    async def search(self, query: str, **kwargs) -> list[Document]:
        if not self.api_key:
            return []  # Anahtar yoksa sessizce pas geç (soylenir, extension olarak eklenir)

        max_results = kwargs.get("max_results", self.max_results)
        # Solr query formatı; basitleştir
        q = query.replace('"', "").strip()
        params = {
            "q": f'title:"{q}" OR abstract:"{q}" OR full:"{q}"',
            "fl": "id,title,abstract,author,year,doi,bibcode,citation_count,pub,pubdate",
            "rows": max_results,
            "sort": "date desc",
        }
        headers = {"Authorization": f"Bearer {self.api_key}"}

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            try:
                r = await client.get(ADS_API, params=params)
                if r.status_code != 200:
                    return []
                body = r.json()
            except Exception:
                return []

        docs: list[Document] = []
        for item in body.get("response", {}).get("docs", [])[:max_results]:
            title = (
                (item.get("title") or [""])[0]
                if isinstance(item.get("title"), list)
                else (item.get("title") or "")
            )
            abstract = item.get("abstract", "") or ""
            authors = item.get("author", []) or []
            doi = (
                (item.get("doi") or [""])[0]
                if isinstance(item.get("doi"), list)
                else item.get("doi")
            )
            bibcode = item.get("bibcode", "")
            url = f"https://ui.adsabs.harvard.edu/abs/{bibcode}/abstract" if bibcode else ""
            docs.append(
                Document(
                    title=title,
                    url=url,
                    snippet=abstract[:300],
                    source=self.name,
                    authors=authors[:8],
                    published=item.get("pubdate", "")[:10] or None,
                    doi=doi,
                    abstract=abstract,
                    citation_count=item.get("citation_count"),
                    extra={"bibcode": bibcode, "venue": item.get("pub", "")},
                )
            )
        return docs
