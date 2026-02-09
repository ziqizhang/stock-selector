# Stock Selector - Team Status

> Keep this file updated when you complete work that affects setup, configuration, or architecture.

## Quick Start

```bash
# 1. Clone and enter the repo
git clone git@github.com:ziqizhang/stock-selector.git
cd stock-selector

# 2. Create a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
pip install -e ".[dev]"     # includes pytest, pytest-asyncio, pytest-httpx

# 4. Run the app
python run.py               # defaults: LLM=claude, data source=yfinance
```

The app starts at http://localhost:8000 and opens a browser automatically.

## Prerequisites

| Requirement | Notes |
|---|---|
| Python >= 3.10 | Uses `str \| None` union syntax |
| Claude CLI **or** Codex CLI | At least one LLM backend must be installed and on PATH |
| No API keys needed | yfinance and web scrapers work without keys |

## Database

- **SQLite** at `data/stock_selector.db` (auto-created on first run)
- **Alembic** migrations run automatically on startup via `Database.init()`
- No manual migration step needed; just start the app

## Environment Variables

| Variable | Default | Options | Description |
|---|---|---|---|
| `STOCK_SELECTOR_LLM` | `claude` (via run.py) | `claude`, `codex` | LLM backend for analysis |
| `STOCK_SELECTOR_DATA_SOURCE` | `yfinance` | `yfinance`, `finviz` | Primary data provider |
| `CODEX_CMD` | `codex exec --json {prompt}` | any shell command | Custom Codex CLI invocation |
| `CODEX_BIN` | auto-detected | path to binary | Override Codex binary location |

You can also pass these as CLI args:

```bash
python run.py codex                    # use Codex as LLM
python run.py claude --data-source finviz  # Claude + Finviz
```

## Running Tests

```bash
pytest tests/ -v        # all 75 tests
pytest tests/ -v -x     # stop on first failure
```

No network access needed - all HTTP calls are mocked via `pytest-httpx`.

## Architecture Overview

```
run.py                  # entry point (uvicorn + browser open)
src/
  api/routes.py         # FastAPI routes + WebSocket handlers
  api/websocket.py      # WebSocket refresh logic
  models.py             # Pydantic models (TickerCreate, DashboardRow, etc.)
  db.py                 # async SQLite via aiosqlite
  analysis/
    engine.py           # orchestrates scraping + LLM analysis
    claude.py           # Claude CLI wrapper
    codex.py            # Codex CLI wrapper
    prompts.py          # LLM prompt templates per signal category
    scoring.py          # weighted score aggregation
    indicators.py       # SMA, EMA, RSI, ATR, Bollinger Bands
  scrapers/
    provider.py         # DataProvider protocol
    yfinance_provider.py  # yfinance implementation (default)
    finviz_provider.py  # Finviz implementation (optional)
    openinsider.py      # US insider trades
    investegate.py      # UK director dealings
    sector.py           # sector ETFs + sector news
    news.py             # Google News scraper
    base.py             # BaseScraper with rate limiting + caching
templates/              # Jinja2 HTML templates
static/                 # CSS + JS
alembic/                # DB migrations
```

## Data Flow

1. User adds a ticker via the dashboard (symbol, name, market, sector)
2. On refresh, `AnalysisEngine.analyze_ticker()` runs:
   - Resolves the symbol via yfinance (e.g. `VOD` -> `VOD.L` for UK)
   - Fetches fundamentals, technicals, analyst data, news from yfinance
   - Fetches insider data from **OpenInsider** (US) or **Investegate** (UK)
   - Fetches sector context from **FinViz** (US only) + Google News
   - Runs 7 LLM analyses (fundamentals, analyst, insider, technicals, sentiment, sector, risk)
   - Synthesizes an overall score and recommendation

## Market Support

| Market | Insider Source | Sector ETFs | Sector Performance | Ticker Format |
|---|---|---|---|---|
| US | OpenInsider | SPDR (XLK, XLV, etc.) | FinViz | `AAPL` |
| UK | Investegate | iShares LSE (IITU.L, etc.) | Skipped | `VOD.L` (auto-resolved) |

Users select market (US/UK) when adding a ticker. The engine auto-routes to the correct data sources.

### Known Bug: UK Ticker Symbol Mismatch (#21)

Many UK companies use a different ticker symbol on the LSE (used by Yahoo Finance / yfinance) than what appears on Google Finance, the financial press, or the company's own branding. Our `resolve_symbol()` currently just appends `.L` to whatever the user types, which fails for these cases:

| What users type | What Google Finance shows | Actual LSE symbol (yfinance) |
|---|---|---|
| HSBC | HSBC | `HSBA.L` |
| RELX | RELX | `REL.L` |
| VOD | VOD | `VOD.L` (this one works) |

When the LSE symbol doesn't match, yfinance falls back to the US-listed version (e.g. NYSE ADR), so the engine thinks it's a US stock. This means insider data routes to OpenInsider (which has nothing for a UK company) instead of Investegate, resulting in null insider activity.

**Workaround**: Enter the actual LSE ticker code instead of the common name (e.g. `HSBA` not `HSBC`, `REL` not `RELX`). You can look up the LSE code on [Yahoo Finance](https://finance.yahoo.com/) by searching the company name and checking for the `.L` suffix.

**Fix needed**: Smarter symbol resolution — see #21.

## Recent Changes

| Date | Commit | What changed |
|---|---|---|
| 2026-02-09 | `504b3ba` | **Issue #8**: UK market support - Investegate scraper, UK sector ETFs, market-aware engine routing, dashboard market dropdown. Fixed Codex CLI stream detection and Alembic logger interference. 75/75 tests passing. |
| 2026-02-09 | `99820e0` | **Issue #7**: yfinance data provider, technical indicators, Alembic migrations. |

## Known Issues / Tech Debt

See [open issues](https://github.com/ziqizhang/stock-selector/issues) for the full backlog. Key items:

- **#21** — UK insider activity missing due to LSE symbol mismatch (see above)
- **#20** — Replace web scraping with official APIs where available
- **#9** — LLM provider abstraction layer
- **#10** — Google News scraping resilience
- **#11** — Cache LLM responses when scraped data hasn't changed
- **#13** — Improve test coverage
