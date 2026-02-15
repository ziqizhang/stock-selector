"""Insider trades fetcher using Financial Modeling Prep (FMP) API.

Replaces OpenInsider (US) and Investegate (UK) HTML scraping.
Requires FMP_API_KEY env var. Free tier supports insider trading endpoint.
"""

import logging
import os

import httpx

logger = logging.getLogger(__name__)

FMP_BASE_URL = "https://financialmodelingprep.com/api/v4"


class FMPInsiderFetcher:
    """Fetch insider trades via FMP API. Requires FMP_API_KEY env var."""

    def __init__(self):
        self._api_key = os.environ.get("FMP_API_KEY", "")
        self._client = httpx.AsyncClient(timeout=15.0)

    @property
    def available(self) -> bool:
        return bool(self._api_key)

    async def fetch_insider_trades(self, symbol: str) -> dict:
        """Fetch insider trades for a symbol. Returns same shape as OpenInsiderScraper.scrape()."""
        # FMP uses bare symbols (strip .L suffix for UK)
        bare = symbol.replace(".L", "")
        url = f"{FMP_BASE_URL}/insider-trading"
        params = {
            "symbol": bare,
            "apikey": self._api_key,
            "page": 0,
        }
        response = await self._client.get(url, params=params)
        response.raise_for_status()
        data = response.json()

        trades = []
        for item in data if isinstance(data, list) else []:
            trades.append({
                "filing_date": item.get("filingDate", ""),
                "trade_date": item.get("transactionDate", ""),
                "ticker": item.get("symbol", bare),
                "insider_name": item.get("reportingName", ""),
                "title": item.get("typeOfOwner", ""),
                "trade_type": _map_transaction_type(item.get("transactionType", "")),
                "price": str(item.get("price", "")),
                "qty": str(item.get("securitiesTransacted", "")),
                "owned": str(item.get("securitiesOwned", "")),
                "change_pct": "",
                "value": _calc_value(item),
            })
        return {"insider_trades": trades}

    async def close(self):
        await self._client.aclose()


def _calc_value(item: dict) -> str:
    """Calculate trade value from price * quantity, tolerating bad data."""
    if not item.get("price") or not item.get("securitiesTransacted"):
        return ""
    try:
        value = str(round(float(item.get("price", 0)) * float(item.get("securitiesTransacted", 0))))
    except (ValueError, TypeError):
        value = ""
    return value


def _map_transaction_type(fmp_type: str) -> str:
    """Map FMP transaction type codes to human-readable labels."""
    mapping = {
        "P-Purchase": "Purchase",
        "S-Sale": "Sale",
        "A-Award": "Award",
        "M-Exempt": "Exercise",
    }
    return mapping.get(fmp_type, fmp_type)
