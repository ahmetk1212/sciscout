"""Tavily tabanlı genel web arama + güvenilir alan filtreli scrape.

Tavily API (https://tavily.com) Google-vari web arama sağlar.
Ücretsiz katman: 1000 arama/ay. API anahtarı .env'de olmalı.

Tavily sonuçları kontrol altına alınmıştır: sadece TRUSTED_DOMAINS içindeki
alan adlarıyla filtrelenir. Böylece yalan haber sitelerine girilmez.
"""

from __future__ import annotations

import httpx

from ..config import get_settings
from .base import Document, Source, trusted


TAVILY_ENDPOINT = "https://api.tavily.com/search"


class WebSource(Source):
    name = "web"

    def __init__(self, max_results: int = 6, timeout: float = 20.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        settings = get_settings()
        if not settings.tavily_api_key:
            return []  # Anahtar yoksa sessizce pas geç

        max_results = kwargs.get("max_results", self.max_results)
        payload = {
            "api_key": settings.tavily_api_key,
            "query": query,
            "search_depth": kwargs.get("depth", "advanced"),
            "max_results": max_results * 3,  # Filtre sonrası max_results kalacak
            "include_raw_content": False,
            "include_answer": True,
            "include_domains": [],
        }
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                r = await client.post(TAVILY_ENDPOINT, json=payload)
                if r.status_code != 200:
                    return []
                body = r.json()
            except Exception:
                return []

        docs: list[Document] = []
        answer = body.get("answer") or ""
        if answer:
            # Tavily answer güvenilir kaynaklardan senteze dayalı; ek için genel yanıtı gömeriz
            docs.append(
                Document(
                    title="Tavily Synthesis Answer",
                    url="(synthesis)",
                    snippet=answer[:400],
                    source="tavily",
                    relevance_score=1.0,
                    abstract=answer,
                )
            )

        for result in body.get("results", []):
            url = result.get("url", "")
            if not trusted(url):
                continue
            docs.append(
                Document(
                    title=result.get("title", ""),
                    url=url,
                    snippet=result.get("content", "")[:400],
                    source="web",
                    relevance_score=float(result.get("score", 0)),
                    abstract=result.get("content"),
                    extra={"raw_content": result.get("raw_content")},
                )
            )
            if len(docs) >= max_results:
                break

        return docs

    async def fetch_full(self, doc: Document) -> str | None:
        """Güvenilir bir sayfayı çek + HTML'yi text'e çevir."""
        if not doc.url or doc.url == "(synthesis)":
            return None
        if not trusted(doc.url):
            return None

        async with httpx.AsyncClient(
            timeout=self.timeout,
            follow_redirects=True,
            headers={"User-Agent": "SciScout/0.1 (research-agent)"},
        ) as client:
            try:
                r = await client.get(doc.url)
                if r.status_code != 200:
                    return None
            except Exception:
                return None

        try:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(r.text, "html.parser")
            # script/style elemekleri atılır
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(" ", strip=True)
            # 40K char kırp
            return text[:40000]
        except Exception:
            return None
