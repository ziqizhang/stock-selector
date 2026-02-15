import json
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from src.analysis.engine import AnalysisEngine, create_llm_provider
from src.analysis.llm_base import LLMProvider
from src.analysis.claude import ClaudeCLI
from src.analysis.codex import CodexCLI
from src.analysis.opencode import OpencodeCLI
from src.db import Database
from src.models import RefreshProgress


def _make_signal(score=5.0, confidence="high", narrative="Test analysis."):
    return {"score": score, "confidence": confidence, "narrative": narrative}


def _make_synthesis(overall_score=6.5, recommendation="buy"):
    return {
        "overall_score": overall_score,
        "recommendation": recommendation,
        "narrative": "Synthesis narrative.",
        "entry_strategy": "Buy at $100.",
    }


class MockLLM(LLMProvider):
    """Mock LLM that returns canned results in sequence."""

    def __init__(self, results=None):
        self.calls = []
        self._results = list(results or [])
        self._idx = 0

    async def analyze(self, prompt: str) -> dict:
        self.calls.append(prompt)
        if self._idx < len(self._results):
            result = self._results[self._idx]
        else:
            result = _make_signal()
        self._idx += 1
        return result


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


def _mock_provider():
    provider = AsyncMock()
    provider.get_fundamentals = AsyncMock(return_value={"pe_ratio": 25})
    provider.get_technicals = AsyncMock(return_value={"rsi": 55})
    provider.get_analyst_data = AsyncMock(return_value={"target": 150})
    provider.get_news = AsyncMock(return_value=[{"title": "News"}])
    provider.get_current_price = AsyncMock(return_value=150.0)
    provider.close = AsyncMock()
    return provider


def _mock_scrapers(engine):
    """Replace real scrapers with mocks."""
    engine.openinsider = AsyncMock()
    engine.openinsider.scrape = AsyncMock(return_value={"insider_trades": []})
    engine.openinsider.close = AsyncMock()

    engine.investegate = AsyncMock()
    engine.investegate.scrape = AsyncMock(return_value={"director_dealings": []})
    engine.investegate.close = AsyncMock()

    engine.news = AsyncMock()
    engine.news.scrape = AsyncMock(return_value={"news_articles": [{"title": "Test"}]})
    engine.news.close = AsyncMock()

    engine.sector = AsyncMock()
    engine.sector.scrape = AsyncMock(return_value={"sector_performance": []})
    engine.sector.close = AsyncMock()


@pytest_asyncio.fixture
async def engine(db):
    provider = _mock_provider()
    eng = AnalysisEngine(db, data_provider=provider)
    eng.llm = MockLLM([_make_signal()] * 7 + [_make_synthesis()])
    _mock_scrapers(eng)
    yield eng


async def _collect(engine, symbol):
    events = []
    async for progress in engine.analyze_ticker(symbol):
        events.append(progress)
    return events


# --- create_llm_provider factory tests ---

def test_create_llm_provider_claude():
    assert isinstance(create_llm_provider("claude"), ClaudeCLI)


def test_create_llm_provider_codex():
    assert isinstance(create_llm_provider("codex"), CodexCLI)


def test_create_llm_provider_opencode():
    assert isinstance(create_llm_provider("opencode"), OpencodeCLI)


def test_create_llm_provider_invalid():
    with pytest.raises(ValueError, match="opencode"):
        create_llm_provider("invalid")


# --- Happy path tests ---

@pytest.mark.asyncio
async def test_us_ticker_full_pipeline(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology", market="US")
    events = await _collect(engine, "AAPL")

    assert events[-1].done is True
    assert events[-1].step == "Complete"
    # 5 categories + sector + risk + synthesis = 8 LLM calls
    assert len(engine.llm.calls) == 8

    engine.openinsider.scrape.assert_called_once()
    engine.investegate.scrape.assert_not_called()

    synthesis = await db.get_latest_synthesis("AAPL")
    assert synthesis is not None
    assert synthesis["recommendation"] == "buy"
    assert synthesis["overall_score"] == 6.5


@pytest.mark.asyncio
async def test_uk_ticker_routes_to_investegate(db, engine):
    await db.add_ticker("VOD", "Vodafone", "Telecom", market="UK")
    events = await _collect(engine, "VOD")

    assert events[-1].done is True
    engine.investegate.scrape.assert_called_once()
    engine.openinsider.scrape.assert_not_called()


@pytest.mark.asyncio
async def test_ticker_not_found(db, engine):
    events = await _collect(engine, "NONEXIST")
    assert len(events) == 1
    assert events[0].done is True
    assert events[0].step == "error"


# --- Scraper failure tests ---

@pytest.mark.asyncio
async def test_news_scraper_failure_graceful(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    engine.news.scrape = AsyncMock(side_effect=RuntimeError("News down"))

    events = await _collect(engine, "AAPL")
    assert events[-1].done is True
    assert events[-1].step == "Complete"


@pytest.mark.asyncio
async def test_insider_scraper_failure_graceful(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    engine.openinsider.scrape = AsyncMock(side_effect=RuntimeError("Insider down"))

    events = await _collect(engine, "AAPL")
    assert events[-1].done is True


# --- LLM edge cases ---

@pytest.mark.asyncio
async def test_llm_parse_error_still_completes(db, engine):
    error_result = {"narrative": "could not parse", "parse_error": True, "score": 0, "confidence": "low"}
    engine.llm = MockLLM(
        [error_result] * 7
        + [{"overall_score": 0, "recommendation": "hold", "narrative": ""}]
    )
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")

    events = await _collect(engine, "AAPL")
    assert events[-1].done is True
    synthesis = await db.get_latest_synthesis("AAPL")
    assert synthesis is not None
    assert synthesis["recommendation"] == "hold"


@pytest.mark.asyncio
async def test_synthesis_fallback_to_weighted_score(db, engine):
    signal = _make_signal(score=5.0)
    # Synthesis without overall_score → should use weighted_score fallback
    synthesis_no_score = {"narrative": "Synthesis", "recommendation": "buy"}
    engine.llm = MockLLM([signal] * 7 + [synthesis_no_score])

    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    events = await _collect(engine, "AAPL")

    assert events[-1].done is True
    synthesis = await db.get_latest_synthesis("AAPL")
    # weighted_score of all 5.0 scores = 5.0
    assert synthesis["overall_score"] == 5.0
    assert synthesis["recommendation"] == "buy"


@pytest.mark.asyncio
async def test_synthesis_entry_strategy_appended(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    events = await _collect(engine, "AAPL")

    synthesis = await db.get_latest_synthesis("AAPL")
    assert "## Entry Strategy" in synthesis["narrative"]
    assert "Buy at $100." in synthesis["narrative"]


# --- Progress events ---

@pytest.mark.asyncio
async def test_progress_events_cover_all_steps(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    events = await _collect(engine, "AAPL")

    steps = [e.step for e in events]
    assert "Fetching market data..." in steps
    assert "Scraping insider data..." in steps
    assert "Scraping news..." in steps
    assert "Scraping sector data..." in steps
    assert "Generating overall recommendation..." in steps
    assert "Complete" in steps
    assert any("Analyzing" in s for s in steps)


# --- LLM caching tests ---

@pytest.mark.asyncio
async def test_cache_hit_skips_llm_calls(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")

    # First run — all 8 LLM calls
    events = await _collect(engine, "AAPL")
    assert events[-1].done is True
    assert len(engine.llm.calls) == 8

    # Second run with fresh MockLLM — signals should be cached
    engine.llm = MockLLM([_make_synthesis()])
    events = await _collect(engine, "AAPL")
    assert events[-1].done is True
    # Only synthesis should call LLM (cached 7 signals)
    assert len(engine.llm.calls) == 1

    steps = [e.step for e in events]
    assert any("Using cached" in s for s in steps)


@pytest.mark.asyncio
async def test_cache_miss_when_data_changes(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")

    # First run
    await _collect(engine, "AAPL")

    # Change fundamentals data → cache miss for fundamentals + risk
    engine.data_provider.get_fundamentals = AsyncMock(return_value={"pe_ratio": 30})
    engine.llm = MockLLM([_make_signal()] * 7 + [_make_synthesis()])

    events = await _collect(engine, "AAPL")
    assert events[-1].done is True
    # fundamentals miss + risk miss (all_scraped changed) + synthesis = 3 LLM calls
    assert len(engine.llm.calls) == 3


@pytest.mark.asyncio
async def test_cached_analysis_stored_with_hash(db, engine):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await _collect(engine, "AAPL")

    analyses = await db.get_analyses("AAPL")
    # All 7 signal analyses should have input_hash set
    for a in analyses:
        assert a["input_hash"] is not None
        assert len(a["input_hash"]) == 64  # SHA-256 hex digest
