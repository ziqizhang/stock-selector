import os
import pytest
from unittest.mock import patch

from src.scrapers.fmp_insider import FMPInsiderFetcher, _map_transaction_type

SAMPLE_RESPONSE = [
    {
        "symbol": "AAPL",
        "filingDate": "2026-02-10",
        "transactionDate": "2026-02-08",
        "reportingName": "Tim Cook",
        "typeOfOwner": "officer",
        "transactionType": "S-Sale",
        "price": 185.50,
        "securitiesTransacted": 10000,
        "securitiesOwned": 500000,
    },
    {
        "symbol": "AAPL",
        "filingDate": "2026-02-05",
        "transactionDate": "2026-02-03",
        "reportingName": "Luca Maestri",
        "typeOfOwner": "officer",
        "transactionType": "P-Purchase",
        "price": 180.00,
        "securitiesTransacted": 5000,
        "securitiesOwned": 100000,
    },
]


@pytest.mark.asyncio
async def test_available_when_key_set():
    with patch.dict(os.environ, {"FMP_API_KEY": "test-key"}):
        fetcher = FMPInsiderFetcher()
        assert fetcher.available is True
        await fetcher.close()


@pytest.mark.asyncio
async def test_not_available_when_no_key():
    env = os.environ.copy()
    env.pop("FMP_API_KEY", None)
    with patch.dict(os.environ, env, clear=True):
        fetcher = FMPInsiderFetcher()
        assert fetcher.available is False
        await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_insider_trades(httpx_mock):
    with patch.dict(os.environ, {"FMP_API_KEY": "test-key"}):
        fetcher = FMPInsiderFetcher()

    httpx_mock.add_response(json=SAMPLE_RESPONSE)
    result = await fetcher.fetch_insider_trades("AAPL")

    assert "insider_trades" in result
    trades = result["insider_trades"]
    assert len(trades) == 2

    assert trades[0]["filing_date"] == "2026-02-10"
    assert trades[0]["trade_date"] == "2026-02-08"
    assert trades[0]["insider_name"] == "Tim Cook"
    assert trades[0]["trade_type"] == "Sale"
    assert trades[0]["price"] == "185.5"
    assert trades[0]["qty"] == "10000"
    assert trades[0]["value"] == "1855000"

    assert trades[1]["trade_type"] == "Purchase"
    assert trades[1]["insider_name"] == "Luca Maestri"
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_insider_strips_l_suffix(httpx_mock):
    with patch.dict(os.environ, {"FMP_API_KEY": "test-key"}):
        fetcher = FMPInsiderFetcher()

    httpx_mock.add_response(json=[])
    result = await fetcher.fetch_insider_trades("VOD.L")

    assert result == {"insider_trades": []}
    # Verify the request used bare symbol
    request = httpx_mock.get_requests()[0]
    assert "symbol=VOD" in str(request.url)
    assert ".L" not in str(request.url)
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_insider_empty_response(httpx_mock):
    with patch.dict(os.environ, {"FMP_API_KEY": "test-key"}):
        fetcher = FMPInsiderFetcher()

    httpx_mock.add_response(json=[])
    result = await fetcher.fetch_insider_trades("XYZ")

    assert result == {"insider_trades": []}
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_insider_error_response(httpx_mock):
    """Non-list response (e.g. error object) returns empty trades."""
    with patch.dict(os.environ, {"FMP_API_KEY": "test-key"}):
        fetcher = FMPInsiderFetcher()

    httpx_mock.add_response(json={"Error Message": "Invalid API KEY"})
    result = await fetcher.fetch_insider_trades("AAPL")

    assert result == {"insider_trades": []}
    await fetcher.close()


@pytest.mark.asyncio
async def test_fetch_insider_http_error(httpx_mock):
    with patch.dict(os.environ, {"FMP_API_KEY": "bad-key"}):
        fetcher = FMPInsiderFetcher()

    httpx_mock.add_response(status_code=403)

    with pytest.raises(Exception):
        await fetcher.fetch_insider_trades("AAPL")
    await fetcher.close()


def test_map_transaction_type():
    assert _map_transaction_type("P-Purchase") == "Purchase"
    assert _map_transaction_type("S-Sale") == "Sale"
    assert _map_transaction_type("A-Award") == "Award"
    assert _map_transaction_type("M-Exempt") == "Exercise"
    assert _map_transaction_type("Unknown") == "Unknown"
