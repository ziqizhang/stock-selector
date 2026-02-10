"""Tests for YFinanceProvider with mocked yfinance.Ticker."""

import pytest
import pandas as pd
import numpy as np
from unittest.mock import MagicMock, patch
from src.scrapers.yfinance_provider import YFinanceProvider, _fmt, _map_info


# ---------------------------------------------------------------------------
# Helper fixtures
# ---------------------------------------------------------------------------

def _make_info(**overrides):
    """Minimal yfinance .info dict for an AAPL-like ticker."""
    base = {
        "trailingPE": 28.5,
        "forwardPE": 25.0,
        "trailingEps": 6.5,
        "marketCap": 2_800_000_000_000,
        "currentPrice": 190.0,
        "previousClose": 188.0,
        "regularMarketPrice": 190.0,
        "beta": 1.2,
        "volume": 50_000_000,
        "averageDailyVolume10Day": 55_000_000,
        "fiftyTwoWeekHigh": 200.0,
        "fiftyTwoWeekLow": 140.0,
        "targetMeanPrice": 210.0,
        "recommendationMean": 1.8,
        "heldPercentInsiders": 0.05,
        "heldPercentInstitutions": 0.60,
        "shortRatio": 1.2,
        "numberOfAnalystOpinions": 35,
        "targetHighPrice": 250.0,
        "targetLowPrice": 170.0,
        "grossMargins": 0.44,
        "profitMargins": 0.26,
        "returnOnEquity": 0.15,
        "debtToEquity": 180.0,
        "dividendRate": 0.96,
    }
    base.update(overrides)
    return base


def _make_history(days=260):
    """Generate a synthetic 1-year price DataFrame."""
    dates = pd.date_range(end="2025-05-01", periods=days, freq="B")
    np.random.seed(42)
    close = 150 + np.cumsum(np.random.randn(days) * 0.5)
    high = close + np.abs(np.random.randn(days))
    low = close - np.abs(np.random.randn(days))
    return pd.DataFrame(
        {"Open": close, "High": high, "Low": low, "Close": close, "Volume": 50_000_000},
        index=dates,
    )


def _make_news():
    return [
        {"providerPublishTime": 1700000000, "title": "Apple beats earnings", "link": "https://example.com/a", "publisher": "Reuters"},
        {"providerPublishTime": 1700100000, "title": "Apple launches product", "link": "https://example.com/b", "publisher": "CNBC"},
    ]


@pytest.fixture
def provider():
    """YFinanceProvider with a mocked _get_ticker."""
    p = YFinanceProvider()
    mock_ticker = MagicMock()
    mock_ticker.info = _make_info()
    mock_ticker.history.return_value = _make_history()
    mock_ticker.news = _make_news()
    p._get_ticker = MagicMock(return_value=mock_ticker)
    return p


# ---------------------------------------------------------------------------
# _fmt / _map_info unit tests
# ---------------------------------------------------------------------------

def test_fmt_none():
    assert _fmt(None) == "-"


def test_fmt_percentage_float():
    assert _fmt(0.44) == "44.00%"


def test_fmt_large_float():
    assert _fmt(28.5) == "28.50"


def test_fmt_string():
    assert _fmt("hello") == "hello"


def test_map_info_basic():
    info = {"trailingPE": 28.5, "forwardPE": 25.0}
    mapping = {"trailingPE": "P/E", "forwardPE": "Forward P/E", "missing": "X"}
    result = _map_info(info, mapping)
    assert result["P/E"] == "28.50"
    assert result["Forward P/E"] == "25.00"
    assert "X" not in result


# ---------------------------------------------------------------------------
# get_fundamentals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_fundamentals_returns_mapped_keys(provider):
    result = await provider.get_fundamentals("AAPL")
    assert "P/E" in result
    assert "EPS (ttm)" in result
    assert "Market Cap" in result


@pytest.mark.asyncio
async def test_get_fundamentals_percentage_formatting(provider):
    result = await provider.get_fundamentals("AAPL")
    # grossMargins=0.44 → "44.00%"
    assert result["Gross Margin"] == "44.00%"


# ---------------------------------------------------------------------------
# get_technicals
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_technicals_has_price_and_indicators(provider):
    result = await provider.get_technicals("AAPL")
    assert "Price" in result
    assert "RSI (14)" in result
    assert "SMA20" in result
    assert "SMA50" in result
    assert "Beta" in result
    assert "52W High" in result


@pytest.mark.asyncio
async def test_get_technicals_rsi_in_valid_range(provider):
    result = await provider.get_technicals("AAPL")
    rsi_val = float(result["RSI (14)"])
    assert 0 <= rsi_val <= 100


@pytest.mark.asyncio
async def test_get_technicals_empty_history():
    """Provider should handle empty history gracefully."""
    p = YFinanceProvider()
    mock_ticker = MagicMock()
    mock_ticker.info = _make_info()
    mock_ticker.history.return_value = pd.DataFrame()
    mock_ticker.news = []
    p._get_ticker = MagicMock(return_value=mock_ticker)

    result = await p.get_technicals("AAPL")
    assert "Price" in result
    # Computed indicators should be absent
    assert "RSI (14)" not in result
    assert "SMA20" not in result


# ---------------------------------------------------------------------------
# get_analyst_data
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_analyst_data(provider):
    result = await provider.get_analyst_data("AAPL")
    assert "Target Price" in result
    assert "Recom" in result
    assert "Analyst Count" in result
    assert result["Analyst Count"] == "35"
    assert "Target High" in result
    assert "Target Low" in result


# ---------------------------------------------------------------------------
# get_news
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_news(provider):
    result = await provider.get_news("AAPL")
    assert len(result) == 2
    assert result[0]["title"] == "Apple beats earnings"
    assert result[0]["publisher"] == "Reuters"


@pytest.mark.asyncio
async def test_get_news_empty():
    p = YFinanceProvider()
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    mock_ticker.history.return_value = pd.DataFrame()
    mock_ticker.news = []
    p._get_ticker = MagicMock(return_value=mock_ticker)
    result = await p.get_news("AAPL")
    assert result == []


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_caches_per_symbol(provider):
    await provider.get_fundamentals("AAPL")
    await provider.get_technicals("AAPL")
    await provider.get_analyst_data("AAPL")
    # _get_ticker should only be called once
    assert provider._get_ticker.call_count == 1


@pytest.mark.asyncio
async def test_clear_cache(provider):
    await provider.get_fundamentals("AAPL")
    provider.clear_cache("AAPL")
    await provider.get_fundamentals("AAPL")
    assert provider._get_ticker.call_count == 2


# ---------------------------------------------------------------------------
# resolve_symbol
# ---------------------------------------------------------------------------

def test_resolve_symbol_us():
    p = YFinanceProvider()
    mock_ticker = MagicMock()
    mock_ticker.info = {"regularMarketPrice": 190.0}
    p._get_ticker = MagicMock(return_value=mock_ticker)

    resolved, market = p.resolve_symbol("AAPL")
    assert resolved == "AAPL"
    assert market == "US"


def test_resolve_symbol_uk_with_suffix():
    p = YFinanceProvider()
    mock_ticker = MagicMock()
    mock_ticker.info = {"regularMarketPrice": 650.0}
    p._get_ticker = MagicMock(return_value=mock_ticker)

    resolved, market = p.resolve_symbol("HSBA.L")
    assert resolved == "HSBA.L"
    assert market == "UK"


def test_resolve_symbol_uk_auto_suffix():
    """When bare symbol fails, yfinance Search should find the UK variant."""
    p = YFinanceProvider()

    # Bare symbol probe fails
    p._probe_symbol = lambda sym: None
    # Search finds HSBA.L on LSE
    p._search_symbol = lambda query, exchange: ("HSBA.L", {"regularMarketPrice": 650.0})

    resolved, market = p.resolve_symbol("HSBA")
    assert resolved == "HSBA.L"
    assert market == "UK"


def test_resolve_symbol_not_found():
    p = YFinanceProvider()
    mock_ticker = MagicMock()
    mock_ticker.info = {}
    p._get_ticker = MagicMock(return_value=mock_ticker)
    p._search_symbol = lambda query, exchange: None

    with pytest.raises(ValueError, match="not found"):
        p.resolve_symbol("XXXYYYZZZ")


def test_resolve_symbol_caches_result():
    p = YFinanceProvider()
    mock_ticker = MagicMock()
    mock_ticker.info = {"regularMarketPrice": 190.0}
    p._get_ticker = MagicMock(return_value=mock_ticker)

    p.resolve_symbol("AAPL")
    p.resolve_symbol("AAPL")  # second call should use cache
    # _probe_symbol calls _get_ticker; first resolve does 1 probe, second does 0
    assert p._get_ticker.call_count == 1


# ---------------------------------------------------------------------------
# Protocol conformance
# ---------------------------------------------------------------------------

def test_yfinance_provider_is_data_provider():
    from src.scrapers.provider import DataProvider
    p = YFinanceProvider()
    assert isinstance(p, DataProvider)
