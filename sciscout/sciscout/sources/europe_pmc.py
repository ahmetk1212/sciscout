"""Europe PMC kaynak modülü — biyomedikal makaleler (PubMed + Avrupa).

Ücretsiz API, anahtar gerekmez. Açık erişim tam metin linki de verir.
Dokümantasyon: https://europepmc.org/RestfulWebService
"""

from __future__ import annotations

import httpx

from .base import Document, Source


EUROPEPMC_SEARCH = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePMCSource(Source):
    name = "europe_pmc"

    def __init__(self, max_results: int = 8, timeout: float = 12.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        params = {
            "query": query,
            "resultType": "core",
            "pageSize": max_results,
            "format": "json",
            "sort": "P_PDATE_D desc",
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.get(EUROPEPMC_SEARCH, params=params)
                if r.status_code != 200:
                    return []
                body = r.json()
            except Exception:
                return []

        docs: list[Document] = []
        for item in body.get("resultList", {}).get("result", [])[:max_results]:
            pmid = item.get("pmid") or ""
            pmcid = item.get("pmcid") or ""
            # Öncelikle tam metin açıksa PMC URL'sini kullan
            if pmcid and item.get("isOpenAccess") == "Y":
                full_text_url = f"https://europepmc.org/article/PMC/{pmcid}"
            elif pmid:
                full_text_url = f"https://europepmc.org/article/MED/{pmid}"
            else:
                full_text_url = ""
            docs.append(
                Document(
                    title=item.get("title", ""),
                    url=full_text_url
                    or f"https://europepmc.org/search?query={query.replace(' ', '+')}",
                    snippet=(item.get("abstractText") or "")[:300],
                    source=self.name,
                    authors=[a.strip() for a in (item.get("authorString") or "").split(",")],
                    published=item.get("firstPublicationDate", "")[:10] or None,
                    doi=item.get("doi"),
                    abstract=item.get("abstractText"),
                    citation_count=item.get("citedByCount"),
                    extra={
                        "journal": item.get("journalTitle"),
                        "pmid": pmid,
                        "pmcid": pmcid,
                        "isOpenAccess": item.get("isOpenAccess"),
                    },
                )
            )
        return docs
