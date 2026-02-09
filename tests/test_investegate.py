import pytest
from src.scrapers.investegate import InvestegateScraper


LISTING_HTML = """
<html><body>
<table>
  <tr>
    <td>09 Feb 2026</td>
    <td>VOD</td>
    <td>Vodafone Group</td>
    <td><a href="/Article.aspx?id=12345">Director Purchase - VOD</a></td>
  </tr>
  <tr>
    <td>08 Feb 2026</td>
    <td>BP</td>
    <td>BP plc</td>
    <td><a href="/Article.aspx?id=99999">Director Sale - BP</a></td>
  </tr>
  <tr>
    <td>07 Feb 2026</td>
    <td>VOD</td>
    <td>Vodafone Group</td>
    <td><a href="/Article.aspx?id=12346">Director Sale - VOD</a></td>
  </tr>
</table>
</body></html>
"""

DETAIL_HTML = """
<html><body>
<h1>Director/PDMR Shareholding</h1>
<p>Director: John Smith</p>
<p>Nature of transaction: Purchase</p>
<p>Number of shares: 50,000</p>
<p>Price per share: £1.25</p>
<p>Aggregate value: £62,500</p>
</body></html>
"""

DETAIL_HTML_MINIMAL = """
<html><body>
<h1>Director Dealings</h1>
<p>Some unstructured RNS announcement text about director dealings.</p>
</body></html>
"""


@pytest.mark.asyncio
async def test_scrape_returns_matching_trades(httpx_mock):
    """scrape('VOD') should return insider trades for VOD only, not BP."""
    httpx_mock.add_response(
        url=InvestegateScraper.LISTING_URL,
        text=LISTING_HTML,
    )
    httpx_mock.add_response(
        url="https://www.investegate.co.uk/Article.aspx?id=12345",
        text=DETAIL_HTML,
    )
    httpx_mock.add_response(
        url="https://www.investegate.co.uk/Article.aspx?id=12346",
        text=DETAIL_HTML_MINIMAL,
    )

    scraper = InvestegateScraper()
    result = await scraper.scrape("VOD")

    assert "insider_trades" in result
    trades = result["insider_trades"]
    assert len(trades) == 2

    # First trade should have structured data parsed
    assert trades[0]["insider_name"] == "John Smith"
    assert trades[0]["trade_type"] == "Purchase"
    assert trades[0]["qty"] == "50,000"
    assert trades[0]["price"] == "£1.25"
    assert trades[0]["value"] == "£62,500"

    # Second trade from minimal page falls back to empty fields
    assert trades[1]["insider_name"] == ""
    assert trades[1]["headline"] == "Director Sale - VOD"

    await scraper.close()


@pytest.mark.asyncio
async def test_scrape_strips_l_suffix(httpx_mock):
    """scrape('VOD.L') should search for 'VOD' on Investegate."""
    httpx_mock.add_response(
        url=InvestegateScraper.LISTING_URL,
        text=LISTING_HTML,
    )
    httpx_mock.add_response(
        url="https://www.investegate.co.uk/Article.aspx?id=12345",
        text=DETAIL_HTML,
    )
    httpx_mock.add_response(
        url="https://www.investegate.co.uk/Article.aspx?id=12346",
        text=DETAIL_HTML_MINIMAL,
    )

    scraper = InvestegateScraper()
    result = await scraper.scrape("VOD.L")

    assert len(result["insider_trades"]) == 2
    await scraper.close()


@pytest.mark.asyncio
async def test_scrape_no_matches_returns_empty(httpx_mock):
    """scrape('XYZ') should return empty list when no matching rows."""
    httpx_mock.add_response(
        url=InvestegateScraper.LISTING_URL,
        text=LISTING_HTML,
    )

    scraper = InvestegateScraper()
    result = await scraper.scrape("XYZ")

    assert result == {"insider_trades": []}
    await scraper.close()
