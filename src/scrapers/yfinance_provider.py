"""DataProvider implementation backed by the yfinance library."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd
import yfinance as yf

from src.analysis.indicators import sma, rsi, atr, bollinger_bands

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Hybrid UK symbol resolution patterns
# ---------------------------------------------------------------------------

# Common UK LSE suffix patterns to try dynamically
_UK_SUFFIX_PATTERNS = [
    ".L",   # Most common LSE suffix
    "",      # Some UK stocks don't use suffix
    ".LN",   # Alternative LSE suffix
    ".",     # For symbols like BP
]

# Small exception mapping only for edge cases where symbol root completely changes
_UK_EXCEPTION_MAPPINGS: dict[str, str] = {
    "HSBC": "HSBA.L",
    "BP": "BP.",      # Special case - uses trailing dot
    "RELX": "REL.L",
    "LLOYDS": "LLOY.L",
    "SHEL": "SHEL.L",
    "ULVR": "ULVR.L",
    "BT": "BT.A.L",
    "TUI": "TUI.L",
    "RR": "RR.L",
    "BAE": "BAES.L",
    "ITV": "ITV.L",
    "WTW": "WTW.L",
}

# ---------------------------------------------------------------------------
# Mapping helpers — translate yfinance Ticker.info keys → our dict keys
# ---------------------------------------------------------------------------

_FUNDAMENTAL_MAP: dict[str, str] = {
    "trailingPE": "P/E",
    "forwardPE": "Forward P/E",
    "pegRatio": "PEG",
    "priceToSalesTrailing12Months": "P/S",
    "priceToBook": "P/B",
    "enterpriseToEbitda": "EV/EBITDA",
    "enterpriseToRevenue": "EV/Sales",
    "trailingEps": "EPS (ttm)",
    "forwardEps": "EPS next Y",
    "totalRevenue": "Sales",
    "revenueGrowth": "Sales Q/Q",
    "grossMargins": "Gross Margin",
    "operatingMargins": "Oper. Margin",
    "profitMargins": "Profit Margin",
    "returnOnAssets": "ROA",
    "returnOnEquity": "ROE",
    "currentRatio": "Current Ratio",
    "quickRatio": "Quick Ratio",
    "debtToEquity": "Debt/Eq",
    "marketCap": "Market Cap",
    "enterpriseValue": "Enterprise Value",
    "bookValue": "Book/sh",
    "totalCashPerShare": "Cash/sh",
    "dividendRate": "Dividend TTM",
    "dividendYield": "Dividend Est.",
    "payoutRatio": "Payout",
    "fullTimeEmployees": "Employees",
    "earningsGrowth": "EPS Q/Q",
    "earningsQuarterlyGrowth": "EPS Y/Y TTM",
}

_ANALYST_MAP: dict[str, str] = {
    "targetMeanPrice": "Target Price",
    "recommendationMean": "Recom",
    "currentPrice": "Price",
    "heldPercentInsiders": "Insider Own",
    "heldPercentInstitutions": "Inst Own",
    "shortPercentOfFloat": "Short Float",
    "shortRatio": "Short Ratio",
    "sharesShort": "Short Interest",
}


def _fmt(val: Any) -> str:
    """Coerce a value to a display string, matching Finviz-like formatting."""
    if val is None:
        return "-"
    if isinstance(val, float):
        # percentages coming from yfinance are 0–1 floats
        if -1 < val < 1 and val != 0:
            return f"{val * 100:.2f}%"
        return f"{val:.2f}"
    return str(val)


def _map_info(info: dict, mapping: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for yf_key, our_key in mapping.items():
        val = info.get(yf_key)
        if val is not None:
            out[our_key] = _fmt(val)
    return out


def _pct(val: float | None) -> str:
    if val is None:
        return "-"
    return f"{val:.2f}%"


# ---------------------------------------------------------------------------
# Provider
# ---------------------------------------------------------------------------


class YFinanceProvider:
    """Primary data provider using the ``yfinance`` library.

    Implements the :class:`DataProvider` protocol.
    """

    def __init__(self) -> None:
        # per-symbol in-memory cache so we don't hit yfinance twice
        self._cache: dict[str, dict] = {}
        # resolved symbol → market mapping
        self._resolved: dict[str, tuple[str, str]] = {}

    # -- internal helpers ---------------------------------------------------

    def _get_ticker(self, symbol: str) -> yf.Ticker:
        return yf.Ticker(symbol)

    def _probe_symbol(self, symbol: str) -> dict | None:
        """Return Ticker.info if *symbol* appears valid, else None."""
        try:
            ticker = self._get_ticker(symbol)
            info = ticker.info or {}
            # yfinance returns an info dict even for invalid symbols, but
            # it won't have a market price.
            if info.get("regularMarketPrice") or info.get("currentPrice"):
                return info
        except Exception:
            pass
        return None

    def resolve_symbol(self, raw_symbol: str, preferred_market: str | None = None) -> tuple[str, str]:
        """Try *raw_symbol* as-is, then with multiple UK patterns dynamically.

        Returns ``(resolved_symbol, market)`` where market is ``"US"``
        or ``"UK"``.  Raises ``ValueError`` if the ticker cannot be found.
        
        Args:
            raw_symbol: The symbol to resolve
            preferred_market: If "UK", prioritize UK symbols even if US symbol exists
        """
        if raw_symbol in self._resolved:
            return self._resolved[raw_symbol]

        # Normalize symbol for pattern matching
        normalized = raw_symbol.rstrip(".").upper()
        
        # If UK is preferred, try UK patterns first
        if preferred_market == "UK":
            uk_result = self._try_uk_patterns(normalized)
            if uk_result:
                uk_symbol, uk_info = uk_result
                self._resolved[raw_symbol] = (uk_symbol, "UK")
                return uk_symbol, "UK"

        # Try as-is (covers US tickers and other exchanges)
        info = self._probe_symbol(raw_symbol)
        if info:
            market = "UK" if raw_symbol.endswith((".L", ".LN", ".")) else "US"
            self._resolved[raw_symbol] = (raw_symbol, market)
            return raw_symbol, market

        # If preferred market isn't UK or UK patterns failed, try UK patterns now
        if preferred_market != "UK":
            uk_result = self._try_uk_patterns(normalized)
            if uk_result:
                uk_symbol, uk_info = uk_result
                self._resolved[raw_symbol] = (uk_symbol, "UK")
                return uk_symbol, "UK"

        raise ValueError(f"Ticker '{raw_symbol}' not found on US or UK exchanges")

    def _try_uk_patterns(self, symbol: str) -> tuple[str, dict] | None:
        """Try hybrid UK LSE resolution for a symbol.
        
        Returns (resolved_symbol, info_dict) or None if no UK variant found.
        
        Strategy:
        1. Check exception mappings for edge cases (HSBC->HSBA.L)
        2. Try dynamic suffix patterns for common cases (VOD->VOD.L)
        """
        # 1. Check exception mappings first (edge cases where symbol root completely changes)
        if symbol in _UK_EXCEPTION_MAPPINGS:
            mapped_symbol = _UK_EXCEPTION_MAPPINGS[symbol]
            info = self._probe_symbol(mapped_symbol)
            if info:
                logger.debug(f"Found UK symbol via exception mapping: {symbol} -> {mapped_symbol}")
                return mapped_symbol, info
        
        # 2. Try dynamic suffix patterns for common cases
        for suffix in _UK_SUFFIX_PATTERNS:
            uk_symbol = f"{symbol}{suffix}"
            info = self._probe_symbol(uk_symbol)
            if info:
                logger.debug(f"Found UK symbol via pattern: {symbol} -> {uk_symbol}")
                return uk_symbol, info
        
        # 3. Special handling for trailing dot symbols (e.g. BP -> BP.)
        if symbol.endswith("."):
            # Remove trailing dot and try patterns again
            clean_symbol = symbol.rstrip(".")
            for suffix in _UK_SUFFIX_PATTERNS:
                uk_symbol = f"{clean_symbol}{suffix}"
                info = self._probe_symbol(uk_symbol)
                if info:
                    logger.debug(f"Found UK symbol with dot handling: {symbol} -> {uk_symbol}")
                    return uk_symbol, info
        
        return None

    def _ensure_cached(self, symbol: str) -> dict:
        """Fetch and cache info + history for *symbol*."""
        if symbol in self._cache:
            return self._cache[symbol]

        ticker = self._get_ticker(symbol)
        info = ticker.info or {}
        try:
            hist: pd.DataFrame = ticker.history(period="1y")
        except Exception:
            hist = pd.DataFrame()
        try:
            news = ticker.news or []
        except Exception:
            news = []

        self._cache[symbol] = {"info": info, "hist": hist, "news": news}
        return self._cache[symbol]

    # -- DataProvider interface ---------------------------------------------

    async def get_fundamentals(self, symbol: str) -> dict:
        data = self._ensure_cached(symbol)
        return _map_info(data["info"], _FUNDAMENTAL_MAP)

    async def get_technicals(self, symbol: str) -> dict:
        data = self._ensure_cached(symbol)
        info = data["info"]
        hist: pd.DataFrame = data["hist"]

        technicals: dict[str, str] = {}

        # Price from info
        price = info.get("currentPrice") or info.get("regularMarketPrice")
        if price is not None:
            technicals["Price"] = _fmt(price)

        prev_close = info.get("previousClose") or info.get("regularMarketPreviousClose")
        if prev_close is not None:
            technicals["Prev Close"] = _fmt(prev_close)

        if price and prev_close:
            change = (price - prev_close) / prev_close * 100
            technicals["Change"] = _pct(change)

        beta = info.get("beta")
        if beta is not None:
            technicals["Beta"] = _fmt(beta)

        vol = info.get("volume") or info.get("regularMarketVolume")
        if vol is not None:
            technicals["Volume"] = str(vol)
        avg_vol = info.get("averageDailyVolume10Day")
        if avg_vol is not None:
            technicals["Avg Volume"] = str(avg_vol)
        if vol and avg_vol and avg_vol > 0:
            technicals["Rel Volume"] = f"{vol / avg_vol:.2f}"

        high52 = info.get("fiftyTwoWeekHigh")
        low52 = info.get("fiftyTwoWeekLow")
        if high52 is not None:
            technicals["52W High"] = _fmt(high52)
        if low52 is not None:
            technicals["52W Low"] = _fmt(low52)

        # Compute indicators from price history
        if not hist.empty and "Close" in hist.columns:
            close = hist["Close"]

            sma20 = sma(close, 20)
            sma50 = sma(close, 50)
            sma200 = sma(close, 200)

            if sma20.notna().any():
                last_sma20 = sma20.dropna().iloc[-1]
                technicals["SMA20"] = _pct((price - last_sma20) / last_sma20 * 100) if price else _fmt(last_sma20)
            if sma50.notna().any():
                last_sma50 = sma50.dropna().iloc[-1]
                technicals["SMA50"] = _pct((price - last_sma50) / last_sma50 * 100) if price else _fmt(last_sma50)
            if sma200.notna().any():
                last_sma200 = sma200.dropna().iloc[-1]
                technicals["SMA200"] = _pct((price - last_sma200) / last_sma200 * 100) if price else _fmt(last_sma200)

            rsi_series = rsi(close)
            if rsi_series.notna().any():
                technicals["RSI (14)"] = f"{rsi_series.dropna().iloc[-1]:.2f}"

            if {"High", "Low", "Close"}.issubset(hist.columns):
                atr_series = atr(hist["High"], hist["Low"], close)
                if atr_series.notna().any():
                    technicals["ATR (14)"] = _fmt(atr_series.dropna().iloc[-1])

            # Performance periods
            def _perf(days: int) -> str | None:
                if len(close) < days + 1:
                    return None
                old = close.iloc[-(days + 1)]
                return _pct((close.iloc[-1] - old) / old * 100)

            for label, days in [
                ("Perf Week", 5), ("Perf Month", 21), ("Perf Quarter", 63),
                ("Perf Half Y", 126), ("Perf Year", 252),
            ]:
                val = _perf(days)
                if val is not None:
                    technicals[label] = val

            # Volatility from Bollinger bandwidth
            upper, middle, lower = bollinger_bands(close)
            if middle.notna().any() and upper.notna().any():
                bw = (upper.iloc[-1] - lower.iloc[-1]) / middle.iloc[-1] * 100
                technicals["Volatility"] = _pct(bw)

        return technicals

    async def get_analyst_data(self, symbol: str) -> dict:
        data = self._ensure_cached(symbol)
        info = data["info"]
        result = _map_info(info, _ANALYST_MAP)

        # Recommendation counts from Ticker.info
        for key in ("recommendationKey",):
            val = info.get(key)
            if val is not None:
                result["Recommendation Key"] = val

        # Number of analyst opinions
        noa = info.get("numberOfAnalystOpinions")
        if noa is not None:
            result["Analyst Count"] = str(noa)

        target_high = info.get("targetHighPrice")
        target_low = info.get("targetLowPrice")
        if target_high is not None:
            result["Target High"] = _fmt(target_high)
        if target_low is not None:
            result["Target Low"] = _fmt(target_low)

        return result

    async def get_news(self, symbol: str) -> list[dict]:
        data = self._ensure_cached(symbol)
        raw_news = data.get("news", [])
        items: list[dict] = []
        for article in raw_news:
            items.append({
                "timestamp": article.get("providerPublishTime", ""),
                "title": article.get("title", ""),
                "url": article.get("link", ""),
                "publisher": article.get("publisher", ""),
            })
        return items

    def clear_cache(self, symbol: str | None = None) -> None:
        if symbol is None:
            self._cache.clear()
        else:
            self._cache.pop(symbol, None)

    async def close(self) -> None:
        self._cache.clear()
