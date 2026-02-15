import json
import os
import pytest
from unittest.mock import AsyncMock, patch

from src.scrapers.newsapi import NewsAPIFetcher, NEWS_API_URL

SAMPLE_RESPONSE = {
    "status": "ok",
    "totalResults": 2,
    "articles": [
        {
            "title": "Apple stock rises on earnings beat",
            "source": {"id": "reuters", "name": "Reuters"},
            "description": "Apple Inc. reported better-than-expected earnings.",
            "url": "https://reuters.com/article/1",
        },
        {
            "title": "Tech sector rally continues",
            "source": {"id": "bloomberg", "name": "Bloomberg"},
            "description": "Technology stocks continued their upward trend.",
            "url": "https://bloomberg.com/article/2",
        },
    ],
}


@pytest.mark.asyncio
async def test_available_when_key_set():
    with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
        fetcher = NewsAPIFetcher()
        assert fetcher.available is True
        await fetcher.close()


@pytest.mark.asyncio
async def test_not_available_when_no_key():
    with patch.dict(os.environ, {}, clear=True):
        env = os.environ.copy()
        env.pop("NEWS_API_KEY", None)
        with patch.dict(os.environ, env, clear=True):
            fetcher = NewsAPIFetcher()
            assert fetcher.available is False
            await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_news_parses_articles(httpx_mock):
    with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
        fetcher = NewsAPIFetcher()

    httpx_mock.add_response(json=SAMPLE_RESPONSE)
    result = await fetcher.fetch_news("AAPL")

    assert "news_articles" in result
    articles = result["news_articles"]
    assert len(articles) == 2
    assert articles[0]["title"] == "Apple stock rises on earnings beat"
    assert articles[0]["source"] == "Reuters"
    assert articles[0]["snippet"] == "Apple Inc. reported better-than-expected earnings."
    assert articles[1]["source"] == "Bloomberg"
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_news_empty_response(httpx_mock):
    with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
        fetcher = NewsAPIFetcher()

    httpx_mock.add_response(json={"status": "ok", "totalResults": 0, "articles": []})
    result = await fetcher.fetch_news("XYZ")

    assert result == {"news_articles": []}
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_news_missing_description(httpx_mock):
    with patch.dict(os.environ, {"NEWS_API_KEY": "test-key"}):
        fetcher = NewsAPIFetcher()

    httpx_mock.add_response(json={
        "status": "ok",
        "articles": [
            {"title": "No desc article", "source": {"name": "CNN"}, "description": None},
        ],
    })
    result = await fetcher.fetch_news("AAPL")

    assert result["news_articles"][0]["snippet"] == ""
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_news_http_error(httpx_mock):
    with patch.dict(os.environ, {"NEWS_API_KEY": "bad-key"}):
        fetcher = NewsAPIFetcher()

    httpx_mock.add_response(status_code=401)

    with pytest.raises(Exception):
        await fetcher.fetch_news("AAPL")
    await fetcher.close()
