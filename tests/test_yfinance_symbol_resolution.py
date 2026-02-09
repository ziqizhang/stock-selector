import pytest
from unittest.mock import patch, AsyncMock
from src.scrapers.yfinance_provider import YFinanceProvider, _UK_SYMBOL_MAPPINGS


class TestYFinanceSymbolResolution:
    """Test symbol resolution for UK tickers."""

    @pytest.fixture
    def provider(self):
        return YFinanceProvider()

    @pytest.mark.asyncio
    async def test_bp_symbol_resolution(self, provider):
        """Test BP resolves correctly."""
        # Mock the probe to return info for BP. but not BP or BP.L
        with patch.object(provider, '_probe_symbol') as mock_probe:
            # BP (no suffix) fails
            mock_probe.return_value = None
            # BP.L succeeds
            def probe_side_effect(symbol):
                if symbol == "BP.":
                    return {"regularMarketPrice": 100}  # Mock valid response
                return None
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("BP")
            assert resolved == "BP."
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_hsbc_mapping(self, provider):
        """Test HSBC maps to HSBA.L."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                if symbol == "HSBA.L":
                    return {"regularMarketPrice": 500}
                return None
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("HSBC")
            assert resolved == "HSBA.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_relx_mapping(self, provider):
        """Test RELX maps to REL.L."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                if symbol == "REL.L":
                    return {"regularMarketPrice": 2000}
                return None
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("RELX")
            assert resolved == "REL.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_us_ticker_unchanged(self, provider):
        """Test US tickers work as normal."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                if symbol == "AAPL":
                    return {"regularMarketPrice": 150}
                return None
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("AAPL")
            assert resolved == "AAPL"
            assert market == "US"

    @pytest.mark.asyncio
    async def test_existing_lse_symbol_unchanged(self, provider):
        """Test existing .L symbols work as normal."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                if symbol == "VOD.L":
                    return {"regularMarketPrice": 80}
                return None
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("VOD.L")
            assert resolved == "VOD.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_symbol_not_found_error(self, provider):
        """Test ValueError when symbol not found."""
        with patch.object(provider, '_probe_symbol', return_value=None):
            with pytest.raises(ValueError, match="Ticker 'UNKNOWN' not found"):
                provider.resolve_symbol("UNKNOWN")

    def test_uk_symbol_mappings_complete(self):
        """Verify the UK symbol mapping contains key stocks."""
        expected_mappings = {
            "HSBC": "HSBA.L",
            "BP": "BP.",
            "RELX": "REL.L",
            "LLOYDS": "LLOY.L",
            "BARC": "BARC.L",
            "SHEL": "SHEL.L",
            "GSK": "GSK.L",
            "AZN": "AZN.L",
        }
        for ticker, expected in expected_mappings.items():
            assert _UK_SYMBOL_MAPPINGS[ticker] == expected

    @pytest.mark.asyncio
    async def test_cached_resolution(self, provider):
        """Test symbol resolution is cached."""
        with patch.object(provider, '_probe_symbol') as mock_probe:
            mock_probe.return_value = {"regularMarketPrice": 100}

            # First call
            resolved1, market1 = provider.resolve_symbol("BP")
            # Second call should use cache
            resolved2, market2 = provider.resolve_symbol("BP")

            # Should only call probe once
            assert mock_probe.call_count == 1
            assert resolved1 == resolved2
            assert market1 == market2