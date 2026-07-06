"""PubMed / NCBI E-utilities kaynak modülü.

Dokümantasyon: https://www.ncbi.nlm.nih.gov/books/NBK25501/ (E-utilities)
Ücretsiz. 3 adımlı akış:
  1) esearch: query → PMID listesi
  2) esummary: PMID → özet metadata
  3) efetch: PMID → tam müfredate (abstract dahil)
Burada 1+2 kullanırız (abstract için esummary yeterli).
"""

from __future__ import annotations

import httpx
from bs4 import BeautifulSoup

from .base import Document, Source


ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"


class PubMedSource(Source):
    name = "pubmed"

    def __init__(self, max_results: int = 8, timeout: float = 15.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r1 = await client.get(
                    ESEARCH,
                    params={
                        "db": "pubmed",
                        "term": query,
                        "retmax": max_results,
                        "sort": "date",
                        "retmode": "json",
                    },
                )
                r1.raise_for_status()
                ids = r1.json().get("esearchresult", {}).get("idlist", [])
                if not ids:
                    return []

                r2 = await client.get(
                    ESUMMARY,
                    params={
                        "db": "pubmed",
                        "id": ",".join(ids),
                        "retmode": "xml",
                    },
                )
                r2.raise_for_status()
            except Exception:
                return []
        return self._parse_summaries(r2.text, ids)

    def _parse_summaries(self, xml: str, ids: list[str]) -> list[Document]:
        soup = BeautifulSoup(xml, "xml")
        docs: list[Document] = []
        for doc in soup.find_all("DocSum"):
            try:
                pmid = _find_id(doc, "pubmed")
                title = _text(doc, "Title")
                authors = [_text(a, "Name") for a in doc.find_all("Author")]
                # PubMed özetleri esummary'de geliyor
                abstract = _text(doc, "Abstract")
                pub_date = _text(doc, "PubDate")
                journal = _text(doc, "Source")
                url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
                docs.append(
                    Document(
                        title=title,
                        url=url,
                        snippet=(abstract or title)[:300],
                        source=self.name,
                        authors=authors,
                        published=pub_date or None,
                        abstract=abstract or None,
                        extra={"journal": journal, "pmid": pmid},
                    )
                )
            except Exception:
                continue
        return docs


def _text(node, tag: str) -> str:
    n = node.find(tag)
    return n.text.strip() if n else ""


def _find_id(node, _name: str) -> str:
    n = node.find("Id")
    return n.text.strip() if n else ""
