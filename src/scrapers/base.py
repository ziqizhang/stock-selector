import logging
from typing import Callable, Awaitable

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
