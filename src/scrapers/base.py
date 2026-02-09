import asyncio
import time
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


class BaseScraper:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    _domain_locks: dict[str, asyncio.Lock] = {}
    _last_request: dict[str, float] = {}
    _min_interval: float = 1.0  # seconds between requests to the same domain

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=self.HEADERS,
            follow_redirects=True,
            timeout=30.0,
        )

    async def fetch(self, url: str) -> str:
        domain = urlparse(url).netloc
        lock = self._domain_locks.setdefault(domain, asyncio.Lock())

        async with lock:
            elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request[domain] = time.monotonic()

            response = await self.client.get(url)
            response.raise_for_status()
            return response.text

    def parse_html(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    async def scrape(self, symbol: str) -> dict:
        raise NotImplementedError

    async def close(self):
        await self.client.aclose()
