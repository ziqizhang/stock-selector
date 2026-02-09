"""Tests for DataProvider implementations and the provider protocol."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.scrapers.provider import DataProvider
from src.scrapers.finviz_provider import FinvizDataProvider


# ---------------------------------------------------------------------------
# FinvizDataProvider
# ---------------------------------------------------------------------------


def _make_finviz_data():
    return {
        "all_data": {"P/E": "25.3", "RSI (14)": "55.2", "Target Price": "180"},
        "fundamentals": {"P/E": "25.3", "EPS (ttm)": "6.50"},
        "technicals": {"RSI (14)": "55.2", "SMA50": "3.20%"},
        "analyst": {"Target Price": "180", "Recom": "1.8"},
        "news": [{"timestamp": "Jan-01", "title": "Good news", "url": "https://example.com"}],
    }


@pytest.fixture
def finviz_provider():
    mock_scraper = AsyncMock()
    mock_scraper.scrape.return_value = _make_finviz_data()
    mock_scraper.close = AsyncMock()
    return FinvizDataProvider(mock_scraper), mock_scraper


@pytest.mark.asyncio
async def test_finviz_provider_get_fundamentals(finviz_provider):
    provider, scraper = finviz_provider
    result = await provider.get_fundamentals("AAPL")
    assert result == {"P/E": "25.3", "EPS (ttm)": "6.50"}
    scraper.scrape.assert_awaited_once_with("AAPL")


@pytest.mark.asyncio
async def test_finviz_provider_get_technicals(finviz_provider):
    provider, _ = finviz_provider
    result = await provider.get_technicals("AAPL")
    assert result == {"RSI (14)": "55.2", "SMA50": "3.20%"}


@pytest.mark.asyncio
async def test_finviz_provider_get_analyst_data(finviz_provider):
    provider, _ = finviz_provider
    result = await provider.get_analyst_data("AAPL")
    assert result == {"Target Price": "180", "Recom": "1.8"}


@pytest.mark.asyncio
async def test_finviz_provider_get_news(finviz_provider):
    provider, _ = finviz_provider
    result = await provider.get_news("AAPL")
    assert len(result) == 1
    assert result[0]["title"] == "Good news"


@pytest.mark.asyncio
async def test_finviz_provider_caches_scrape(finviz_provider):
    """Calling multiple get_* methods should only scrape once."""
    provider, scraper = finviz_provider
    await provider.get_fundamentals("AAPL")
    await provider.get_technicals("AAPL")
    await provider.get_analyst_data("AAPL")
    await provider.get_news("AAPL")
    # Only one scrape call despite four method calls
    scraper.scrape.assert_awaited_once_with("AAPL")


@pytest.mark.asyncio
async def test_finviz_provider_clear_cache(finviz_provider):
    provider, scraper = finviz_provider
    await provider.get_fundamentals("AAPL")
    provider.clear_cache("AAPL")
    await provider.get_fundamentals("AAPL")
    assert scraper.scrape.await_count == 2


@pytest.mark.asyncio
async def test_finviz_provider_close(finviz_provider):
    provider, scraper = finviz_provider
    await provider.close()
    scraper.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_finviz_provider_handles_missing_keys():
    """If scrape returns incomplete data, get_* should return empty dict/list."""
    mock_scraper = AsyncMock()
    mock_scraper.scrape.return_value = {"all_data": {}}
    mock_scraper.close = AsyncMock()
    provider = FinvizDataProvider(mock_scraper)

    assert await provider.get_fundamentals("AAPL") == {}
    assert await provider.get_technicals("AAPL") == {}
    assert await provider.get_analyst_data("AAPL") == {}
    assert await provider.get_news("AAPL") == []


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------


def test_finviz_provider_is_data_provider():
    mock_scraper = AsyncMock()
    mock_scraper.close = AsyncMock()
    provider = FinvizDataProvider(mock_scraper)
    assert isinstance(provider, DataProvider)
