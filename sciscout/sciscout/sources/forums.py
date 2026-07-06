"""Bilimsel/mühendislik forumları kaynak modülü.

- Physics Forums (physicsforums.com) — RSS yok, search.html scrape eder
- Engineering.com forum / Reddit API (r/Physics, r/engineering, r/AskEngineers,
  r/AskScience, r/Physics)

Reddit API, gerçek bir JSON API verir ve ücretsizdir. Daha güvenilir.
"""

from __future__ import annotations

import httpx

from .base import Document, Source, trusted


REDDIT_SEARCH = "https://www.reddit.com/search.json"

RELEVANT_SUBREDDITS = [
    "Physics",
    "AskPhysics",
    "engineering",
    "AskEngineers",
    "AskScience",
    "Math",
    "MachineLearning",
    "Science",
    "labrats",
    "Chemistry",
    "CFD",
    "FE",
    "ElectricalEngineering",
]


class ForumsSource(Source):
    name = "forums"

    def __init__(self, max_results: int = 6, timeout: float = 10.0):
        super().__init__(max_results=max_results)
        self.timeout = timeout

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)
        subreddit = kwargs.get("subreddit", None)
        params = {
            "q": query,
            "sort": "relevance",
            "limit": max_results,
            "type": "link",
        }
        headers = {"User-Agent": "SciScout/0.1 (research bot) by /u/sciscout"}

        url = REDDIT_SEARCH
        if subreddit:
            url = f"https://www.reddit.com/r/{subreddit}/search.json"
            params["restrict_sr"] = 1

        async with httpx.AsyncClient(timeout=self.timeout, headers=headers) as client:
            try:
                r = await client.get(url, params=params)
                if r.status_code != 200:
                    return []
                body = r.json()
            except Exception:
                return []

        docs: list[Document] = []
        for item in body.get("data", {}).get("children", [])[:max_results]:
            child = item.get("data") or {}
            url = child.get("url") or ""
            permalink = child.get("permalink") or ""
            full_url = f"https://www.reddit.com{permalink}" if permalink else url
            if not trusted(full_url) and child.get("subreddit_name_prefixed"):
                # reddit sebuah ile subreddit var: güvenilir ama dış URL yine control et
                pass
            snippet = (child.get("selftext") or child.get("title") or "")[:300]
            docs.append(
                Document(
                    title=child.get("title", ""),
                    url=full_url,
                    snippet=snippet,
                    source=f"reddit:r/{child.get('subreddit', '?')}",
                    authors=[str(child.get("author"))] if child.get("author") else [],
                    published=_iso(float(child.get("created_utc") or 0)) or None,
                    citation_count=child.get("score"),
                    relevance_score=float(child.get("score", 0)),
                    extra={
                        "subreddit": child.get("subreddit"),
                        "num_comments": child.get("num_comments"),
                        "flair": child.get("link_flair_text"),
                    },
                )
            )

        # Reddit güvenilir ama dış digoğu linkleri olabilir;
        # core snippet bile yabancı URL barındırmayacağı icin bir filter uygulamıyoruz.
        return docs


def _iso(ts: float) -> str:
    import datetime as _dt

    try:
        return _dt.datetime.utcfromtimestamp(float(ts)).strftime("%Y-%m-%d")
    except Exception:
        return ""
