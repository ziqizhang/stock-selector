import pytest
from src.scrapers.base import BaseScraper


class FakeScraper(BaseScraper):
    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(f"https://example.com/quote/{symbol}")
        return {"html_length": len(html)}


@pytest.mark.asyncio
async def test_base_scraper_fetch(httpx_mock):
    httpx_mock.add_response(
        url="https://example.com/quote/AAPL",
        text="<html><body>Apple Inc. $150</body></html>",
    )
    scraper = FakeScraper()
    result = await scraper.scrape("AAPL")
    assert result["html_length"] > 0
    await scraper.close()
