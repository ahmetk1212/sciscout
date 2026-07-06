"""arXiv kaynak modülü.

arXiv API: http://export.arxiv.org/api/query
Atom feed döndürür. xml parsing için BeautifulSoup kullanılır.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
from bs4 import BeautifulSoup

from .base import Document, Source


ARXIV_API = "https://export.arxiv.org/api/query"


class ArxivSource(Source):
    name = "arxiv"

    def __init__(self, max_results: int = 8, timeout: float = 15.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        params = {
            "search_query": self._build_query(query),
            "start": 0,
            "max_results": max_results,
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }

        docs: list[Document] = []
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                r = await client.get(ARXIV_API, params=params)
                r.raise_for_status()
            except Exception:
                return []

        soup = BeautifulSoup(r.text, "xml")
        for entry in soup.find_all("entry"):
            try:
                docs.append(self._parse_entry(entry))
            except Exception:
                continue
        return docs

    def _build_query(self, q: str) -> str:
        # Kullanıcı serbest metin girdiği için all:"..." şeklinde aratıyoruz;
        # arXiv bunu çok güçlü tutuyor. abs:"" ve ti:"" alternatif olarak
        # çok sorgu döndüreceğini düşündüğümüz için all kullanırız.
        q = q.strip()
        return f'all:"{q}"' if " " in q and '"' not in q else f"all:{q}"

    def _parse_entry(self, entry: Any) -> Document:
        def _text(tag: str) -> str:
            node = entry.find(tag)
            return node.text.strip() if node else ""

        id_url = _text("id")
        title = _text("title").replace("\n", " ")
        summary = _text("summary").replace("\n", " ")
        published = _text("published")[:10] if _text("published") else None

        authors = []
        for a in entry.find_all("author"):
            n = a.find("name")
            if n:
                authors.append(n.text.strip())

        # PDF linki
        pdf_url = None
        for link in entry.find_all("link"):
            if link.get("title") == "pdf":
                pdf_url = link.get("href")
                break

        doi = _text("arxiv:doi") or None
        if not doi:
            doi_node = entry.find("arxiv:doi")
            if doi_node is not None:
                doi = doi_node.text.strip()

        return Document(
            title=title,
            url=id_url,
            snippet=summary[:300] + "…" if len(summary) > 300 else summary,
            source=self.name,
            authors=authors,
            published=published,
            doi=doi,
            pdf_url=pdf_url,
            abstract=summary,
        )

    async def fetch_full(self, doc: Document) -> str | None:
        """PDF indir + PyMuPDF ile metne çevir."""
        if not doc.pdf_url:
            return None
        try:
            import fitz  # pymupdf
        except ImportError:
            return None

        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            try:
                r = await client.get(doc.pdf_url)
                r.raise_for_status()
            except Exception:
                return None

        try:
            with fitz.open(stream=r.content, filetype="pdf") as pdf:
                return "\n\n".join(page.get_text() for page in pdf)
        except Exception:
            return None
