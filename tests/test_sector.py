import re

import pytest
from src.scrapers.sector import SectorScraper, SECTOR_ETFS, UK_SECTOR_ETFS


FINVIZ_HTML = """
<html><body>
<table class="groups_table">
  <tr><th>No.</th><th>Sector</th><th>Stocks</th><th>Market Cap</th><th>Perf Week</th></tr>
  <tr><td>1</td><td>Technology</td><td>500</td><td>10T</td><td>2.5%</td></tr>
</table>
</body></html>
"""

NEWS_HTML = """
<html><body>
<div class="SoaBEf"><div class="MBeuO">Tech stocks rally on AI hype</div></div>
</body></html>
"""

GOOGLE_NEWS_PATTERN = re.compile(r"https://www\.google\.com/search\?q=.*&tbm=nws.*")


@pytest.mark.asyncio
async def test_scrape_us_market_default(httpx_mock):
    """US market (default) should fetch FinViz and return US ETF."""
    httpx_mock.add_response(
        url="https://finviz.com/groups.ashx?g=sector&v=110&o=-perf1w",
        text=FINVIZ_HTML,
    )
    httpx_mock.add_response(
        url=GOOGLE_NEWS_PATTERN,
        text=NEWS_HTML,
    )

    scraper = SectorScraper()
    result = await scraper.scrape("AAPL", sector="Technology")

    assert result["sector_etf"] == "XLK"
    assert result["ticker_sector"] == "Technology"
    assert len(result["sector_performance"]) == 1
    assert result["sector_performance"][0]["name"] == "Technology"
    await scraper.close()


@pytest.mark.asyncio
async def test_scrape_us_market_explicit(httpx_mock):
    """Explicit market='US' should behave like default."""
    httpx_mock.add_response(
        url="https://finviz.com/groups.ashx?g=sector&v=110&o=-perf1w",
        text=FINVIZ_HTML,
    )
    httpx_mock.add_response(
        url=GOOGLE_NEWS_PATTERN,
        text=NEWS_HTML,
    )

    scraper = SectorScraper()
    result = await scraper.scrape("AAPL", sector="Technology", market="US")

    assert result["sector_etf"] == "XLK"
    await scraper.close()


@pytest.mark.asyncio
async def test_scrape_uk_market_skips_finviz(httpx_mock):
    """UK market should skip FinViz fetch and use UK ETFs."""
    httpx_mock.add_response(
        url=GOOGLE_NEWS_PATTERN,
        text=NEWS_HTML,
    )

    scraper = SectorScraper()
    result = await scraper.scrape("VOD.L", sector="Communication Services", market="UK")

    assert result["sector_etf"] == "IUCM.L"
    assert result["ticker_sector"] == "Communication Services"
    # No FinViz data for UK
    assert result["sector_performance"] == []

    # Verify no FinViz request was made
    urls = [str(req.url) for req in httpx_mock.get_requests()]
    assert not any("finviz.com" in url for url in urls)
    await scraper.close()


@pytest.mark.asyncio
async def test_scrape_uk_fallback_etf(httpx_mock):
    """UK market with unknown sector should fall back to ISF.L."""
    httpx_mock.add_response(
        url=GOOGLE_NEWS_PATTERN,
        text=NEWS_HTML,
    )

    scraper = SectorScraper()
    result = await scraper.scrape("VOD.L", sector="SomeUnknownSector", market="UK")

    assert result["sector_etf"] == "ISF.L"
    await scraper.close()


@pytest.mark.asyncio
async def test_scrape_us_fallback_etf(httpx_mock):
    """US market with no sector should fall back to SPY."""
    httpx_mock.add_response(
        url="https://finviz.com/groups.ashx?g=sector&v=110&o=-perf1w",
        text=FINVIZ_HTML,
    )
    httpx_mock.add_response(
        url=GOOGLE_NEWS_PATTERN,
        text=NEWS_HTML,
    )

    scraper = SectorScraper()
    result = await scraper.scrape("AAPL", sector=None, market="US")

    assert result["sector_etf"] == "SPY"
    await scraper.close()


@pytest.mark.asyncio
async def test_uk_sector_etfs_coverage():
    """All US sectors should have a UK ETF counterpart."""
    for sector in SECTOR_ETFS:
        assert sector in UK_SECTOR_ETFS, f"Missing UK ETF for sector: {sector}"
    for etf in UK_SECTOR_ETFS.values():
        assert etf.endswith(".L"), f"UK ETF {etf} should end with .L"
