"""Google Scholar scrape modülü.

Google Scholar, scrape için doğrudan API vermez ve Cloudflare-engellidir.
Scholarly library (https://github.com/scholarly-python-pro/scholarly) veya
direct HTML scrape kullanılabilir. Burada basit htmlyakalama kullanırız:
- gizli rate-limit;tamment sadece en iyi 10 sonucu çeker
- şıkıp domain/regex ile parse eder

Not: Bu modül opsiyoneldir. Google bot-engeli koyarsa 0 döner.
"""

from __future__ import annotations

import re
import time
from typing import Any

import httpx

from .base import Document, Source


SCHOLAR_URL = "https://scholar.google.com/scholar"

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


class GoogleScholarSource(Source):
    name = "google_scholar"

    def __init__(
        self,
        max_results: int = 8,
        timeout: float = 15.0,
        min_delay: float = 5.0,
    ):
        super().__init__(max_results=max_results)
        self.timeout = timeout
        self.min_delay = min_delay
        self._last_call = 0.0

    async def search(self, query: str, **kwargs) -> list[Document]:
        max_results = kwargs.get("max_results", self.max_results)

        # Rate-limit koruması: her çağrı arasında en az min_delay saniye
        elapsed = time.time() - self._last_call
        if elapsed < self.min_delay:
            import asyncio

            await asyncio.sleep(self.min_delay - elapsed)

        params = {
            "q": query,
            "hl": "en",
            "as_sdt": "0",
            "num": str(min(max_results, 10)),
        }
        headers = {
            "User-Agent": USER_AGENT,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html",
            "Referer": "https://scholar.google.com/",
        }

        async with httpx.AsyncClient(
            timeout=self.timeout, headers=headers, follow_redirects=True
        ) as client:
            try:
                r = await client.get(SCHOLAR_URL, params=params)
                if r.status_code != 200 or "Captcha" in r.text:
                    return []
                body = r.text
            except Exception:
                return []
        self._last_call = time.time()
        return self._parse(body)

    def _parse(self, html: str) -> list[Document]:
        """Basit regex-tabanlı Scholar parse. Çok kırılgan ama muğlak olmadan iyi kalanlar yakalanır."""
        docs: list[Document] = []
        blocks = re.findall(
            r'<div class="gs_ri">(.*?)</div>\s*<div class="gs_fl gs_flb">',
            html,
            flags=re.DOTALL,
        )
        for b in blocks:
            try:
                title_m = re.search(r"<h3[^>]*>.*?<a [^>]*>(.*?)</a>", b, re.DOTALL)
                url_m = re.search(r'<a [^>]*href="([^"]+)"', b)
                snippet_m = re.search(r'<div class="gs_rs">(.*?)</div>', b, re.DOTALL)
                meta_m = re.search(r'<div class="gs_a">(.*?)</div>', b, re.DOTALL)

                title = _strip_html(title_m.group(1)) if title_m else ""
                url = url_m.group(1) if url_m else ""
                snippet = _strip_html(snippet_m.group(1)) if snippet_m else ""
                meta = _strip_html(meta_m.group(1)) if meta_m else ""

                if not title:
                    continue
                # meta: "A Author, B Author - Journal, 2021 - publisher"
                authors: list[str] = []
                year = None
                if meta:
                    parts = [p.strip() for p in meta.split(" - ")]
                    if parts:
                        for a in parts[0].split(","):
                            if a:
                                authors.append(a.strip())
                    for p in parts:
                        m = re.search(r"\b(20\d\d|19\d\d)\b", p)
                        if m:
                            year = m.group(1)
                if snippet:
                    snippet = snippet.replace("…", "… ").strip()
                docs.append(
                    Document(
                        title=title,
                        url=url,
                        snippet=snippet[:300],
                        source=self.name,
                        authors=authors,
                        published=f"{year}-01-01" if year else None,
                        abstract=snippet or None,
                    )
                )
            except Exception:
                continue
        return docs


def _strip_html(s: str) -> str:
    from bs4 import BeautifulSoup

    return BeautifulSoup(s, "html.parser").get_text(" ", strip=True)
