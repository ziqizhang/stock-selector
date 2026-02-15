"""Tests for the engine's API-first-with-scraper-fallback logic."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock

from src.analysis.engine import AnalysisEngine
from src.analysis.llm_base import LLMProvider
from src.db import Database


def _make_signal(score=5.0, confidence="high", narrative="Test."):
    return {"score": score, "confidence": confidence, "narrative": narrative}


def _make_synthesis(overall_score=6.5, recommendation="buy"):
    return {
        "overall_score": overall_score,
        "recommendation": recommendation,
        "narrative": "Synthesis.",
        "entry_strategy": "",
    }


class MockLLM(LLMProvider):
    def __init__(self):
        self.calls = []
        self._idx = 0

    async def analyze(self, prompt: str) -> dict:
        self.calls.append(prompt)
        self._idx += 1
        if self._idx <= 7:
            return _make_signal()
        return _make_synthesis()


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


def _setup_engine(db):
    provider = AsyncMock()
    provider.get_fundamentals = AsyncMock(return_value={"pe": 25})
    provider.get_technicals = AsyncMock(return_value={"rsi": 55})
    provider.get_analyst_data = AsyncMock(return_value={"target": 150})
    provider.get_news = AsyncMock(return_value=[{"title": "News"}])
    provider.close = AsyncMock()

    eng = AnalysisEngine(db, data_provider=provider)
    eng.llm = MockLLM()

    # Mock all scrapers
    eng.openinsider = AsyncMock()
    eng.openinsider.scrape = AsyncMock(return_value={"insider_trades": []})
    eng.openinsider.close = AsyncMock()
    eng.investegate = AsyncMock()
    eng.investegate.scrape = AsyncMock(return_value={"insider_trades": []})
    eng.investegate.close = AsyncMock()
    eng.news = AsyncMock()
    eng.news.scrape = AsyncMock(return_value={"news_articles": [{"title": "Fallback"}]})
    eng.news.close = AsyncMock()
    eng.sector = AsyncMock()
    eng.sector.scrape = AsyncMock(return_value={"sector_performance": []})
    eng.sector.close = AsyncMock()

    # Mock API fetchers
    eng.newsapi = AsyncMock()
    eng.newsapi.close = AsyncMock()
    eng.fmp_insider = AsyncMock()
    eng.fmp_insider.close = AsyncMock()

    return eng


async def _collect(engine, symbol):
    events = []
    async for p in engine.analyze_ticker(symbol):
        events.append(p)
    return events


@pytest.mark.asyncio
async def test_newsapi_used_when_available(db):
    eng = _setup_engine(db)
    eng.newsapi.available = True
    eng.newsapi.fetch_news = AsyncMock(return_value={"news_articles": [{"title": "API News"}]})
    eng.fmp_insider.available = False

    await db.add_ticker("AAPL", "Apple", "Technology")
    await _collect(eng, "AAPL")

    eng.newsapi.fetch_news.assert_called_once()
    eng.news.scrape.assert_not_called()


@pytest.mark.asyncio
async def test_news_scraper_fallback_when_no_key(db):
    eng = _setup_engine(db)
    eng.newsapi.available = False
    eng.fmp_insider.available = False

    await db.add_ticker("AAPL", "Apple", "Technology")
    await _collect(eng, "AAPL")

    eng.news.scrape.assert_called_once()


@pytest.mark.asyncio
async def test_news_scraper_fallback_on_api_error(db):
    eng = _setup_engine(db)
    eng.newsapi.available = True
    eng.newsapi.fetch_news = AsyncMock(side_effect=RuntimeError("API down"))
    eng.fmp_insider.available = False

    await db.add_ticker("AAPL", "Apple", "Technology")
    await _collect(eng, "AAPL")

    eng.newsapi.fetch_news.assert_called_once()
    eng.news.scrape.assert_called_once()


@pytest.mark.asyncio
async def test_fmp_insider_used_when_available(db):
    eng = _setup_engine(db)
    eng.newsapi.available = False
    eng.fmp_insider.available = True
    eng.fmp_insider.fetch_insider_trades = AsyncMock(return_value={"insider_trades": [{"ticker": "AAPL"}]})

    await db.add_ticker("AAPL", "Apple", "Technology")
    await _collect(eng, "AAPL")

    eng.fmp_insider.fetch_insider_trades.assert_called_once()
    eng.openinsider.scrape.assert_not_called()
    eng.investegate.scrape.assert_not_called()


@pytest.mark.asyncio
async def test_insider_scraper_fallback_when_no_key(db):
    eng = _setup_engine(db)
    eng.newsapi.available = False
    eng.fmp_insider.available = False

    await db.add_ticker("AAPL", "Apple", "Technology")
    await _collect(eng, "AAPL")

    eng.openinsider.scrape.assert_called_once()
    eng.investegate.scrape.assert_not_called()


@pytest.mark.asyncio
async def test_insider_scraper_fallback_on_api_error(db):
    eng = _setup_engine(db)
    eng.newsapi.available = False
    eng.fmp_insider.available = True
    eng.fmp_insider.fetch_insider_trades = AsyncMock(side_effect=RuntimeError("FMP down"))

    await db.add_ticker("AAPL", "Apple", "Technology")
    await _collect(eng, "AAPL")

    eng.fmp_insider.fetch_insider_trades.assert_called_once()
    eng.openinsider.scrape.assert_called_once()


@pytest.mark.asyncio
async def test_uk_ticker_falls_back_to_investegate(db):
    eng = _setup_engine(db)
    eng.newsapi.available = False
    eng.fmp_insider.available = False

    await db.add_ticker("VOD", "Vodafone", "Telecom", market="UK")
    await _collect(eng, "VOD")

    eng.investegate.scrape.assert_called_once()
    eng.openinsider.scrape.assert_not_called()


@pytest.mark.asyncio
async def test_fmp_used_for_uk_ticker_too(db):
    """FMP API works for both US and UK tickers (strips .L internally)."""
    eng = _setup_engine(db)
    eng.newsapi.available = False
    eng.fmp_insider.available = True
    eng.fmp_insider.fetch_insider_trades = AsyncMock(return_value={"insider_trades": []})

    await db.add_ticker("VOD", "Vodafone", "Telecom", market="UK")
    await _collect(eng, "VOD")

    eng.fmp_insider.fetch_insider_trades.assert_called_once()
    eng.investegate.scrape.assert_not_called()
    eng.openinsider.scrape.assert_not_called()
