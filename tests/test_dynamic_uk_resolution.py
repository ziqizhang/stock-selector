import pytest
from unittest.mock import patch, AsyncMock
from src.scrapers.yfinance_provider import YFinanceProvider, _UK_SUFFIX_PATTERNS, _UK_EXCEPTION_MAPPINGS
from src.scrapers.investegate import InvestegateScraper


class TestDynamicUKSymbolResolution:
    """Test dynamic UK symbol resolution without hardcoded mappings."""

    @pytest.mark.asyncio
    async def test_hybrid_hsbc_resolution_with_uk_preference(self):
        """Test HSBC resolves via exception mapping to HSBA.L when UK is preferred."""
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
    async def test_hybrid_bp_resolution_with_uk_preference(self):
        """Test BP resolves via exception mapping to BP. when UK is preferred."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "BP.": {"regularMarketPrice": 400},  # Exception mapping
                    "BP.L": None,  # Should fail
                    "BP": {"regularMarketPrice": 39},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("BP", preferred_market="UK")
            assert resolved == "BP."
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_dynamic_uk_patterns_tried_in_order(self):
        """Test UK patterns are tried in correct order for failing case."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            call_order = []
            
            def probe_side_effect(symbol):
                call_order.append(symbol)
                responses = {
                    "FAIL.L": None,  # First pattern should fail
                    "FAIL": None,    # Second pattern should fail
                    "FAIL.LN": {"regularMarketPrice": 50},  # Third pattern should succeed
                    "FAIL.": None,
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("FAIL", preferred_market="UK")
            assert resolved == "FAIL.LN"
            assert market == "UK"
            # Should try patterns in order: FAIL.L, FAIL, FAIL.LN, FAIL.
            assert call_order[:3] == ["FAIL.L", "FAIL", "FAIL.LN"]

    @pytest.mark.asyncio
    async def test_us_preference_prioritizes_us_symbols(self):
        """Test that without UK preference, US symbols are tried first."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "HSBC": {"regularMarketPrice": 90},  # US should be found first
                    "HSBA.L": {"regularMarketPrice": 1300},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("HSBC")
            assert resolved == "HSBC"
            assert market == "US"

    @pytest.mark.asyncio
    async def test_fallback_to_uk_when_us_fails(self):
        """Test fallback to UK patterns when US symbol fails."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "UNKNOWN": None,  # US symbol fails
                    "UNKNOWN.L": {"regularMarketPrice": 50},  # UK pattern succeeds
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("UNKNOWN")
            assert resolved == "UNKNOWN.L"
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_alternative_lse_suffix_works(self):
        """Test alternative LSE suffix (.LN) works."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "EXAMPLE.L": None,  # First pattern fails
                    "EXAMPLE": None,   # Second pattern fails  
                    "EXAMPLE.LN": {"regularMarketPrice": 100},  # Third pattern succeeds
                    "EXAMPLE.": None,  # Fourth pattern would fail
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("EXAMPLE", preferred_market="UK")
            assert resolved == "EXAMPLE.LN"
            assert market == "UK"

    def test_uk_suffix_patterns_completeness(self):
        """Verify UK suffix patterns include common variants."""
        expected_patterns = [".L", "", ".LN", "."]
        assert _UK_SUFFIX_PATTERNS == expected_patterns

    def test_uk_exception_mappings_completeness(self):
        """Verify critical UK symbols are in exception mappings."""
        critical_exceptions = {
            "HSBC": "HSBA.L",
            "BP": "BP.",
            "RELX": "REL.L",
            "LLOYDS": "LLOY.L",
            "SHEL": "SHEL.L",
        }
        
        for symbol, expected in critical_exceptions.items():
            assert _UK_EXCEPTION_MAPPINGS.get(symbol) == expected, f"Missing exception mapping for {symbol}"

    @pytest.mark.asyncio
    async def test_symbol_resolution_caching_with_patterns(self):
        """Test symbol resolution caching works with dynamic patterns."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "TEST.L": {"regularMarketPrice": 50},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            # First call should probe multiple patterns
            resolved1, market1 = provider.resolve_symbol("TEST", preferred_market="UK")
            # Second call should use cache
            resolved2, market2 = provider.resolve_symbol("TEST", preferred_market="UK")
            
            # Should only probe on first call, not second
            assert mock_probe.call_count <= 4  # Max 4 pattern attempts
            assert resolved1 == resolved2
            assert market1 == market2 == "UK"

    @pytest.mark.asyncio
    async def test_special_dot_handling(self):
        """Test special handling for symbols ending with dot."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol') as mock_probe:
            def probe_side_effect(symbol):
                responses = {
                    "BP.": {"regularMarketPrice": 400},
                    "BP.L": {"regularMarketPrice": 0},
                }
                return responses.get(symbol)
            mock_probe.side_effect = probe_side_effect

            resolved, market = provider.resolve_symbol("BP.", preferred_market="UK")
            assert resolved == "BP."
            assert market == "UK"

    @pytest.mark.asyncio
    async def test_investegate_updated_link_pattern(self):
        """Test Investegate scraper uses updated /announcement/ pattern."""
        scraper = InvestegateScraper()
        
        # Mock HTML response with new announcement pattern
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
        # Should find announcements with new /announcement/ pattern
        assert len(result["insider_trades"]) >= 1

    @pytest.mark.asyncio
    async def test_error_when_no_patterns_work(self):
        """Test ValueError when no UK or US patterns work."""
        provider = YFinanceProvider()
        
        with patch.object(provider, '_probe_symbol', return_value=None):
            with pytest.raises(ValueError, match="Ticker 'NOSUCH' not found"):
                provider.resolve_symbol("NOSUCH", preferred_market="UK")