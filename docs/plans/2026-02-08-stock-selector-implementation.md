# Stock Selector Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a local web app that tracks a personal stock watchlist and provides AI-powered buy/hold/sell analysis using web scraping and Claude Code CLI.

**Architecture:** FastAPI backend with SQLite storage, HTMX + Tailwind frontend, modular web scrapers (httpx + BeautifulSoup), and Claude CLI for LLM-powered signal scoring and narrative generation.

**Tech Stack:** Python 3.11+, FastAPI, uvicorn, httpx, beautifulsoup4, playwright, Jinja2, Pydantic, SQLite, HTMX, Tailwind CSS, Chart.js

---

## Phase 1: Project Skeleton & Database

### Task 1: Project setup and dependencies

**Files:**
- Create: `pyproject.toml`
- Create: `run.py`
- Create: `src/__init__.py`

**Step 1: Create pyproject.toml**

```toml
[project]
name = "stock-selector"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.34.0",
    "jinja2>=3.1.0",
    "httpx>=0.28.0",
    "beautifulsoup4>=4.12.0",
    "lxml>=5.0.0",
    "pydantic>=2.0.0",
    "aiosqlite>=0.20.0",
    "python-multipart>=0.0.18",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.24.0",
    "pytest-httpx>=0.35.0",
]
```

**Step 2: Create run.py entry point**

```python
import subprocess
import sys
import webbrowser
import threading
import uvicorn


def open_browser():
    """Open browser after a short delay to let the server start."""
    import time
    time.sleep(1.5)
    webbrowser.open("http://localhost:8000")


def main():
    threading.Thread(target=open_browser, daemon=True).start()
    uvicorn.run("src.api.routes:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
```

**Step 3: Create src/__init__.py (empty)**

**Step 4: Install dependencies**

Run: `cd /home/zz/Work/stock-selector && pip install -e ".[dev]"`

**Step 5: Verify run.py starts (will fail because routes don't exist yet — that's ok)**

Run: `cd /home/zz/Work/stock-selector && python -c "from run import main; print('import ok')"`
Expected: `import ok`

---

### Task 2: SQLite schema and database layer

**Files:**
- Create: `db/schema.sql`
- Create: `src/db.py`
- Create: `tests/__init__.py`
- Create: `tests/test_db.py`

**Step 1: Write the failing test**

```python
# tests/test_db.py
import pytest
import asyncio
from src.db import Database


@pytest.fixture
async def db(tmp_path):
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


@pytest.mark.asyncio
async def test_add_and_list_tickers(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    tickers = await db.list_tickers()
    assert len(tickers) == 1
    assert tickers[0]["symbol"] == "AAPL"
    assert tickers[0]["name"] == "Apple Inc."


@pytest.mark.asyncio
async def test_remove_ticker(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.remove_ticker("AAPL")
    tickers = await db.list_tickers()
    assert len(tickers) == 0


@pytest.mark.asyncio
async def test_save_and_get_analysis(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.save_analysis(
        symbol="AAPL",
        category="fundamentals",
        score=7.5,
        confidence="high",
        narrative="Strong earnings growth.",
        raw_data='{"pe": 28.5}',
    )
    analyses = await db.get_analyses("AAPL")
    assert len(analyses) == 1
    assert analyses[0]["category"] == "fundamentals"
    assert analyses[0]["score"] == 7.5


@pytest.mark.asyncio
async def test_save_and_get_synthesis(db):
    await db.add_ticker("AAPL", "Apple Inc.", "Technology")
    await db.save_synthesis(
        symbol="AAPL",
        overall_score=6.2,
        recommendation="buy",
        narrative="Overall bullish outlook.",
        signal_scores='{"fundamentals": 7.5}',
    )
    synthesis = await db.get_latest_synthesis("AAPL")
    assert synthesis["recommendation"] == "buy"
    assert synthesis["overall_score"] == 6.2
```

**Step 2: Run test to verify it fails**

Run: `cd /home/zz/Work/stock-selector && python -m pytest tests/test_db.py -v`
Expected: FAIL (module not found)

**Step 3: Create db/schema.sql**

```sql
CREATE TABLE IF NOT EXISTS tickers (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    added_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    category TEXT NOT NULL,
    score REAL NOT NULL,
    confidence TEXT NOT NULL,
    narrative TEXT,
    raw_data TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS syntheses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    overall_score REAL NOT NULL,
    recommendation TEXT NOT NULL,
    narrative TEXT,
    signal_scores TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS scrape_cache (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    url TEXT NOT NULL,
    content TEXT,
    fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_analyses_symbol ON analyses(symbol);
CREATE INDEX IF NOT EXISTS idx_syntheses_symbol ON syntheses(symbol);
CREATE INDEX IF NOT EXISTS idx_scrape_cache_url ON scrape_cache(url);
```

**Step 4: Implement src/db.py**

```python
import aiosqlite
from pathlib import Path
from datetime import datetime

SCHEMA_PATH = Path(__file__).parent.parent / "db" / "schema.sql"


class Database:
    def __init__(self, db_path: str = "data/stock_selector.db"):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    async def init(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA foreign_keys = ON")
        schema = SCHEMA_PATH.read_text()
        await self.db.executescript(schema)
        await self.db.commit()

    async def close(self):
        if self.db:
            await self.db.close()

    # -- Tickers --

    async def add_ticker(self, symbol: str, name: str, sector: str | None = None):
        await self.db.execute(
            "INSERT OR IGNORE INTO tickers (symbol, name, sector) VALUES (?, ?, ?)",
            (symbol.upper(), name, sector),
        )
        await self.db.commit()

    async def remove_ticker(self, symbol: str):
        await self.db.execute("DELETE FROM tickers WHERE symbol = ?", (symbol.upper(),))
        await self.db.commit()

    async def list_tickers(self) -> list[dict]:
        cursor = await self.db.execute("SELECT * FROM tickers ORDER BY symbol")
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_ticker(self, symbol: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM tickers WHERE symbol = ?", (symbol.upper(),)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    # -- Analyses --

    async def save_analysis(
        self, symbol: str, category: str, score: float, confidence: str,
        narrative: str, raw_data: str,
    ):
        await self.db.execute(
            """INSERT INTO analyses (symbol, category, score, confidence, narrative, raw_data)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (symbol.upper(), category, score, confidence, narrative, raw_data),
        )
        await self.db.commit()

    async def get_analyses(self, symbol: str, limit: int = 50) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM analyses WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
            (symbol.upper(), limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_latest_analyses(self, symbol: str) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT * FROM analyses WHERE symbol = ? AND created_at = (
                SELECT MAX(created_at) FROM analyses WHERE symbol = ?
            )""",
            (symbol.upper(), symbol.upper()),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -- Syntheses --

    async def save_synthesis(
        self, symbol: str, overall_score: float, recommendation: str,
        narrative: str, signal_scores: str,
    ):
        await self.db.execute(
            """INSERT INTO syntheses (symbol, overall_score, recommendation, narrative, signal_scores)
               VALUES (?, ?, ?, ?, ?)""",
            (symbol.upper(), overall_score, recommendation, narrative, signal_scores),
        )
        await self.db.commit()

    async def get_latest_synthesis(self, symbol: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM syntheses WHERE symbol = ? ORDER BY created_at DESC LIMIT 1",
            (symbol.upper(),),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_synthesis_history(self, symbol: str, limit: int = 20) -> list[dict]:
        cursor = await self.db.execute(
            "SELECT * FROM syntheses WHERE symbol = ? ORDER BY created_at DESC LIMIT ?",
            (symbol.upper(), limit),
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    # -- Scrape Cache --

    async def get_cached_scrape(self, url: str) -> dict | None:
        cursor = await self.db.execute(
            "SELECT * FROM scrape_cache WHERE url = ? AND expires_at > datetime('now') ORDER BY fetched_at DESC LIMIT 1",
            (url,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def save_scrape_cache(self, url: str, content: str, ttl_hours: int = 24):
        await self.db.execute(
            """INSERT INTO scrape_cache (url, content, expires_at)
               VALUES (?, ?, datetime('now', ?))""",
            (url, content, f"+{ttl_hours} hours"),
        )
        await self.db.commit()

    # -- Dashboard helpers --

    async def get_dashboard_data(self) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT t.symbol, t.name, t.sector, t.added_at,
                      s.overall_score, s.recommendation, s.created_at as last_refreshed
               FROM tickers t
               LEFT JOIN syntheses s ON t.symbol = s.symbol
                 AND s.id = (SELECT MAX(id) FROM syntheses WHERE symbol = t.symbol)
               ORDER BY s.overall_score DESC NULLS LAST"""
        )
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def get_staleness(self) -> bool:
        cursor = await self.db.execute(
            """SELECT COUNT(*) as stale FROM tickers t
               LEFT JOIN syntheses s ON t.symbol = s.symbol
                 AND s.id = (SELECT MAX(id) FROM syntheses WHERE symbol = t.symbol)
               WHERE s.created_at IS NULL OR s.created_at < datetime('now', '-24 hours')"""
        )
        row = await cursor.fetchone()
        return row["stale"] > 0
```

**Step 5: Run tests to verify they pass**

Run: `cd /home/zz/Work/stock-selector && python -m pytest tests/test_db.py -v`
Expected: All 4 tests PASS

---

### Task 3: Pydantic models

**Files:**
- Create: `src/models.py`

**Step 1: Create the models**

```python
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class Recommendation(str, Enum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SignalCategory(str, Enum):
    FUNDAMENTALS = "fundamentals"
    ANALYST_CONSENSUS = "analyst_consensus"
    INSIDER_ACTIVITY = "insider_activity"
    TECHNICALS = "technicals"
    SENTIMENT = "sentiment"
    SECTOR_CONTEXT = "sector_context"
    RISK_ASSESSMENT = "risk_assessment"


class TickerCreate(BaseModel):
    symbol: str
    name: str
    sector: str | None = None


class TickerResponse(BaseModel):
    symbol: str
    name: str
    sector: str | None
    added_at: str | None


class SignalResult(BaseModel):
    category: SignalCategory
    score: float = Field(ge=-10, le=10)
    confidence: Confidence
    narrative: str
    raw_data: dict


class SynthesisResult(BaseModel):
    overall_score: float = Field(ge=-10, le=10)
    recommendation: Recommendation
    narrative: str
    signal_scores: dict[str, float]


class DashboardRow(BaseModel):
    symbol: str
    name: str
    sector: str | None
    overall_score: float | None
    recommendation: str | None
    last_refreshed: str | None


class RefreshProgress(BaseModel):
    symbol: str
    step: str
    category: str | None = None
    done: bool = False
```

**Step 2: Verify import**

Run: `cd /home/zz/Work/stock-selector && python -c "from src.models import *; print('models ok')"`
Expected: `models ok`

---

## Phase 2: Scraping Layer

### Task 4: Base scraper and scrape cache integration

**Files:**
- Create: `src/scrapers/__init__.py`
- Create: `src/scrapers/base.py`
- Create: `tests/test_scrapers.py`

**Step 1: Write the failing test**

```python
# tests/test_scrapers.py
import pytest
import httpx
from src.scrapers.base import BaseScraper


class FakeScraper(BaseScraper):
    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(f"https://example.com/quote/{symbol}")
        return {"html_length": len(html)}


@pytest.mark.asyncio
async def test_base_scraper_fetch(httpx_mock):
    httpx_mock.add_response(
        url="https://example.com/quote/AAPL",
        text="<html><body>Apple Inc. $150</body></html>",
    )
    scraper = FakeScraper()
    result = await scraper.scrape("AAPL")
    assert result["html_length"] > 0
    await scraper.close()
```

**Step 2: Run test to verify it fails**

Run: `cd /home/zz/Work/stock-selector && python -m pytest tests/test_scrapers.py -v`
Expected: FAIL

**Step 3: Implement base scraper**

```python
# src/scrapers/base.py
import httpx
from bs4 import BeautifulSoup


class BaseScraper:
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }

    def __init__(self):
        self.client = httpx.AsyncClient(
            headers=self.HEADERS,
            follow_redirects=True,
            timeout=30.0,
        )

    async def fetch(self, url: str) -> str:
        response = await self.client.get(url)
        response.raise_for_status()
        return response.text

    def parse_html(self, html: str) -> BeautifulSoup:
        return BeautifulSoup(html, "lxml")

    async def scrape(self, symbol: str) -> dict:
        raise NotImplementedError

    async def close(self):
        await self.client.aclose()
```

**Step 4: Run test to verify it passes**

Run: `cd /home/zz/Work/stock-selector && python -m pytest tests/test_scrapers.py -v`
Expected: PASS

---

### Task 5: Yahoo Finance scraper (fundamentals + analyst consensus)

**Files:**
- Create: `src/scrapers/yahoo.py`
- Create: `tests/test_yahoo_scraper.py`

**Step 1: Write the test**

```python
# tests/test_yahoo_scraper.py
import pytest
from src.scrapers.yahoo import YahooFinanceScraper


@pytest.mark.asyncio
async def test_yahoo_scraper_parses_fundamentals(httpx_mock):
    # Mock the Yahoo Finance summary page
    with open("tests/fixtures/yahoo_summary.html", "r") as f:
        html = f.read()
    httpx_mock.add_response(url__regex=r".*finance\.yahoo\.com/quote/AAPL.*", text=html)

    scraper = YahooFinanceScraper()
    result = await scraper.scrape("AAPL")
    assert "fundamentals" in result
    assert "analyst" in result
    await scraper.close()
```

Note: We need to create a fixture HTML file. This task requires visiting Yahoo Finance to understand the page structure. The scraper should extract:

**Fundamentals:** P/E ratio, EPS, market cap, revenue, profit margins, debt/equity from the quote summary and statistics pages.

**Analyst data:** number of buy/hold/sell ratings, price targets from the analysis page.

**Step 2: Implement the scraper**

```python
# src/scrapers/yahoo.py
from src.scrapers.base import BaseScraper


class YahooFinanceScraper(BaseScraper):
    BASE_URL = "https://finance.yahoo.com"

    async def scrape(self, symbol: str) -> dict:
        fundamentals = await self._scrape_fundamentals(symbol)
        analyst = await self._scrape_analyst(symbol)
        return {"fundamentals": fundamentals, "analyst": analyst}

    async def _scrape_fundamentals(self, symbol: str) -> dict:
        html = await self.fetch(f"{self.BASE_URL}/quote/{symbol}/")
        soup = self.parse_html(html)
        data = {}
        # Extract key stats from the quote page
        # Yahoo uses data-testid attributes for key stats
        for row in soup.select('[data-testid="quote-statistics"] tr'):
            cells = row.find_all("td")
            if len(cells) == 2:
                label = cells[0].get_text(strip=True)
                value = cells[1].get_text(strip=True)
                data[label] = value
        return data

    async def _scrape_analyst(self, symbol: str) -> dict:
        html = await self.fetch(f"{self.BASE_URL}/quote/{symbol}/analysis/")
        soup = self.parse_html(html)
        data = {}
        tables = soup.find_all("table")
        for table in tables:
            header = table.find("thead")
            if header:
                title = header.get_text(strip=True)
                rows = []
                for tr in table.find_all("tr"):
                    cells = [td.get_text(strip=True) for td in tr.find_all("td")]
                    if cells:
                        rows.append(cells)
                data[title] = rows
        return data
```

Note: Yahoo Finance HTML structure changes frequently. The scraper will need adjustments once we test against live data. The key is having the structure in place — we'll fine-tune selectors during integration testing.

**Step 3: Create empty fixture dir**

Run: `mkdir -p /home/zz/Work/stock-selector/tests/fixtures`

---

### Task 6: Finviz scraper (technicals + news)

**Files:**
- Create: `src/scrapers/finviz.py`

**Step 1: Implement the scraper**

```python
# src/scrapers/finviz.py
from src.scrapers.base import BaseScraper


class FinvizScraper(BaseScraper):
    BASE_URL = "https://finviz.com/quote.ashx"

    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(f"{self.BASE_URL}?t={symbol}&p=d")
        soup = self.parse_html(html)
        technicals = self._parse_technicals(soup)
        news = self._parse_news(soup)
        return {"technicals": technicals, "news": news}

    def _parse_technicals(self, soup) -> dict:
        data = {}
        table = soup.find("table", class_="snapshot-table2")
        if table:
            rows = table.find_all("tr")
            for row in rows:
                cells = row.find_all("td")
                # Finviz alternates label/value pairs in cells
                for i in range(0, len(cells) - 1, 2):
                    label = cells[i].get_text(strip=True)
                    value = cells[i + 1].get_text(strip=True)
                    data[label] = value
        return data

    def _parse_news(self, soup) -> list[dict]:
        news = []
        news_table = soup.find("table", id="news-table")
        if news_table:
            for row in news_table.find_all("tr"):
                cells = row.find_all("td")
                if len(cells) >= 2:
                    timestamp = cells[0].get_text(strip=True)
                    link = cells[1].find("a")
                    if link:
                        news.append({
                            "timestamp": timestamp,
                            "title": link.get_text(strip=True),
                            "url": link.get("href", ""),
                        })
        return news
```

---

### Task 7: OpenInsider scraper (insider activity)

**Files:**
- Create: `src/scrapers/openinsider.py`

**Step 1: Implement the scraper**

```python
# src/scrapers/openinsider.py
from src.scrapers.base import BaseScraper


class OpenInsiderScraper(BaseScraper):
    BASE_URL = "http://openinsider.com/screener"

    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(
            f"{self.BASE_URL}?s={symbol}&o=&pl=&ph=&st=0&lt=1&lk=&fs=&fr=&fl=&per=&rec=&na=&fdlyl=&fdlyh=&lu=&gh=&gl=&sa=&slt=&sct=&isceo=1&iscfo=1&isd=1&ipp=50&grp=0&nfl=&nfh=&nil=&nih=&nol=&noh=&v2l=&v2h=&oc2l=&oc2h=&sortcol=0&cnt=25&page=1"
        )
        soup = self.parse_html(html)
        return {"insider_trades": self._parse_trades(soup)}

    def _parse_trades(self, soup) -> list[dict]:
        trades = []
        table = soup.find("table", class_="tinytable")
        if not table:
            return trades
        rows = table.find_all("tr")[1:]  # skip header
        for row in rows:
            cells = [td.get_text(strip=True) for td in row.find_all("td")]
            if len(cells) >= 12:
                trades.append({
                    "filing_date": cells[1],
                    "trade_date": cells[2],
                    "ticker": cells[3],
                    "insider_name": cells[4],
                    "title": cells[5],
                    "trade_type": cells[6],
                    "price": cells[7],
                    "qty": cells[8],
                    "owned": cells[9],
                    "change_pct": cells[10],
                    "value": cells[11],
                })
        return trades
```

---

### Task 8: News and sector scrapers

**Files:**
- Create: `src/scrapers/news.py`
- Create: `src/scrapers/sector.py`

**Step 1: Implement news scraper (Google News via search)**

```python
# src/scrapers/news.py
from src.scrapers.base import BaseScraper


class NewsScraper(BaseScraper):
    """Scrapes Google News search results for a stock ticker."""

    async def scrape(self, symbol: str) -> dict:
        html = await self.fetch(
            f"https://www.google.com/search?q={symbol}+stock+news&tbm=nws&num=10"
        )
        soup = self.parse_html(html)
        articles = []
        for item in soup.select("div.SoaBEf"):
            title_el = item.select_one("div.MBeuO")
            source_el = item.select_one("div.OSrXXb span")
            snippet_el = item.select_one("div.GI74Re")
            if title_el:
                articles.append({
                    "title": title_el.get_text(strip=True),
                    "source": source_el.get_text(strip=True) if source_el else "",
                    "snippet": snippet_el.get_text(strip=True) if snippet_el else "",
                })
        return {"news_articles": articles}
```

**Step 2: Implement sector scraper**

```python
# src/scrapers/sector.py
from src.scrapers.base import BaseScraper

# Map of common sectors to their ETF proxies
SECTOR_ETFS = {
    "Technology": "XLK",
    "Healthcare": "XLV",
    "Financial": "XLF",
    "Consumer Cyclical": "XLY",
    "Consumer Defensive": "XLP",
    "Energy": "XLE",
    "Industrials": "XLI",
    "Materials": "XLB",
    "Real Estate": "XLRE",
    "Utilities": "XLU",
    "Communication Services": "XLC",
}


class SectorScraper(BaseScraper):
    """Scrapes sector performance data using Finviz sector view."""

    async def scrape(self, symbol: str, sector: str | None = None) -> dict:
        # Get sector performance overview from Finviz
        html = await self.fetch("https://finviz.com/groups.ashx?g=sector&v=110&o=-perf1w")
        soup = self.parse_html(html)
        sector_data = []
        table = soup.find("table", class_="table-light")
        if table:
            for row in table.find_all("tr")[1:]:
                cells = [td.get_text(strip=True) for td in row.find_all("td")]
                if len(cells) >= 3:
                    sector_data.append({
                        "name": cells[1],
                        "perf_week": cells[2] if len(cells) > 2 else "",
                        "perf_month": cells[3] if len(cells) > 3 else "",
                        "perf_ytd": cells[6] if len(cells) > 6 else "",
                    })

        # Also get news for the sector
        sector_name = sector or "market"
        news_html = await self.fetch(
            f"https://www.google.com/search?q={sector_name}+sector+stock+market+news&tbm=nws&num=5"
        )
        news_soup = self.parse_html(news_html)
        sector_news = []
        for item in news_soup.select("div.SoaBEf"):
            title_el = item.select_one("div.MBeuO")
            if title_el:
                sector_news.append({"title": title_el.get_text(strip=True)})

        return {
            "sector_performance": sector_data,
            "sector_news": sector_news,
            "ticker_sector": sector,
            "sector_etf": SECTOR_ETFS.get(sector, "SPY"),
        }
```

---

## Phase 3: Claude CLI Integration & Analysis Engine

### Task 9: Claude CLI wrapper

**Files:**
- Create: `src/analysis/__init__.py`
- Create: `src/analysis/claude.py`
- Create: `tests/test_claude.py`

**Step 1: Write the failing test**

```python
# tests/test_claude.py
import pytest
import json
from unittest.mock import AsyncMock, patch
from src.analysis.claude import ClaudeCLI


@pytest.mark.asyncio
async def test_claude_cli_returns_parsed_json():
    mock_result = json.dumps({"score": 7.5, "confidence": "high", "narrative": "test"})
    with patch("asyncio.create_subprocess_exec", new_callable=AsyncMock) as mock_exec:
        mock_proc = AsyncMock()
        mock_proc.communicate.return_value = (mock_result.encode(), b"")
        mock_proc.returncode = 0
        mock_exec.return_value = mock_proc

        cli = ClaudeCLI()
        result = await cli.analyze("test prompt")
        assert result == {"score": 7.5, "confidence": "high", "narrative": "test"}
```

**Step 2: Run test to verify it fails**

Run: `cd /home/zz/Work/stock-selector && python -m pytest tests/test_claude.py -v`
Expected: FAIL

**Step 3: Implement Claude CLI wrapper**

```python
# src/analysis/claude.py
import asyncio
import json
import logging

logger = logging.getLogger(__name__)


class ClaudeCLI:
    """Wrapper around the Claude Code CLI for LLM analysis."""

    async def analyze(self, prompt: str) -> dict:
        """Send a prompt to Claude CLI and parse the JSON response."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "claude", "--print", "-p", prompt,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await proc.communicate()

            if proc.returncode != 0:
                logger.error(f"Claude CLI error: {stderr.decode()}")
                return {"error": stderr.decode()}

            response_text = stdout.decode().strip()
            # Try to extract JSON from the response
            return self._parse_response(response_text)
        except FileNotFoundError:
            logger.error("Claude CLI not found. Is it installed?")
            return {"error": "Claude CLI not found"}
        except Exception as e:
            logger.error(f"Claude CLI exception: {e}")
            return {"error": str(e)}

    def _parse_response(self, text: str) -> dict:
        """Extract JSON from Claude's response, handling markdown code blocks."""
        # Try direct JSON parse first
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # Try extracting from markdown code block
        if "```json" in text:
            start = text.index("```json") + 7
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        if "```" in text:
            start = text.index("```") + 3
            end = text.index("```", start)
            try:
                return json.loads(text[start:end].strip())
            except json.JSONDecodeError:
                pass

        # Return as narrative if not JSON
        return {"narrative": text, "parse_error": True}
```

**Step 4: Run test to verify it passes**

Run: `cd /home/zz/Work/stock-selector && python -m pytest tests/test_claude.py -v`
Expected: PASS

---

### Task 10: Prompt templates

**Files:**
- Create: `src/analysis/prompts.py`

**Step 1: Create prompt templates for each signal category**

```python
# src/analysis/prompts.py

SYSTEM_INSTRUCTION = """You are a stock analyst assistant. Analyze the provided data and respond with ONLY valid JSON matching the specified schema. No markdown, no explanation outside the JSON."""


def fundamentals_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the fundamental data for {symbol}:

{_format_data(data)}

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10, where -10 is extremely bearish and 10 is extremely bullish>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of the fundamentals>"
}}"""


def analyst_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the analyst consensus data for {symbol}:

{_format_data(data)}

Consider: price targets vs current price, buy/hold/sell distribution, recent upgrades/downgrades.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of analyst consensus>"
}}"""


def insider_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze insider and institutional trading activity for {symbol}:

{_format_data(data)}

Consider: cluster buys (multiple insiders buying), trade sizes, insider roles (CEO/CFO buys are stronger signals), timing relative to earnings.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of insider activity>"
}}"""


def technicals_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the technical indicators for {symbol}:

{_format_data(data)}

Consider: RSI (oversold < 30, overbought > 70), support/resistance levels, moving average crossovers, volume trends, MACD signal, Bollinger Band position.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of technicals>"
}}"""


def sentiment_prompt(symbol: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze news sentiment and social media discussion for {symbol}:

{_format_data(data)}

Consider: news tone (positive/negative), event significance, social media buzz, earnings call sentiment if available.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of sentiment>"
}}"""


def sector_prompt(symbol: str, sector: str, data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Analyze the sector context for {symbol} in the {sector} sector:

{_format_data(data)}

Consider: is the stock moving with or against the sector? Is this a sector-wide trend or stock-specific? Sector rotation implications.

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown analysis of sector context>"
}}"""


def risk_prompt(symbol: str, all_data: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

Provide a risk assessment for {symbol} based on all available data:

{_format_data(all_data)}

Respond with this exact JSON structure:
{{
    "score": <float from -10 to 10, where negative means high risk>,
    "confidence": "<low|medium|high>",
    "narrative": "<2-3 paragraph markdown risk assessment>",
    "bull_case": "<1-2 paragraph bull case>",
    "bear_case": "<1-2 paragraph bear case>"
}}"""


def synthesis_prompt(symbol: str, signal_results: dict) -> str:
    return f"""{SYSTEM_INSTRUCTION}

You have analyzed {symbol} across multiple signal categories. Here are the results:

{_format_data(signal_results)}

Synthesize all signals into an overall recommendation. Weight the signals appropriately — fundamentals and technicals typically carry more weight for medium-term holds, while sentiment and news matter more for short-term.

Respond with this exact JSON structure:
{{
    "overall_score": <float from -10 to 10>,
    "recommendation": "<buy|hold|sell>",
    "narrative": "<3-5 paragraph markdown synthesis explaining the overall picture, key drivers, and what to watch>",
    "signal_scores": {{<category>: <score> for each signal}}
}}"""


def _format_data(data: dict) -> str:
    """Format a dict as readable text for the prompt."""
    import json
    return json.dumps(data, indent=2, default=str)
```

**Step 2: Verify import**

Run: `cd /home/zz/Work/stock-selector && python -c "from src.analysis.prompts import *; print('prompts ok')"`
Expected: `prompts ok`

---

### Task 11: Analysis engine (orchestrator)

**Files:**
- Create: `src/analysis/engine.py`
- Create: `src/analysis/scoring.py`

**Step 1: Implement scoring helpers**

```python
# src/analysis/scoring.py

CATEGORY_WEIGHTS = {
    "fundamentals": 0.20,
    "analyst_consensus": 0.15,
    "insider_activity": 0.10,
    "technicals": 0.20,
    "sentiment": 0.10,
    "sector_context": 0.10,
    "risk_assessment": 0.15,
}


def weighted_score(signal_scores: dict[str, float]) -> float:
    """Calculate weighted average score from individual signal scores."""
    total_weight = 0
    weighted_sum = 0
    for category, score in signal_scores.items():
        weight = CATEGORY_WEIGHTS.get(category, 0.1)
        weighted_sum += score * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 2)


def score_to_recommendation(score: float) -> str:
    if score >= 3.0:
        return "buy"
    elif score <= -3.0:
        return "sell"
    return "hold"
```

**Step 2: Implement the analysis engine**

```python
# src/analysis/engine.py
import json
import logging
from typing import AsyncGenerator
from src.scrapers.yahoo import YahooFinanceScraper
from src.scrapers.finviz import FinvizScraper
from src.scrapers.openinsider import OpenInsiderScraper
from src.scrapers.news import NewsScraper
from src.scrapers.sector import SectorScraper
from src.analysis.claude import ClaudeCLI
from src.analysis import prompts
from src.analysis.scoring import weighted_score, score_to_recommendation
from src.db import Database
from src.models import SignalCategory, RefreshProgress

logger = logging.getLogger(__name__)


class AnalysisEngine:
    def __init__(self, db: Database):
        self.db = db
        self.claude = ClaudeCLI()
        self.yahoo = YahooFinanceScraper()
        self.finviz = FinvizScraper()
        self.openinsider = OpenInsiderScraper()
        self.news = NewsScraper()
        self.sector = SectorScraper()

    async def analyze_ticker(self, symbol: str) -> AsyncGenerator[RefreshProgress, None]:
        """Run full analysis for a ticker, yielding progress updates."""
        ticker = await self.db.get_ticker(symbol)
        if not ticker:
            yield RefreshProgress(symbol=symbol, step="error", done=True)
            return

        sector = ticker.get("sector")
        all_scraped = {}
        signal_results = {}

        # 1. Scrape fundamentals + analyst from Yahoo
        yield RefreshProgress(symbol=symbol, step="Scraping Yahoo Finance...", category="fundamentals")
        try:
            yahoo_data = await self.yahoo.scrape(symbol)
            all_scraped["yahoo"] = yahoo_data
        except Exception as e:
            logger.error(f"Yahoo scrape failed for {symbol}: {e}")
            yahoo_data = {"fundamentals": {}, "analyst": {}}
            all_scraped["yahoo"] = yahoo_data

        # 2. Scrape technicals + news from Finviz
        yield RefreshProgress(symbol=symbol, step="Scraping Finviz...", category="technicals")
        try:
            finviz_data = await self.finviz.scrape(symbol)
            all_scraped["finviz"] = finviz_data
        except Exception as e:
            logger.error(f"Finviz scrape failed for {symbol}: {e}")
            finviz_data = {"technicals": {}, "news": []}
            all_scraped["finviz"] = finviz_data

        # 3. Scrape insider activity
        yield RefreshProgress(symbol=symbol, step="Scraping OpenInsider...", category="insider_activity")
        try:
            insider_data = await self.openinsider.scrape(symbol)
            all_scraped["openinsider"] = insider_data
        except Exception as e:
            logger.error(f"OpenInsider scrape failed for {symbol}: {e}")
            insider_data = {"insider_trades": []}
            all_scraped["openinsider"] = insider_data

        # 4. Scrape news
        yield RefreshProgress(symbol=symbol, step="Scraping news...", category="sentiment")
        try:
            news_data = await self.news.scrape(symbol)
            all_scraped["news"] = news_data
        except Exception as e:
            logger.error(f"News scrape failed for {symbol}: {e}")
            news_data = {"news_articles": []}
            all_scraped["news"] = news_data

        # 5. Scrape sector context
        yield RefreshProgress(symbol=symbol, step="Scraping sector data...", category="sector_context")
        try:
            sector_data = await self.sector.scrape(symbol, sector)
            all_scraped["sector"] = sector_data
        except Exception as e:
            logger.error(f"Sector scrape failed for {symbol}: {e}")
            sector_data = {"sector_performance": [], "sector_news": []}
            all_scraped["sector"] = sector_data

        # 6. LLM Analysis — one per signal category
        categories = [
            ("fundamentals", prompts.fundamentals_prompt, yahoo_data.get("fundamentals", {})),
            ("analyst_consensus", prompts.analyst_prompt, yahoo_data.get("analyst", {})),
            ("insider_activity", prompts.insider_prompt, insider_data),
            ("technicals", prompts.technicals_prompt, finviz_data.get("technicals", {})),
            ("sentiment", prompts.sentiment_prompt, {**news_data, **finviz_data.get("news", {})}),
        ]

        for category, prompt_fn, data in categories:
            yield RefreshProgress(symbol=symbol, step=f"Analyzing {category}...", category=category)
            prompt = prompt_fn(symbol, data)
            result = await self.claude.analyze(prompt)
            score = result.get("score", 0)
            confidence = result.get("confidence", "low")
            narrative = result.get("narrative", "Analysis unavailable.")
            signal_results[category] = {"score": score, "confidence": confidence, "narrative": narrative}
            await self.db.save_analysis(
                symbol=symbol, category=category, score=score,
                confidence=confidence, narrative=narrative,
                raw_data=json.dumps(data, default=str),
            )

        # Sector context (needs sector param)
        yield RefreshProgress(symbol=symbol, step="Analyzing sector context...", category="sector_context")
        sector_prompt = prompts.sector_prompt(symbol, sector or "Unknown", sector_data)
        result = await self.claude.analyze(sector_prompt)
        signal_results["sector_context"] = {
            "score": result.get("score", 0),
            "confidence": result.get("confidence", "low"),
            "narrative": result.get("narrative", ""),
        }
        await self.db.save_analysis(
            symbol=symbol, category="sector_context",
            score=result.get("score", 0), confidence=result.get("confidence", "low"),
            narrative=result.get("narrative", ""), raw_data=json.dumps(sector_data, default=str),
        )

        # Risk assessment
        yield RefreshProgress(symbol=symbol, step="Analyzing risk...", category="risk_assessment")
        risk_prompt_text = prompts.risk_prompt(symbol, all_scraped)
        result = await self.claude.analyze(risk_prompt_text)
        signal_results["risk_assessment"] = {
            "score": result.get("score", 0),
            "confidence": result.get("confidence", "low"),
            "narrative": result.get("narrative", ""),
            "bull_case": result.get("bull_case", ""),
            "bear_case": result.get("bear_case", ""),
        }
        await self.db.save_analysis(
            symbol=symbol, category="risk_assessment",
            score=result.get("score", 0), confidence=result.get("confidence", "low"),
            narrative=result.get("narrative", ""), raw_data=json.dumps(all_scraped, default=str),
        )

        # 7. Synthesis
        yield RefreshProgress(symbol=symbol, step="Generating overall recommendation...", category=None)
        synthesis_prompt = prompts.synthesis_prompt(symbol, signal_results)
        synthesis = await self.claude.analyze(synthesis_prompt)
        overall_score = synthesis.get("overall_score", weighted_score(
            {k: v["score"] for k, v in signal_results.items()}
        ))
        recommendation = synthesis.get("recommendation", score_to_recommendation(overall_score))
        await self.db.save_synthesis(
            symbol=symbol,
            overall_score=overall_score,
            recommendation=recommendation,
            narrative=synthesis.get("narrative", ""),
            signal_scores=json.dumps({k: v["score"] for k, v in signal_results.items()}),
        )

        yield RefreshProgress(symbol=symbol, step="Complete", done=True)

    async def close(self):
        await self.yahoo.close()
        await self.finviz.close()
        await self.openinsider.close()
        await self.news.close()
        await self.sector.close()
```

---

## Phase 4: API Routes & WebSocket

### Task 12: FastAPI routes and WebSocket

**Files:**
- Create: `src/api/__init__.py`
- Create: `src/api/routes.py`
- Create: `src/api/websocket.py`

**Step 1: Implement WebSocket handler**

```python
# src/api/websocket.py
import json
from fastapi import WebSocket
from src.analysis.engine import AnalysisEngine
from src.db import Database


async def handle_refresh(websocket: WebSocket, symbol: str, db: Database):
    """Stream analysis progress over WebSocket."""
    engine = AnalysisEngine(db)
    try:
        async for progress in engine.analyze_ticker(symbol):
            await websocket.send_text(json.dumps({
                "symbol": progress.symbol,
                "step": progress.step,
                "category": progress.category,
                "done": progress.done,
            }))
    finally:
        await engine.close()


async def handle_refresh_all(websocket: WebSocket, db: Database):
    """Refresh all tickers, streaming progress."""
    tickers = await db.list_tickers()
    total = len(tickers)
    engine = AnalysisEngine(db)
    try:
        for i, ticker in enumerate(tickers):
            await websocket.send_text(json.dumps({
                "type": "ticker_start",
                "symbol": ticker["symbol"],
                "index": i + 1,
                "total": total,
            }))
            async for progress in engine.analyze_ticker(ticker["symbol"]):
                await websocket.send_text(json.dumps({
                    "symbol": progress.symbol,
                    "step": progress.step,
                    "category": progress.category,
                    "done": progress.done,
                }))
        await websocket.send_text(json.dumps({"type": "all_done"}))
    finally:
        await engine.close()
```

**Step 2: Implement main routes**

```python
# src/api/routes.py
import json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.db import Database
from src.api.websocket import handle_refresh, handle_refresh_all

BASE_DIR = Path(__file__).parent.parent.parent
db = Database()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    yield
    await db.close()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    rows = await db.get_dashboard_data()
    is_stale = await db.get_staleness()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tickers": rows,
        "is_stale": is_stale,
    })


@app.post("/tickers")
async def add_ticker(symbol: str = Form(...), name: str = Form(...), sector: str = Form(None)):
    await db.add_ticker(symbol.upper(), name, sector)
    return RedirectResponse(url="/", status_code=303)


@app.post("/tickers/{symbol}/delete")
async def remove_ticker(symbol: str):
    await db.remove_ticker(symbol.upper())
    return RedirectResponse(url="/", status_code=303)


@app.get("/ticker/{symbol}", response_class=HTMLResponse)
async def ticker_detail(request: Request, symbol: str):
    ticker = await db.get_ticker(symbol.upper())
    if not ticker:
        return RedirectResponse(url="/")
    synthesis = await db.get_latest_synthesis(symbol.upper())
    analyses = await db.get_latest_analyses(symbol.upper())
    history = await db.get_synthesis_history(symbol.upper())
    # Parse signal_scores from synthesis
    signal_scores = {}
    if synthesis and synthesis.get("signal_scores"):
        signal_scores = json.loads(synthesis["signal_scores"])
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "ticker": ticker,
        "synthesis": synthesis,
        "analyses": analyses,
        "history": history,
        "signal_scores": signal_scores,
    })


@app.websocket("/ws/refresh/{symbol}")
async def ws_refresh_ticker(websocket: WebSocket, symbol: str):
    await websocket.accept()
    try:
        await handle_refresh(websocket, symbol.upper(), db)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/refresh-all")
async def ws_refresh_all(websocket: WebSocket):
    await websocket.accept()
    try:
        await handle_refresh_all(websocket, db)
    except WebSocketDisconnect:
        pass
```

---

## Phase 5: Frontend Templates

### Task 13: Base layout and static assets

**Files:**
- Create: `templates/layout.html`
- Create: `static/css/app.css`
- Create: `static/js/app.js`

**Step 1: Create base layout with Tailwind CDN and HTMX**

```html
<!-- templates/layout.html -->
<!DOCTYPE html>
<html lang="en" class="h-full bg-gray-50">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{% block title %}Stock Selector{% endblock %}</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/htmx.org@2.0.4"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <link rel="stylesheet" href="/static/css/app.css">
</head>
<body class="h-full">
    <nav class="bg-white shadow-sm border-b">
        <div class="max-w-7xl mx-auto px-4 py-3 flex items-center justify-between">
            <a href="/" class="text-xl font-bold text-gray-900">Stock Selector</a>
        </div>
    </nav>
    <main class="max-w-7xl mx-auto px-4 py-6">
        {% block content %}{% endblock %}
    </main>
    <script src="/static/js/app.js"></script>
    {% block scripts %}{% endblock %}
</body>
</html>
```

**Step 2: Create minimal CSS**

```css
/* static/css/app.css */
.score-bar {
    height: 24px;
    border-radius: 4px;
    transition: width 0.3s ease;
}
.badge-buy { background-color: #10b981; color: white; }
.badge-hold { background-color: #f59e0b; color: white; }
.badge-sell { background-color: #ef4444; color: white; }
```

**Step 3: Create app.js with WebSocket helpers**

```javascript
// static/js/app.js

function refreshTicker(symbol) {
    const progressEl = document.getElementById(`progress-${symbol}`) ||
                       document.getElementById('progress');
    if (progressEl) progressEl.classList.remove('hidden');

    const ws = new WebSocket(`ws://localhost:8000/ws/refresh/${symbol}`);
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const stepEl = document.getElementById(`step-${symbol}`) ||
                       document.getElementById('step');
        if (stepEl) stepEl.textContent = data.step;
        if (data.done) {
            ws.close();
            window.location.reload();
        }
    };
    ws.onerror = () => {
        if (progressEl) progressEl.textContent = 'Error during refresh';
    };
}

function refreshAll() {
    const progressEl = document.getElementById('progress-all');
    if (progressEl) progressEl.classList.remove('hidden');

    const ws = new WebSocket('ws://localhost:8000/ws/refresh-all');
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        const stepEl = document.getElementById('step-all');
        if (data.type === 'ticker_start' && stepEl) {
            stepEl.textContent = `(${data.index}/${data.total}) ${data.symbol}...`;
        } else if (data.type === 'all_done') {
            ws.close();
            window.location.reload();
        } else if (stepEl) {
            stepEl.textContent = `${data.symbol}: ${data.step}`;
        }
    };
}

function scoreColor(score) {
    if (score >= 3) return '#10b981';
    if (score <= -3) return '#ef4444';
    return '#f59e0b';
}
```

---

### Task 14: Dashboard template

**Files:**
- Create: `templates/dashboard.html`

**Step 1: Create the dashboard**

```html
<!-- templates/dashboard.html -->
{% extends "layout.html" %}

{% block title %}Dashboard — Stock Selector{% endblock %}

{% block content %}
<!-- Stale data alert -->
{% if is_stale %}
<div id="stale-alert" class="mb-4 p-4 bg-yellow-50 border border-yellow-200 rounded-lg flex items-center justify-between">
    <span class="text-yellow-800">Your analysis data is stale — refresh now?</span>
    <button onclick="refreshAll()" class="px-4 py-2 bg-yellow-500 text-white rounded hover:bg-yellow-600 text-sm">
        Refresh All
    </button>
</div>
{% endif %}

<!-- Add ticker form -->
<div class="mb-6 bg-white p-4 rounded-lg shadow-sm border">
    <form action="/tickers" method="post" class="flex gap-3 items-end">
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Symbol</label>
            <input type="text" name="symbol" required placeholder="AAPL"
                   class="px-3 py-2 border rounded-md text-sm w-28 uppercase">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Name</label>
            <input type="text" name="name" required placeholder="Apple Inc."
                   class="px-3 py-2 border rounded-md text-sm w-48">
        </div>
        <div>
            <label class="block text-sm font-medium text-gray-700 mb-1">Sector</label>
            <select name="sector" class="px-3 py-2 border rounded-md text-sm w-48">
                <option value="">Select sector...</option>
                <option>Technology</option>
                <option>Healthcare</option>
                <option>Financial</option>
                <option>Consumer Cyclical</option>
                <option>Consumer Defensive</option>
                <option>Energy</option>
                <option>Industrials</option>
                <option>Materials</option>
                <option>Real Estate</option>
                <option>Utilities</option>
                <option>Communication Services</option>
            </select>
        </div>
        <button type="submit" class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm">
            Add Ticker
        </button>
    </form>
</div>

<!-- Refresh all progress -->
<div id="progress-all" class="hidden mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
    <span class="text-blue-800">Refreshing: </span>
    <span id="step-all" class="text-blue-700 font-medium">Starting...</span>
</div>

<!-- Watchlist table -->
<div class="bg-white rounded-lg shadow-sm border overflow-hidden">
    <div class="px-4 py-3 border-b flex items-center justify-between">
        <h2 class="text-lg font-semibold">Watchlist</h2>
        {% if tickers %}
        <button onclick="refreshAll()" class="px-3 py-1.5 bg-gray-100 text-gray-700 rounded hover:bg-gray-200 text-sm">
            Refresh All
        </button>
        {% endif %}
    </div>
    {% if tickers %}
    <table class="w-full">
        <thead class="bg-gray-50">
            <tr>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Symbol</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Name</th>
                <th class="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Sector</th>
                <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Score</th>
                <th class="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase">Signal</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Last Refreshed</th>
                <th class="px-4 py-3 text-right text-xs font-medium text-gray-500 uppercase">Actions</th>
            </tr>
        </thead>
        <tbody class="divide-y">
            {% for t in tickers %}
            <tr class="hover:bg-gray-50 cursor-pointer" onclick="window.location='/ticker/{{ t.symbol }}'">
                <td class="px-4 py-3 font-bold text-blue-600">{{ t.symbol }}</td>
                <td class="px-4 py-3 text-gray-900">{{ t.name }}</td>
                <td class="px-4 py-3 text-gray-500 text-sm">{{ t.sector or '—' }}</td>
                <td class="px-4 py-3 text-center">
                    {% if t.overall_score is not none %}
                    <span class="font-bold {% if t.overall_score >= 3 %}text-green-600{% elif t.overall_score <= -3 %}text-red-600{% else %}text-yellow-600{% endif %}">
                        {{ "%.1f"|format(t.overall_score) }}
                    </span>
                    {% else %}
                    <span class="text-gray-400">—</span>
                    {% endif %}
                </td>
                <td class="px-4 py-3 text-center">
                    {% if t.recommendation %}
                    <span class="px-2 py-1 rounded text-xs font-bold uppercase badge-{{ t.recommendation }}">
                        {{ t.recommendation }}
                    </span>
                    {% else %}
                    <span class="text-gray-400">—</span>
                    {% endif %}
                </td>
                <td class="px-4 py-3 text-right text-sm text-gray-500">
                    {{ t.last_refreshed or 'Never' }}
                </td>
                <td class="px-4 py-3 text-right" onclick="event.stopPropagation()">
                    <form action="/tickers/{{ t.symbol }}/delete" method="post" class="inline"
                          onsubmit="return confirm('Remove {{ t.symbol }}?')">
                        <button type="submit" class="text-red-500 hover:text-red-700 text-sm">Remove</button>
                    </form>
                </td>
            </tr>
            {% endfor %}
        </tbody>
    </table>
    {% else %}
    <div class="p-8 text-center text-gray-500">
        No tickers yet. Add one above to get started.
    </div>
    {% endif %}
</div>
{% endblock %}
```

---

### Task 15: Ticker detail template

**Files:**
- Create: `templates/detail.html`

**Step 1: Create the detail page**

```html
<!-- templates/detail.html -->
{% extends "layout.html" %}

{% block title %}{{ ticker.symbol }} — Stock Selector{% endblock %}

{% block content %}
<!-- Hero -->
<div class="mb-6 bg-white p-6 rounded-lg shadow-sm border">
    <div class="flex items-center justify-between">
        <div>
            <h1 class="text-2xl font-bold">{{ ticker.symbol }} — {{ ticker.name }}</h1>
            <p class="text-gray-500">{{ ticker.sector or 'Unknown sector' }}</p>
        </div>
        <div class="text-right">
            {% if synthesis %}
            <div class="text-3xl font-bold {% if synthesis.overall_score >= 3 %}text-green-600{% elif synthesis.overall_score <= -3 %}text-red-600{% else %}text-yellow-600{% endif %}">
                {{ "%.1f"|format(synthesis.overall_score) }}
            </div>
            <span class="px-3 py-1 rounded text-sm font-bold uppercase badge-{{ synthesis.recommendation }}">
                {{ synthesis.recommendation }}
            </span>
            {% else %}
            <span class="text-gray-400">Not analyzed yet</span>
            {% endif %}
        </div>
    </div>
    <div class="mt-4 flex gap-3">
        <button onclick="refreshTicker('{{ ticker.symbol }}')"
                class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm">
            Refresh Analysis
        </button>
        <form action="/tickers/{{ ticker.symbol }}/delete" method="post" class="inline"
              onsubmit="return confirm('Remove {{ ticker.symbol }}?')">
            <button type="submit" class="px-4 py-2 bg-red-100 text-red-700 rounded-md hover:bg-red-200 text-sm">
                Remove from Watchlist
            </button>
        </form>
        <a href="/" class="px-4 py-2 bg-gray-100 text-gray-700 rounded-md hover:bg-gray-200 text-sm">
            Back to Dashboard
        </a>
    </div>
    <!-- Refresh progress -->
    <div id="progress" class="hidden mt-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
        <span class="text-blue-800">Analyzing: </span>
        <span id="step" class="text-blue-700 font-medium">Starting...</span>
    </div>
</div>

{% if synthesis %}
<!-- Score breakdown chart -->
<div class="mb-6 bg-white p-6 rounded-lg shadow-sm border">
    <h2 class="text-lg font-semibold mb-4">Signal Breakdown</h2>
    <canvas id="scoreChart" height="80"></canvas>
</div>

<!-- Synthesis narrative -->
<div class="mb-6 bg-white p-6 rounded-lg shadow-sm border">
    <h2 class="text-lg font-semibold mb-3">Overall Analysis</h2>
    <div class="prose max-w-none text-gray-700">{{ synthesis.narrative | safe }}</div>
</div>

<!-- Individual signal sections -->
{% for analysis in analyses %}
<details class="mb-3 bg-white rounded-lg shadow-sm border">
    <summary class="px-6 py-4 cursor-pointer flex items-center justify-between">
        <span class="font-medium capitalize">{{ analysis.category | replace("_", " ") }}</span>
        <div class="flex items-center gap-3">
            <span class="text-sm px-2 py-0.5 rounded bg-gray-100">{{ analysis.confidence }}</span>
            <span class="font-bold {% if analysis.score >= 3 %}text-green-600{% elif analysis.score <= -3 %}text-red-600{% else %}text-yellow-600{% endif %}">
                {{ "%.1f"|format(analysis.score) }}
            </span>
        </div>
    </summary>
    <div class="px-6 pb-4 border-t">
        <div class="prose max-w-none text-gray-700 mt-3">{{ analysis.narrative | safe }}</div>
        <details class="mt-3">
            <summary class="text-sm text-gray-500 cursor-pointer">Raw scraped data</summary>
            <pre class="mt-2 p-3 bg-gray-50 rounded text-xs overflow-x-auto">{{ analysis.raw_data }}</pre>
        </details>
    </div>
</details>
{% endfor %}

<!-- Score history -->
{% if history | length > 1 %}
<div class="mb-6 bg-white p-6 rounded-lg shadow-sm border">
    <h2 class="text-lg font-semibold mb-4">Score History</h2>
    <canvas id="historyChart" height="60"></canvas>
</div>
{% endif %}
{% endif %}
{% endblock %}

{% block scripts %}
{% if signal_scores %}
<script>
const scores = {{ signal_scores | tojson }};
const labels = Object.keys(scores).map(k => k.replace(/_/g, ' '));
const values = Object.values(scores);
const colors = values.map(v => v >= 3 ? '#10b981' : v <= -3 ? '#ef4444' : '#f59e0b');

new Chart(document.getElementById('scoreChart'), {
    type: 'bar',
    data: {
        labels: labels,
        datasets: [{
            data: values,
            backgroundColor: colors,
            borderRadius: 4,
        }]
    },
    options: {
        indexAxis: 'y',
        plugins: { legend: { display: false } },
        scales: {
            x: { min: -10, max: 10, grid: { color: '#f3f4f6' } },
            y: { grid: { display: false } }
        }
    }
});
</script>
{% endif %}

{% if history and history | length > 1 %}
<script>
const history = {{ history | tojson }};
new Chart(document.getElementById('historyChart'), {
    type: 'line',
    data: {
        labels: history.map(h => h.created_at).reverse(),
        datasets: [{
            label: 'Overall Score',
            data: history.map(h => h.overall_score).reverse(),
            borderColor: '#3b82f6',
            tension: 0.3,
            fill: false,
        }]
    },
    options: {
        plugins: { legend: { display: false } },
        scales: {
            y: { min: -10, max: 10 },
        }
    }
});
</script>
{% endif %}
{% endblock %}
```

---

## Phase 6: Integration & Polish

### Task 16: Wire everything together and smoke test

**Step 1: Create required directories**

Run:
```bash
mkdir -p static/css static/js templates data tests/fixtures db src/api src/scrapers src/analysis
```

**Step 2: Create all `__init__.py` files**

Create empty `__init__.py` in: `src/`, `src/api/`, `src/scrapers/`, `src/analysis/`, `tests/`

**Step 3: Start the server**

Run: `cd /home/zz/Work/stock-selector && python run.py`

**Step 4: Manual smoke test**
- Open http://localhost:8000
- Add a ticker (e.g., AAPL, Apple Inc., Technology)
- Click "Refresh Analysis" on the detail page
- Verify progress updates stream in
- Verify scores and narratives appear after completion

**Step 5: Fix any scraper selectors**

Web scraping is inherently fragile. Expect to adjust CSS selectors based on live page structures during this step. The key patterns are in place — this is iterative debugging.

---

### Task 17: Error handling and edge cases

**Step 1:** Handle scraper failures gracefully — if one source is down, continue with available data and note the gap in the analysis.

**Step 2:** Add a loading spinner / skeleton UI while refresh is in progress.

**Step 3:** Handle empty watchlist state.

**Step 4:** Handle ticker not found / invalid symbol.

**Step 5:** Add basic input validation (symbol format, duplicate tickers).

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| 1 | Tasks 1-3 | Working project skeleton, DB, models |
| 2 | Tasks 4-8 | All 5 scrapers fetching live data |
| 3 | Tasks 9-11 | Claude CLI integration, prompts, analysis engine |
| 4 | Task 12 | API routes + WebSocket streaming |
| 5 | Tasks 13-15 | Full frontend: dashboard + detail page |
| 6 | Tasks 16-17 | Integration, smoke test, polish |
