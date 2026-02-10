import pytest
from unittest.mock import AsyncMock, patch
from src.scrapers.news import NewsScraper

SAMPLE_RSS = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>AAPL stock - Google News</title>
    <item>
      <title>Apple stock rises on earnings beat</title>
      <source url="https://reuters.com">Reuters</source>
      <description>Apple Inc. reported better-than-expected earnings.</description>
    </item>
    <item>
      <title>Tech sector rally continues</title>
      <source url="https://bloomberg.com">Bloomberg</source>
      <description>Technology stocks continued their upward trend.</description>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_NO_SOURCE = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>TEST stock - Google News</title>
    <item>
      <title>Headline without source</title>
      <description>A snippet here.</description>
    </item>
  </channel>
</rss>"""

SAMPLE_RSS_EMPTY = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>EMPTY - Google News</title>
  </channel>
</rss>"""


@pytest.mark.asyncio
async def test_news_scraper_parses_rss_articles():
    scraper = NewsScraper()
    with patch.object(scraper, "fetch", new_callable=AsyncMock, return_value=SAMPLE_RSS):
        result = await scraper.scrape("AAPL")

    assert "news_articles" in result
    articles = result["news_articles"]
    assert len(articles) == 2
    assert articles[0]["title"] == "Apple stock rises on earnings beat"
    assert articles[0]["source"] == "Reuters"
    assert articles[0]["snippet"] == "Apple Inc. reported better-than-expected earnings."
    assert articles[1]["title"] == "Tech sector rally continues"
    assert articles[1]["source"] == "Bloomberg"
    await scraper.close()


@pytest.mark.asyncio
async def test_news_scraper_missing_source_element():
    scraper = NewsScraper()
    with patch.object(scraper, "fetch", new_callable=AsyncMock, return_value=SAMPLE_RSS_NO_SOURCE):
        result = await scraper.scrape("TEST")

    articles = result["news_articles"]
    assert len(articles) == 1
    assert articles[0]["title"] == "Headline without source"
    assert articles[0]["source"] == ""
    assert articles[0]["snippet"] == "A snippet here."
    await scraper.close()


@pytest.mark.asyncio
async def test_news_scraper_empty_feed():
    scraper = NewsScraper()
    with patch.object(scraper, "fetch", new_callable=AsyncMock, return_value=SAMPLE_RSS_EMPTY):
        result = await scraper.scrape("EMPTY")

    assert result == {"news_articles": []}
    await scraper.close()


@pytest.mark.asyncio
async def test_news_scraper_builds_correct_url():
    scraper = NewsScraper()
    with patch.object(scraper, "fetch", new_callable=AsyncMock, return_value=SAMPLE_RSS_EMPTY) as mock_fetch:
        await scraper.scrape("MSFT")

    mock_fetch.assert_called_once_with(
        "https://news.google.com/rss/search?q=MSFT+stock&hl=en-US&gl=US&ceid=US:en"
    )
    await scraper.close()
