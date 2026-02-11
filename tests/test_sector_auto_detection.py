"""Tests for sector auto-detection functionality."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from src.api.routes import app
from src.scrapers.yfinance_provider import YFinanceProvider


@pytest.fixture
def client():
    """Create a test client."""
    return TestClient(app)


@pytest.fixture
def mock_db():
    """Mock the database."""
    with patch("src.api.routes.db") as mock:
        mock.add_ticker = AsyncMock()
        mock.init = AsyncMock()
        mock.close = AsyncMock()
        yield mock


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


class TestSectorDetectionIntegration:
    """Integration tests for sector detection via API endpoints."""

    def test_add_ticker_endpoint_auto_detects_sector(self, client, mock_db, mock_yfinance):
        """Test the /tickers endpoint auto-detects sector when not provided."""
        # Arrange
        mock_yfinance.resolve_symbol.return_value = ("AAPL", "US")
        mock_yfinance.get_sector_info.return_value = {
            "sector": "Technology",
            "sector_key": "technology",
            "industry": "Consumer Electronics",
            "industry_key": "consumer-electronics",
        }

        # Act
        response = client.post("/tickers", data={
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "US",
        }, follow_redirects=False)

        # Assert
        assert response.status_code == 303
        assert response.headers["location"] == "/"
        mock_db.add_ticker.assert_called_once()
        call_args = mock_db.add_ticker.call_args
        assert call_args.args[0] == "AAPL"  # symbol
        assert call_args.args[1] == "Apple Inc."  # name
        assert call_args.args[2] == "Technology"  # auto-detected sector
        assert call_args.kwargs["market"] == "US"
        assert call_args.kwargs["resolved_symbol"] == "AAPL"

    def test_add_ticker_endpoint_respects_user_sector(self, client, mock_db, mock_yfinance):
        """Test the /tickers endpoint uses user-provided sector when available."""
        # Arrange
        mock_yfinance.resolve_symbol.return_value = ("AAPL", "US")

        # Act - with user-provided sector
        response = client.post("/tickers", data={
            "symbol": "AAPL",
            "name": "Apple Inc.",
            "market": "US",
            "sector": "Healthcare",  # User override
        }, follow_redirects=False)

        # Assert
        assert response.status_code == 303
        mock_yfinance.get_sector_info.assert_not_called()  # Should not auto-detect
        mock_db.add_ticker.assert_called_once()
        call_args = mock_db.add_ticker.call_args
        assert call_args.args[2] == "Healthcare"  # user-provided sector

    def test_add_ticker_endpoint_uk_market(self, client, mock_db, mock_yfinance):
        """Test the /tickers endpoint with UK market auto-detection."""
        # Arrange
        mock_yfinance.resolve_symbol.return_value = ("HSBA.L", "UK")
        mock_yfinance.get_sector_info.return_value = {
            "sector": "Financial Services",
            "sector_key": "financial-services",
            "industry": "Banks - Diversified",
            "industry_key": "banks-diversified",
        }

        # Act
        response = client.post("/tickers", data={
            "symbol": "HSBC",
            "name": "HSBC Holdings",
            "market": "UK",
        }, follow_redirects=False)

        # Assert
        assert response.status_code == 303
        mock_db.add_ticker.assert_called_once()
        call_args = mock_db.add_ticker.call_args
        assert call_args.args[2] == "Financial Services"  # auto-detected sector
        assert call_args.kwargs["market"] == "UK"
        assert call_args.kwargs["resolved_symbol"] == "HSBA.L"

    def test_add_ticker_endpoint_fallback_when_detection_fails(self, client, mock_db, mock_yfinance):
        """Test that None sector is stored when auto-detection fails."""
        # Arrange
        mock_yfinance.resolve_symbol.return_value = ("UNKNOWN", "US")
        mock_yfinance.get_sector_info.return_value = {
            "sector": None,
            "sector_key": None,
            "industry": None,
            "industry_key": None,
        }

        # Act
        response = client.post("/tickers", data={
            "symbol": "UNKNOWN",
            "name": "Unknown Company",
            "market": "US",
        }, follow_redirects=False)

        # Assert
        assert response.status_code == 303
        mock_db.add_ticker.assert_called_once()
        call_args = mock_db.add_ticker.call_args
        assert call_args.args[2] is None  # sector should be None

    def test_add_ticker_endpoint_various_sectors(self, client, mock_db, mock_yfinance):
        """Test detection of various sectors via endpoint."""
        test_cases = [
            ("MSFT", "Microsoft", "Technology"),
            ("JPM", "JPMorgan", "Financial Services"),
            ("XOM", "Exxon Mobil", "Energy"),
            ("JNJ", "Johnson & Johnson", "Healthcare"),
            ("BA", "Boeing", "Industrials"),
            ("TSLA", "Tesla", "Consumer Cyclical"),
            ("KO", "Coca-Cola", "Consumer Defensive"),
        ]

        for symbol, name, expected_sector in test_cases:
            # Reset mocks
            mock_db.reset_mock()
            mock_yfinance.reset_mock()
            
            # Arrange
            mock_yfinance.resolve_symbol.return_value = (symbol, "US")
            mock_yfinance.get_sector_info.return_value = {
                "sector": expected_sector,
                "sector_key": expected_sector.lower().replace(" ", "-"),
                "industry": "Test Industry",
                "industry_key": "test-industry",
            }

            # Act
            response = client.post("/tickers", data={
                "symbol": symbol,
                "name": name,
                "market": "US",
            }, follow_redirects=False)

            # Assert
            assert response.status_code == 303, f"Failed for {symbol}"
            mock_db.add_ticker.assert_called_once()
            call_args = mock_db.add_ticker.call_args
            assert call_args.kwargs["resolved_symbol"] == symbol


class TestYFinanceProviderSectorInfo:
    """Test YFinanceProvider.get_sector_info method."""

    @pytest.mark.asyncio
    async def test_get_sector_info_success(self):
        """Test successful sector info retrieval."""
        # Arrange
        provider = YFinanceProvider()
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "sector": "Technology",
            "sectorKey": "technology",
            "industry": "Software - Infrastructure",
            "industryKey": "software-infrastructure",
        }
        
        with patch.object(provider, "_get_ticker", return_value=mock_ticker):
            # Act
            result = await provider.get_sector_info("MSFT")

        # Assert
        assert result["sector"] == "Technology"
        assert result["sector_key"] == "technology"
        assert result["industry"] == "Software - Infrastructure"
        assert result["industry_key"] == "software-infrastructure"

    @pytest.mark.asyncio
    async def test_get_sector_info_missing_data(self):
        """Test sector info when data is missing."""
        # Arrange
        provider = YFinanceProvider()
        mock_ticker = MagicMock()
        mock_ticker.info = {}  # Empty info
        
        with patch.object(provider, "_get_ticker", return_value=mock_ticker):
            # Act
            result = await provider.get_sector_info("UNKNOWN")

        # Assert
        assert result["sector"] is None
        assert result["sector_key"] is None
        assert result["industry"] is None
        assert result["industry_key"] is None

    @pytest.mark.asyncio
    async def test_get_sector_info_exception_handling(self):
        """Test that exceptions are handled gracefully."""
        # Arrange
        provider = YFinanceProvider()
        
        with patch.object(provider, "_get_ticker", side_effect=Exception("Network error")):
            # Act
            result = await provider.get_sector_info("ERROR")

        # Assert
        assert result["sector"] is None
        assert result["sector_key"] is None
        assert result["industry"] is None
        assert result["industry_key"] is None

    @pytest.mark.asyncio
    async def test_get_sector_info_uk_ticker(self):
        """Test sector info for UK ticker."""
        # Arrange
        provider = YFinanceProvider()
        mock_ticker = MagicMock()
        mock_ticker.info = {
            "sector": "Financial Services",
            "sectorKey": "financial-services",
            "industry": "Banks - Diversified",
            "industryKey": "banks-diversified",
        }
        
        with patch.object(provider, "_get_ticker", return_value=mock_ticker):
            # Act
            result = await provider.get_sector_info("HSBA.L")

        # Assert
        assert result["sector"] == "Financial Services"
        assert result["sector_key"] == "financial-services"

    @pytest.mark.asyncio
    async def test_get_sector_info_various_stocks(self):
        """Test sector detection for various stock symbols."""
        test_cases = [
            ("AAPL", "Technology", "Consumer Electronics"),
            ("MSFT", "Technology", "Software"),
            ("JPM", "Financial Services", "Banks"),
            ("XOM", "Energy", "Oil & Gas"),
            ("JNJ", "Healthcare", "Pharmaceuticals"),
            ("BA", "Industrials", "Aerospace & Defense"),
            ("TSLA", "Consumer Cyclical", "Auto Manufacturers"),
            ("KO", "Consumer Defensive", "Beverages"),
        ]

        for symbol, expected_sector, expected_industry in test_cases:
            # Arrange
            provider = YFinanceProvider()
            mock_ticker = MagicMock()
            mock_ticker.info = {
                "sector": expected_sector,
                "sectorKey": expected_sector.lower().replace(" ", "-"),
                "industry": expected_industry,
                "industryKey": expected_industry.lower().replace(" ", "-").replace("&", "and"),
            }
            
            with patch.object(provider, "_get_ticker", return_value=mock_ticker):
                # Act
                result = await provider.get_sector_info(symbol)

            # Assert
            assert result["sector"] == expected_sector, f"Wrong sector for {symbol}"
            assert result["industry"] == expected_industry, f"Wrong industry for {symbol}"
