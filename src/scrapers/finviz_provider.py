import logging
from src.scrapers.finviz import FinvizScraper

logger = logging.getLogger(__name__)


class FinvizDataProvider:
    """Wraps the existing FinvizScraper behind the DataProvider interface."""

    def __init__(self, finviz: FinvizScraper):
        self._finviz = finviz
        self._cache: dict[str, dict] = {}

    async def _scrape_once(self, symbol: str) -> dict:
        """Scrape Finviz once per symbol and cache the result in memory."""
        if symbol not in self._cache:
            self._cache[symbol] = await self._finviz.scrape(symbol)
        return self._cache[symbol]

    async def get_fundamentals(self, symbol: str) -> dict:
        data = await self._scrape_once(symbol)
        return data.get("fundamentals", {})

    async def get_technicals(self, symbol: str) -> dict:
        data = await self._scrape_once(symbol)
        return data.get("technicals", {})

    async def get_analyst_data(self, symbol: str) -> dict:
        data = await self._scrape_once(symbol)
        return data.get("analyst", {})

    async def get_news(self, symbol: str) -> list[dict]:
        data = await self._scrape_once(symbol)
        return data.get("news", [])

    async def get_current_price(self, symbol: str) -> float | None:
        data = await self._scrape_once(symbol)
        technicals = data.get("technicals", {})
        price_str = technicals.get("Price")
        if price_str:
            try:
                return float(price_str)
            except (ValueError, TypeError):
                pass
        return None

    def clear_cache(self, symbol: str | None = None):
        """Drop cached scrape results (all symbols, or just one)."""
        if symbol is None:
            self._cache.clear()
        else:
            self._cache.pop(symbol, None)

    async def close(self) -> None:
        await self._finviz.close()
