import asyncio
import logging
import time
from typing import Callable, Awaitable
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# Type aliases for the optional cache callbacks
CacheGetter = Callable[[str], Awaitable[dict | None]]
CacheSaver = Callable[[str, str], Awaitable[None]]


class BaseScraper:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    _domain_locks: dict[str, asyncio.Lock] = {}
    _last_request: dict[str, float] = {}
    _min_interval: float = 1.0  # seconds between requests to the same domain

    def __init__(
        self,
        cache_get: CacheGetter | None = None,
        cache_save: CacheSaver | None = None,
    ):
        self.client = httpx.AsyncClient(
            headers=self.HEADERS,
            follow_redirects=True,
            timeout=30.0,
        )
        self._cache_get = cache_get
        self._cache_save = cache_save

    async def fetch(self, url: str) -> str:
        if self._cache_get:
            cached = await self._cache_get(url)
            if cached:
                logger.debug("Cache hit for %s", url)
                return cached["content"]

        domain = urlparse(url).netloc
        lock = self._domain_locks.setdefault(domain, asyncio.Lock())

        async with lock:
            elapsed = time.monotonic() - self._last_request.get(domain, 0.0)
            if elapsed < self._min_interval:
                await asyncio.sleep(self._min_interval - elapsed)
            self._last_request[domain] = time.monotonic()

            response = await self.client.get(url)
            response.raise_for_status()
            text = response.text

        if self._cache_save:
            await self._cache_save(url, text)

        return text

    def parse_html(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    async def scrape(self, symbol: str) -> dict:
        raise NotImplementedError

    async def close(self):
        await self.client.aclose()
