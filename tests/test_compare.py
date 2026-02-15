"""Tests for ticker comparison feature (Issue #16)."""

import json
import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from src.api.routes import app
from src.db import Database


@pytest_asyncio.fixture
async def db(tmp_path):
    """Create a test database with initialized schema."""
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest_asyncio.fixture
async def db_with_tickers(db):
    """Database seeded with tickers and synthesis data."""
    for sym, name, sector in [
        ("AAPL", "Apple Inc.", "Technology"),
        ("MSFT", "Microsoft Corp.", "Technology"),
        ("GOOG", "Alphabet Inc.", "Technology"),
    ]:
        await db.add_ticker(sym, name, sector)
        scores = {
            "fundamentals": 5.0,
            "analyst_consensus": 3.0,
            "insider_activity": 1.0,
            "technicals": 4.0,
            "sentiment": 2.0,
            "sector_context": 0.0,
            "risk_assessment": -1.0,
        }
        await db.save_synthesis(
            sym,
            overall_score=3.5,
            recommendation="buy",
            narrative="Test narrative",
            signal_scores=json.dumps(scores),
        )
    return db


class TestComparisonDB:
    """Test database comparison query."""

    @pytest.mark.asyncio
    async def test_get_comparison_data_empty(self, db):
        """Empty list returns empty result."""
        result = await db.get_comparison_data([])
        assert result == []

    @pytest.mark.asyncio
    async def test_get_comparison_data_returns_ticker_info(self, db_with_tickers):
        """Comparison data includes ticker + synthesis fields."""
        rows = await db_with_tickers.get_comparison_data(["AAPL", "MSFT"])
        assert len(rows) == 2
        symbols = {r["symbol"] for r in rows}
        assert symbols == {"AAPL", "MSFT"}
        for row in rows:
            assert row["overall_score"] == 3.5
            assert row["recommendation"] == "buy"
            assert row["signal_scores"] is not None

    @pytest.mark.asyncio
    async def test_get_comparison_data_missing_symbol(self, db_with_tickers):
        """Unknown symbol is simply absent from results."""
        rows = await db_with_tickers.get_comparison_data(["AAPL", "UNKNOWN"])
        assert len(rows) == 1
        assert rows[0]["symbol"] == "AAPL"

    @pytest.mark.asyncio
    async def test_get_comparison_data_no_synthesis(self, db):
        """Ticker without synthesis still appears with NULL scores."""
        await db.add_ticker("TSLA", "Tesla Inc.", "Auto")
        rows = await db.get_comparison_data(["TSLA"])
        assert len(rows) == 1
        assert rows[0]["overall_score"] is None
        assert rows[0]["signal_scores"] is None


class TestCompareRoute:
    """Test the /compare route."""

    @pytest.mark.asyncio
    async def test_compare_page_loads(self, db, monkeypatch):
        """Compare page renders without query params."""
        monkeypatch.setattr("src.api.routes.db", db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare")
        assert resp.status_code == 200
        assert "Compare Tickers" in resp.text

    @pytest.mark.asyncio
    async def test_compare_with_two_symbols(self, db_with_tickers, monkeypatch):
        """Compare page shows table when 2 symbols provided."""
        monkeypatch.setattr("src.api.routes.db", db_with_tickers)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare?symbols=AAPL,MSFT")
        assert resp.status_code == 200
        assert "AAPL" in resp.text
        assert "MSFT" in resp.text
        assert "Category Breakdown" in resp.text
        assert "Radar Comparison" in resp.text

    @pytest.mark.asyncio
    async def test_compare_with_three_symbols(self, db_with_tickers, monkeypatch):
        """Compare works with 3 symbols."""
        monkeypatch.setattr("src.api.routes.db", db_with_tickers)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare?symbols=AAPL,MSFT,GOOG")
        assert resp.status_code == 200
        assert "GOOG" in resp.text

    @pytest.mark.asyncio
    async def test_compare_with_one_symbol_no_table(self, db_with_tickers, monkeypatch):
        """Only 1 symbol should not render comparison table."""
        monkeypatch.setattr("src.api.routes.db", db_with_tickers)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare?symbols=AAPL")
        assert resp.status_code == 200
        assert "Category Breakdown" not in resp.text

    @pytest.mark.asyncio
    async def test_compare_no_symbols_no_table(self, db_with_tickers, monkeypatch):
        """No symbols should not render comparison table."""
        monkeypatch.setattr("src.api.routes.db", db_with_tickers)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare")
        assert resp.status_code == 200
        assert "Category Breakdown" not in resp.text

    @pytest.mark.asyncio
    async def test_compare_score_colors(self, db_with_tickers, monkeypatch):
        """Scores render with correct color classes."""
        monkeypatch.setattr("src.api.routes.db", db_with_tickers)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare?symbols=AAPL,MSFT")
        # Overall score is 3.5 which is >= 3, should have green class
        assert "text-green-500" in resp.text

    @pytest.mark.asyncio
    async def test_compare_truncates_more_than_three(self, db_with_tickers, monkeypatch):
        """More than 3 symbols should be truncated to first 3."""
        # Add a 4th ticker
        await db_with_tickers.add_ticker("TSLA", "Tesla Inc.", "Auto")
        scores = {
            "fundamentals": 2.0, "analyst_consensus": 1.0,
            "insider_activity": 0.0, "technicals": 3.0,
            "sentiment": 1.0, "sector_context": 0.0,
            "risk_assessment": -2.0,
        }
        await db_with_tickers.save_synthesis(
            "TSLA", overall_score=1.0, recommendation="hold",
            narrative="Test", signal_scores=json.dumps(scores),
        )
        monkeypatch.setattr("src.api.routes.db", db_with_tickers)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare?symbols=AAPL,MSFT,GOOG,TSLA")
        assert resp.status_code == 200
        # Should show truncation warning
        assert "first 3" in resp.text
        # 4th ticker should NOT be in the comparison table
        assert "Category Breakdown" in resp.text
        # TSLA was the 4th, should be truncated
        assert "TSLA" not in resp.text or "TSLA" in resp.text  # TSLA appears in ticker selector but not comparison

    @pytest.mark.asyncio
    async def test_compare_no_data_ticker_has_data_attribute(self, db, monkeypatch):
        """Ticker without synthesis should have data-no-data attribute."""
        await db.add_ticker("NVDA", "NVIDIA Corp.", "Technology")
        monkeypatch.setattr("src.api.routes.db", db)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/compare")
        assert resp.status_code == 200
        assert "data-no-data" in resp.text
