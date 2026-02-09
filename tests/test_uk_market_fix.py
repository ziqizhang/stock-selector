import pytest
from unittest.mock import patch, AsyncMock
from src.scrapers.yfinance_provider import YFinanceProvider, _UK_SYMBOL_MAPPINGS
from src.scrapers.investegate import InvestegateScraper


class TestUKMarketFix:
    """Test comprehensive fix for UK market symbol resolution and Investegate scraping."""

    @pytest.mark.asyncio
    async def test_hsbc_resolves_to_uk_with_preference(self):
        """Test HSBC resolves to HSBA.L when UK is preferred."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "HSBA.L": {"regularMarketPrice": 1300},
                    "HSBC": {"regularMarketPrice": 90},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("HSBC", preferred_market="UK")
            assert resolved == "HSBA.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_bp_resolves_correctly_with_dot(self):
        """Test BP resolves to BP.L when UK is preferred."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "BP.L": {"regularMarketPrice": 400},
                    "BP": {"regularMarketPrice": 39},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("BP", preferred_market="UK")
            assert resolved == "BP.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_us_symbol_unchanged_when_no_preference(self):
        """Test US symbols work normally without market preference."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "AAPL": {"regularMarketPrice": 150},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("AAPL")
            assert resolved == "AAPL"
            assert market == "US"

    @pytest.mark.asyncio
    async def test_investegate_finds_hsbc_announcements(self):
        """Test Investegate scraper finds HSBC announcements."""
        scraper = InvestegateScraper()
        
        # Mock the HTML response to include HSBC announcement
        mock_html = '''
        <html>
            <body>
                <a href="/announcement/rns/hsbc-holdings--hsba/holding-s-in-company/123456">
                    HSBC Holdings: Holding(s) in Company
                </a>
            </body>
        </html>
        '''
        
        with patch.object(scraper, 'fetch', return_value=mock_html):
            with patch.object(scraper, '_parse_detail', return_value={
                "filing_date": "2024-01-15",
                "insider_name": "Test Director",
                "trade_type": "Buy",
                "qty": "1000",
                "price": "£7.50",
                "value": "£7500",
                "headline": "Test director purchase"
            }):
                result = await scraper.scrape("HSBA.L")
                
        assert "insider_trades" in result
        assert len(result["insider_trades"]) == 1
        trade = result["insider_trades"][0]
        assert trade["insider_name"] == "Test Director"
        assert trade["trade_type"] == "Buy"

    def test_uk_symbol_mapping_completeness(self):
        """Verify critical UK symbols are mapped correctly."""
        critical_mappings = {
            "HSBC": "HSBA.L",
            "BP": "BP.",
            "RELX": "REL.L",
            "LLOYDS": "LLOY.L",
            "BARC": "BARC.L",
            "SHEL": "SHEL.L",
            "GSK": "GSK.L",
            "AZN": "AZN.L",
            "DGE": "DGE.L",
            "ULVR": "ULVR.L",
        }
        
        for symbol, expected in critical_mappings.items():
            assert _UK_SYMBOL_MAPPINGS.get(symbol) == expected, f"Missing mapping for {symbol}"

    @pytest.mark.asyncio
    async def test_symbol_resolution_cache_works_with_preference(self):
        """Test symbol resolution caching works with preferred market."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "HSBA.L": {"regularMarketPrice": 1300},
                    "HSBC": {"regularMarketPrice": 90},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            # First call should probe
            resolved1, market1 = provider.resolve_symbol("HSBC", preferred_market="UK")
            # Second call should use cache
            resolved2, market2 = provider.resolve_symbol("HSBC", preferred_market="UK")
            
            # Should only call probe for the UK symbol, not US symbol
            assert mock_probe.call_count == 1
            assert resolved1 == resolved2 == "HSBA.L"
            assert market1 == market2 == "UK"

    @pytest.mark.asyncio
    async def test_fallback_to_us_when_uk_not_available(self):
        """Test fallback to US when UK symbol doesn't exist."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "UNKNOWN": {"regularMarketPrice": 50},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("UNKNOWN", preferred_market="UK")
            assert resolved == "UNKNOWN"
            assert market == "US"