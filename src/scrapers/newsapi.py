"""News fetcher using NewsAPI (newsapi.org) as an alternative to Google News RSS scraping."""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

NEWS_API_URL = "https://newsapi.org/v2/everything"


class NewsAPIFetcher:
    """Fetch news articles via NewsAPI. Requires NEWS_API_KEY env var."""

    def __init__(self):
        self._api_key = os.environ.get("NEWS_API_KEY", "")
        self._client = httpx.AsyncClient(timeout=15.0)

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def fetch_news(self, symbol: str) -> dict:
        """Fetch news for a stock symbol. Returns same shape as NewsScraper.scrape()."""
        query_symbol = symbol.rstrip(".L") if symbol.endswith(".L") else symbol
        params = {
            "q": f"{query_symbol} stock",
            "apiKey": self._api_key,
            "language": "en",
            "sortBy": "publishedAt",
            "pageSize": 20,
        }
        response = await self._client.get(NEWS_API_URL, params=params)
        response.raise_for_status()
        data = response.json()

        articles = []
        for item in data.get("articles", []):
            articles.append({
                "title": item.get("title", ""),
                "source": item.get("source", {}).get("name", ""),
                "snippet": item.get("description", "") or "",
            })
        return {"news_articles": articles}

    async def close(self):
        await self._client.aclose()
