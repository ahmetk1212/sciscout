"""GitHub kaynak modülü — kod/repo tabanlı mühendislik problemleri için.

GitHub REST API: https://api.github.com/search/repositories
Ücretsiz, anahtar gerekmez (60 istek/saat). Token varsa 5000/saat.
"""

from __future__ import annotations

import httpx

from .base import Document, Source


GITHUB_SEARCH = "https://api.github.com/search/repositories"


class GitHubSource(Source):
    name = "github"

    def __init__(self, max_results: int = 6, timeout: float = 12.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        # Sıralama: mühendislik/teknik soru için stars + recently updated
        params = {
            "q": query,
            "sort": "stars",
            "order": "desc",
            "per_page": max_results,
        }
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "SciScout/0.1",
        }
        import os

        token = os.environ.get("GITHUB_TOKEN", "")
        if token:
            headers["Authorization"] = f"Bearer {token}"

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            try:
                r = await client.get(GITHUB_SEARCH, params=params)
                if r.status_code == 403:
                    return []  # rate limit
                r.raise_for_status()
            except Exception:
                return []

        docs: list[Document] = []
        for item in r.json().get("items", [])[:max_results]:
            docs.append(
                Document(
                    title=item.get("full_name", ""),
                    url=item.get("html_url", ""),
                    snippet=(item.get("description") or "")[:300],
                    source=self.name,
                    published=(item.get("pushed_at") or "")[:10] or None,
                    citation_count=item.get("stargazers_count"),
                    relevance_score=float(item.get("score", 0)),
                    extra={
                        "language": item.get("language"),
                        "forks": item.get("forks_count"),
                        "topics": item.get("topics", []),
                        "homepage": item.get("homepage"),
                    },
                )
            )
        return docs
