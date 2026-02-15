"""Tests for the backtest module."""

import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from src.db import Database
from src.analysis.backtest import run_backtest, _is_correct, HORIZONS, BacktestSummary


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.get_historical_price = AsyncMock()
    provider.close = AsyncMock()
    return provider


# ---------------------------------------------------------------------------
# Unit tests for _is_correct
# ---------------------------------------------------------------------------

class TestIsCorrect:
    def test_buy_price_up(self):
        assert _is_correct("buy", 5.0) is True

    def test_buy_price_down(self):
        assert _is_correct("buy", -3.0) is False

    def test_sell_price_down(self):
        assert _is_correct("sell", -5.0) is True

    def test_sell_price_up(self):
        assert _is_correct("sell", 3.0) is False

    def test_hold_within_range(self):
        assert _is_correct("hold", 2.0) is True

    def test_hold_at_boundary(self):
        assert _is_correct("hold", 5.0) is True

    def test_hold_outside_range(self):
        assert _is_correct("hold", 6.0) is False

    def test_hold_negative_within_range(self):
        assert _is_correct("hold", -4.0) is True

    def test_hold_negative_outside_range(self):
        assert _is_correct("hold", -7.0) is False


# ---------------------------------------------------------------------------
# Integration tests for run_backtest
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_backtest_empty(db, mock_provider):
    """No recommendations → empty summary."""
    summary = await run_backtest(db, mock_provider)
    assert summary.total == 0
    assert summary.results == []
    for h in HORIZONS:
        assert summary.hit_rates[h]["total"] == 0


@pytest.mark.asyncio
async def test_backtest_no_price_at_rec(db, mock_provider):
    """Recommendations without price_at_rec are skipped."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.save_recommendation("AAPL", "buy", 5.0, price_at_rec=None)

    summary = await run_backtest(db, mock_provider)
    assert summary.total == 0


@pytest.mark.asyncio
async def test_backtest_future_horizon(db, mock_provider):
    """Recommendations too recent for any horizon produce no outcomes."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.save_recommendation("AAPL", "buy", 5.0, price_at_rec=150.0)

    # The rec was just created (now), so no horizon has elapsed
    summary = await run_backtest(db, mock_provider)
    # Result exists but has no outcomes
    assert summary.total == 1
    assert summary.results[0].outcomes == {}


@pytest.mark.asyncio
async def test_backtest_buy_correct(db, mock_provider):
    """A buy recommendation where price went up is correct."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")

    # Insert a recommendation dated 60 days ago
    old_date = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    await db.db.execute(
        """INSERT INTO recommendations (symbol, recommendation, overall_score, price_at_rec, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("AAPL", "buy", 6.0, 100.0, old_date),
    )
    await db.db.commit()

    # 30-day horizon should trigger; price went up
    mock_provider.get_historical_price.return_value = 110.0

    summary = await run_backtest(db, mock_provider)
    assert summary.total == 1
    result = summary.results[0]
    assert 30 in result.outcomes
    assert result.outcomes[30]["correct"] is True
    assert result.outcomes[30]["pct_change"] == 10.0

    assert summary.hit_rates[30]["total"] == 1
    assert summary.hit_rates[30]["correct"] == 1
    assert summary.hit_rates[30]["rate"] == 100.0


@pytest.mark.asyncio
async def test_backtest_sell_correct(db, mock_provider):
    """A sell recommendation where price went down is correct."""
    await db.add_ticker("MSFT", "Microsoft Corp.", "Technology")

    old_date = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    await db.db.execute(
        """INSERT INTO recommendations (symbol, recommendation, overall_score, price_at_rec, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("MSFT", "sell", -5.0, 200.0, old_date),
    )
    await db.db.commit()

    mock_provider.get_historical_price.return_value = 180.0

    summary = await run_backtest(db, mock_provider)
    result = summary.results[0]
    assert 30 in result.outcomes
    assert result.outcomes[30]["correct"] is True
    assert result.outcomes[30]["pct_change"] == -10.0


@pytest.mark.asyncio
async def test_backtest_buy_incorrect(db, mock_provider):
    """A buy recommendation where price went down is incorrect."""
    await db.add_ticker("TSLA", "Tesla Inc.", "Automotive")

    old_date = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    await db.db.execute(
        """INSERT INTO recommendations (symbol, recommendation, overall_score, price_at_rec, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("TSLA", "buy", 4.0, 250.0, old_date),
    )
    await db.db.commit()

    mock_provider.get_historical_price.return_value = 230.0

    summary = await run_backtest(db, mock_provider)
    result = summary.results[0]
    assert 30 in result.outcomes
    assert result.outcomes[30]["correct"] is False


@pytest.mark.asyncio
async def test_backtest_multiple_horizons(db, mock_provider):
    """A recommendation old enough triggers multiple horizons."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")

    old_date = (datetime.utcnow() - timedelta(days=200)).strftime("%Y-%m-%d %H:%M:%S")
    await db.db.execute(
        """INSERT INTO recommendations (symbol, recommendation, overall_score, price_at_rec, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("AAPL", "buy", 7.0, 100.0, old_date),
    )
    await db.db.commit()

    # Price goes up at all horizons
    mock_provider.get_historical_price.return_value = 120.0

    summary = await run_backtest(db, mock_provider)
    result = summary.results[0]
    # All 3 horizons should be present
    assert 30 in result.outcomes
    assert 90 in result.outcomes
    assert 180 in result.outcomes
    for h in HORIZONS:
        assert summary.hit_rates[h]["total"] == 1
        assert summary.hit_rates[h]["correct"] == 1


@pytest.mark.asyncio
async def test_backtest_filter_by_symbol(db, mock_provider):
    """Filtering by symbol only returns that ticker's recommendations."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.add_ticker("MSFT", "Microsoft Corp.", "Technology")

    old_date = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    for sym in ("AAPL", "MSFT"):
        await db.db.execute(
            """INSERT INTO recommendations (symbol, recommendation, overall_score, price_at_rec, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (sym, "buy", 5.0, 100.0, old_date),
        )
    await db.db.commit()

    mock_provider.get_historical_price.return_value = 110.0

    summary = await run_backtest(db, mock_provider, symbol="AAPL")
    assert summary.total == 1
    assert summary.results[0].symbol == "AAPL"


@pytest.mark.asyncio
async def test_backtest_missing_historical_price(db, mock_provider):
    """If provider returns None for a horizon, that outcome is skipped."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")

    old_date = (datetime.utcnow() - timedelta(days=60)).strftime("%Y-%m-%d %H:%M:%S")
    await db.db.execute(
        """INSERT INTO recommendations (symbol, recommendation, overall_score, price_at_rec, created_at)
           VALUES (?, ?, ?, ?, ?)""",
        ("AAPL", "buy", 5.0, 100.0, old_date),
    )
    await db.db.commit()

    mock_provider.get_historical_price.return_value = None

    summary = await run_backtest(db, mock_provider)
    assert summary.total == 1
    assert summary.results[0].outcomes == {}
    assert summary.hit_rates[30]["total"] == 0


@pytest.mark.asyncio
async def test_db_save_and_get_recommendations(db):
    """Test DB methods for saving and retrieving recommendations."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.save_recommendation("AAPL", "buy", 6.5, price_at_rec=150.0)

    recs = await db.get_recommendations(symbol="AAPL")
    assert len(recs) == 1
    assert recs[0]["symbol"] == "AAPL"
    assert recs[0]["recommendation"] == "buy"
    assert recs[0]["overall_score"] == 6.5
    assert recs[0]["price_at_rec"] == 150.0


@pytest.mark.asyncio
async def test_db_get_recommendations_all(db):
    """get_recommendations with no symbol returns all."""
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.add_ticker("MSFT", "Microsoft Corp.", "Technology")
    await db.save_recommendation("AAPL", "buy", 5.0, price_at_rec=100.0)
    await db.save_recommendation("MSFT", "hold", 1.0, price_at_rec=200.0)

    recs = await db.get_recommendations()
    assert len(recs) == 2
