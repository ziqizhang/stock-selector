import pytest
from unittest.mock import patch
from src.scrapers.yfinance_provider import YFinanceProvider


class TestYFinanceSymbolResolution:
    """Test symbol resolution for UK tickers via yfinance Search API."""

    @pytest.fixture
    def provider(self):
        return YFinanceProvider()

    @pytest.mark.asyncio
    async def test_bp_symbol_resolution(self, provider):
        """Test BP resolves via search when bare symbol fails."""
        with patch.object(provider, '_probe_symbol', return_value=None), \
             patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("BP.L", {"regularMarketPrice": 400})

            resolved, market = provider.resolve_symbol("BP")
            assert resolved == "BP.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_hsbc_search_resolution(self, provider):
        """Test HSBC resolves to HSBA.L via search."""
        with patch.object(provider, '_probe_symbol', return_value=None), \
             patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("HSBA.L", {"regularMarketPrice": 500})

            resolved, market = provider.resolve_symbol("HSBC")
            assert resolved == "HSBA.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_relx_search_resolution(self, provider):
        """Test RELX resolves to REL.L via search."""
        with patch.object(provider, '_probe_symbol', return_value=None), \
             patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("REL.L", {"regularMarketPrice": 2000})

            resolved, market = provider.resolve_symbol("RELX")
            assert resolved == "REL.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_us_ticker_unchanged(self, provider):
        """Test US tickers work as normal."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            mock_probe.return_value = {"regularMarketPrice": 150}

            resolved, market = provider.resolve_symbol("AAPL")
            assert resolved == "AAPL"
            assert market == "US"

    @pytest.mark.asyncio
    async def test_existing_lse_symbol_unchanged(self, provider):
        """Test existing .L symbols work as normal."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            mock_probe.return_value = {"regularMarketPrice": 80}

            resolved, market = provider.resolve_symbol("VOD.L")
            assert resolved == "VOD.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_symbol_not_found_error(self, provider):
        """Test ValueError when symbol not found."""
        with patch.object(provider, '_probe_symbol', return_value=None), \
             patch.object(provider, '_search_symbol', return_value=None):
            with pytest.raises(ValueError, match="Ticker 'UNKNOWN' not found"):
                provider.resolve_symbol("UNKNOWN")

    @pytest.mark.asyncio
    async def test_cached_resolution(self, provider):
        """Test symbol resolution is cached."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            mock_probe.return_value = {"regularMarketPrice": 100}

            resolved1, market1 = provider.resolve_symbol("BP")
            resolved2, market2 = provider.resolve_symbol("BP")

            assert mock_probe.call_count == 1
            assert resolved1 == resolved2
            assert market1 == market2
