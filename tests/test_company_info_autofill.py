"""Tests for company name auto-fill functionality."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from src.api.routes import app


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_yfinance():
    """Mock the yfinance provider."""
    with patch("src.api.routes.yfinance_provider") as mock:
        mock.resolve_symbol = MagicMock(return_value=("AAPL", "US"))
        mock.get_sector_info = AsyncMock(return_value={
            "sector": "Technology",
            "sector_key": "technology",
            "industry": "Consumer Electronics",
            "industry_key": "consumer-electronics",
        })
        yield mock


class TestCompanyInfoEndpoint:
    """Test the /api/company-info/{symbol} endpoint."""

    def test_get_company_info_success(self, client, mock_yfinance):
        """Test successful company info retrieval."""
        # Arrange
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "longName": "Apple Inc.",
            "shortName": "Apple",
            "sector": "Technology",
            "industry": "Consumer Electronics",
        }
        mock_yfinance._get_ticker = MagicMock(return_value=mock_ticker)
        mock_yfinance.resolve_symbol = MagicMock(return_value=("AAPL", "US"))

        # Act
        response = client.get("/api/company-info/AAPL?market=US")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "AAPL"
        assert data["name"] == "Apple Inc."
        assert data["sector"] == "Technology"
        assert data["industry"] == "Consumer Electronics"
        assert data["market"] == "US"

    def test_get_company_info_uses_short_name_fallback(self, client, mock_yfinance):
        """Test that shortName is used when longName is not available."""
        # Arrange
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "shortName": "Apple",
            "sector": "Technology",
        }
        mock_yfinance._get_ticker = MagicMock(return_value=mock_ticker)
        mock_yfinance.resolve_symbol = MagicMock(return_value=("AAPL", "US"))

        # Act
        response = client.get("/api/company-info/AAPL")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Apple"

    def test_get_company_info_uk_ticker(self, client, mock_yfinance):
        """Test company info for UK ticker."""
        # Arrange
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "longName": "HSBC Holdings plc",
            "sector": "Financial Services",
            "industry": "Banks - Diversified",
        }
        mock_yfinance._get_ticker = MagicMock(return_value=mock_ticker)
        mock_yfinance.resolve_symbol = MagicMock(return_value=("HSBA.L", "UK"))
        mock_yfinance.get_sector_info = AsyncMock(return_value={
            "sector": "Financial Services",
            "industry": "Banks - Diversified",
        })

        # Act
        response = client.get("/api/company-info/HSBC?market=UK")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "HSBC"
        assert data["resolved_symbol"] == "HSBA.L"
        assert data["name"] == "HSBC Holdings plc"
        assert data["market"] == "UK"

    def test_get_company_info_empty_response(self, client, mock_yfinance):
        """Test handling when yfinance returns empty info."""
        # Arrange
        mock_ticker = MagicMock()
        mock_ticker.info = {}
        mock_yfinance._get_ticker = MagicMock(return_value=mock_ticker)
        mock_yfinance.resolve_symbol = MagicMock(return_value=("UNKNOWN", "US"))
        mock_yfinance.get_sector_info = AsyncMock(return_value={
            "sector": None,
            "industry": None,
        })

        # Act
        response = client.get("/api/company-info/UNKNOWN")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "UNKNOWN"
        assert data["name"] == ""
        assert data["sector"] is None

    def test_get_company_info_exception_handling(self, client, mock_yfinance):
        """Test that exceptions are handled gracefully."""
        # Arrange
        mock_yfinance.resolve_symbol = MagicMock(side_effect=Exception("Network error"))

        # Act
        response = client.get("/api/company-info/ERROR")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["symbol"] == "ERROR"
        assert data["name"] == ""
        assert "error" in data


class TestCompanyInfoVariousSymbols:
    """Test company info for various stock symbols."""

    @pytest.mark.parametrize("symbol,expected_name,expected_sector", [
        ("MSFT", "Microsoft Corporation", "Technology"),
        ("JPM", "JPMorgan Chase & Co.", "Financial Services"),
        ("XOM", "Exxon Mobil Corporation", "Energy"),
        ("JNJ", "Johnson & Johnson", "Healthcare"),
        ("BA", "The Boeing Company", "Industrials"),
        ("TSLA", "Tesla, Inc.", "Consumer Cyclical"),
        ("KO", "The Coca-Cola Company", "Consumer Defensive"),
    ])
    def test_various_company_symbols(self, client, mock_yfinance, symbol, expected_name, expected_sector):
        """Test company info retrieval for various symbols."""
        # Arrange
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "longName": expected_name,
            "sector": expected_sector,
        }
        mock_yfinance._get_ticker = MagicMock(return_value=mock_ticker)
        mock_yfinance.resolve_symbol = MagicMock(return_value=(symbol, "US"))
        mock_yfinance.get_sector_info = AsyncMock(return_value={
            "sector": expected_sector,
            "industry": "Test Industry",
        })

        # Act
        response = client.get(f"/api/company-info/{symbol}")

        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == expected_name
        assert data["sector"] == expected_sector
