import pytest
import pytest_asyncio
from src.db import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_add_and_list_tickers(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    tickers = await db.list_tickers()
    assert len(tickers) == 1
    assert tickers[0]["symbol"] == "AAPL"
    assert tickers[0]["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_remove_ticker(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.remove_ticker("AAPL")
    tickers = await db.list_tickers()
    assert len(tickers) == 0


@pytest.mark.asyncio
async def test_save_and_get_analysis(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.save_analysis(
        symbol="AAPL",
        category="fundamentals",
        score=7.5,
        confidence="high",
        narrative="Strong earnings growth.",
        raw_data='{"pe": 28.5}',
    )
    analyses = await db.get_analyses("AAPL")
    assert len(analyses) == 1
    assert analyses[0]["category"] == "fundamentals"
    assert analyses[0]["score"] == 7.5


@pytest.mark.asyncio
async def test_save_and_get_synthesis(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.save_synthesis(
        symbol="AAPL",
        overall_score=6.2,
        recommendation="buy",
        narrative="Overall bullish outlook.",
        signal_scores='{"fundamentals": 7.5}',
    )
    synthesis = await db.get_latest_synthesis("AAPL")
    assert synthesis["recommendation"] == "buy"
    assert synthesis["overall_score"] == 6.2
