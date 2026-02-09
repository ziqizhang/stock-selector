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


@pytest.mark.asyncio
async def test_base_scraper_cache_hit_skips_http(httpx_mock):
    """When cache returns content, no HTTP request should be made."""
    cached_html = "<html><body>Cached content</body></html>"

    async def fake_cache_get(url: str):
        return {"content": cached_html, "url": url}

    save_calls = []

    async def fake_cache_save(url: str, content: str):
        save_calls.append((url, content))

    scraper = FakeScraper(cache_get=fake_cache_get, cache_save=fake_cache_save)
    result = await scraper.scrape("AAPL")
    assert result["html_length"] == len(cached_html)
    # No HTTP request should have been made
    assert len(httpx_mock.get_requests()) == 0
    # No save should have been called (cache hit)
    assert len(save_calls) == 0
    await scraper.close()


@pytest.mark.asyncio
async def test_base_scraper_cache_miss_fetches_and_saves(httpx_mock):
    """On cache miss, fetch via HTTP and save to cache."""
    live_html = "<html><body>Live content</body></html>"
    httpx_mock.add_response(
        url="https://example.com/quote/AAPL",
        text=live_html,
    )

    async def fake_cache_get(url: str):
        return None  # cache miss

    save_calls = []

    async def fake_cache_save(url: str, content: str):
        save_calls.append((url, content))

    scraper = FakeScraper(cache_get=fake_cache_get, cache_save=fake_cache_save)
    result = await scraper.scrape("AAPL")
    assert result["html_length"] == len(live_html)
    # HTTP request was made
    assert len(httpx_mock.get_requests()) == 1
    # Content was saved to cache
    assert len(save_calls) == 1
    assert save_calls[0] == ("https://example.com/quote/AAPL", live_html)
    await scraper.close()
