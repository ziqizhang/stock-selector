import pytest
from unittest.mock import patch
from src.scrapers.yfinance_provider import YFinanceProvider
from src.scrapers.investegate import InvestegateScraper


class TestDynamicUKSymbolResolution:
    """Test dynamic UK symbol resolution via yfinance Search API."""

    @pytest.mark.asyncio
    async def test_search_hsbc_resolution_with_uk_preference(self):
        """Test HSBC resolves via search to HSBA.L when UK is preferred."""
        provider = YFinanceProvider()

        with patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("HSBA.L", {"regularMarketPrice": 1300})

            resolved, market = provider.resolve_symbol("HSBC", preferred_market="UK")
            assert resolved == "HSBA.L"
            assert market == "UK"
            mock_search.assert_called_once_with("HSBC", "LSE")

    @pytest.mark.asyncio
    async def test_search_bp_resolution_with_uk_preference(self):
        """Test BP resolves via search to BP.L when UK is preferred."""
        provider = YFinanceProvider()

        with patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("BP.L", {"regularMarketPrice": 400})

            resolved, market = provider.resolve_symbol("BP", preferred_market="UK")
            assert resolved == "BP.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_us_preference_prioritizes_us_symbols(self):
        """Test that without UK preference, US symbols are tried first."""
        provider = YFinanceProvider()

        with patch.object(provider, '_probe_symbol') as mock_probe:
            mock_probe.return_value = {"regularMarketPrice": 90}

            resolved, market = provider.resolve_symbol("HSBC")
            assert resolved == "HSBC"
            assert market == "US"

    @pytest.mark.asyncio
    async def test_fallback_to_uk_search_when_us_fails(self):
        """Test fallback to UK search when US symbol fails."""
        provider = YFinanceProvider()

        with patch.object(provider, '_probe_symbol', return_value=None), \
             patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("UNKNOWN.L", {"regularMarketPrice": 50})

            resolved, market = provider.resolve_symbol("UNKNOWN")
            assert resolved == "UNKNOWN.L"
            assert market == "UK"
            mock_search.assert_called_once_with("UNKNOWN", "LSE")

    @pytest.mark.asyncio
    async def test_search_returns_first_lse_match(self):
        """Test that search picks the first LSE result."""
        provider = YFinanceProvider()

        with patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("VOD.L", {"regularMarketPrice": 80})

            resolved, market = provider.resolve_symbol("VOD", preferred_market="UK")
            assert resolved == "VOD.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_symbol_resolution_caching_with_search(self):
        """Test symbol resolution caching works with search-based resolution."""
        provider = YFinanceProvider()

        with patch.object(provider, '_search_symbol') as mock_search:
            mock_search.return_value = ("TEST.L", {"regularMarketPrice": 50})

            resolved1, market1 = provider.resolve_symbol("TEST", preferred_market="UK")
            resolved2, market2 = provider.resolve_symbol("TEST", preferred_market="UK")

            assert mock_search.call_count == 1
            assert resolved1 == resolved2 == "TEST.L"
            assert market1 == market2 == "UK"

    @pytest.mark.asyncio
    async def test_investegate_updated_link_pattern(self):
        """Test Investegate scraper uses updated /announcement/ pattern."""
        scraper = InvestegateScraper()

        mock_html = '''
        <html>
            <body>
                <a href="/announcement/rns/hsbc-holdings--hsba/holding-s-in-company/123456">
                    HSBC Holdings: Holding(s) in Company
                </a>
                <a href="/announcement/rns/bp-plc--bp/directorate-change/123457">
                    BP plc: Directorate change
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
        assert len(result["insider_trades"]) >= 1

    @pytest.mark.asyncio
    async def test_error_when_nothing_found(self):
        """Test ValueError when no US or UK match is found."""
        provider = YFinanceProvider()

        with patch.object(provider, '_probe_symbol', return_value=None), \
             patch.object(provider, '_search_symbol', return_value=None):
            with pytest.raises(ValueError, match="Ticker 'NOSUCH' not found"):
                provider.resolve_symbol("NOSUCH", preferred_market="UK")
