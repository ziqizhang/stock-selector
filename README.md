# Stock Selector

This is a personal stock tracker and analysis dashboard that helps decide whether to buy, hold, or sell stocks. Runs locally as a web app, uses web scraping for market data and Claude Code CLI (default), Codex CLI, or Opencode CLI for AI-powered analysis and scoring.

## Features

- **Watchlist management** — Add and remove stock tickers with symbol, name, and sector
- **7-signal analysis** — Each ticker is analyzed across seven categories, each scored from -10 (strong sell) to +10 (strong buy):
  - Fundamentals (P/E, revenue, margins, debt)
  - Analyst consensus (price targets, buy/hold/sell ratings)
  - Insider activity (insider buys/sells, cluster buys)
  - Technicals (RSI, MACD, moving averages, Bollinger Bands)
  - Sentiment & news (recent news tone, event significance)
  - Sector context (sector-relative performance, rotation trends)
  - Risk assessment (bull/bear case, volatility)
- **AI-powered synthesis** — Claude (default), Codex, or Opencode analyzes scraped data per signal category, then synthesizes all signals into an overall buy/hold/sell recommendation with narrative explanation
- **Score history** — Historical analyses are stored so you can track score changes over time
- **Real-time progress** — WebSocket-based streaming shows scraping and analysis progress as it happens
- **Staleness alerts** — On startup, the app prompts to refresh if any analysis data is older than 24 hours

## Data Sources

All data is obtained via web scraping (no API keys required):

| Source | Data |
|--------|------|
| Finviz | Fundamentals, technicals, analyst data, stock news |
| OpenInsider | Insider trading activity |
| Google News | General news sentiment |
| Finviz Groups | Sector performance |

## Prerequisites

- **Python 3.10+**
- **Claude Code CLI** (default), **Codex CLI**, or **Opencode CLI** — for LLM analysis. By default the app uses Claude Code CLI. Codex CLI and Opencode CLI are also supported via `STOCK_SELECTOR_LLM=codex` or `STOCK_SELECTOR_LLM=opencode`.

## Setup

1. **Clone the repo:**
   ```bash
   git clone <your-repo-url>
   cd stock-selector
   ```

2. **Create a virtual environment:**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

   For development (tests):
   ```bash
   pip install -r requirements.txt
   pip install pytest pytest-asyncio pytest-httpx
   ```

## Usage

### Start the app

```bash
source .venv/bin/activate
python run.py            # default: claude
python run.py codex      # use codex
python run.py claude     # explicit claude
python run.py opencode   # use opencode
```

The app starts at `http://localhost:8000` and opens your browser automatically.

### Add tickers

On the dashboard, fill in the symbol (e.g. `AAPL`), company name, and sector, then click **Add Ticker**.

### Run analysis

- Click **Refresh All** to analyze every ticker in your watchlist
- On a ticker's detail page, click **Refresh This Ticker** for a single stock
- Each analysis scrapes 5 data sources, runs 8 LLM CLI calls (one per signal + synthesis), and takes ~1-2 minutes per ticker

### View results

- **Dashboard** — Sortable watchlist table with overall score (color-coded) and buy/hold/sell badge
- **Ticker detail** — Score breakdown bar chart, synthesis narrative, expandable per-signal analysis with raw data, and score history line chart

## Project Structure

```
stock-selector/
├── run.py                    # Entry point — starts uvicorn, opens browser
├── pyproject.toml            # Project metadata and dependencies
├── requirements.txt          # Pip-installable dependencies
├── db/
│   └── schema.sql            # SQLite schema (4 tables)
├── src/
│   ├── db.py                 # Async database layer (aiosqlite)
│   ├── models.py             # Pydantic models and enums
│   ├── api/
│   │   ├── routes.py         # FastAPI routes (dashboard, detail, CRUD)
│   │   └── websocket.py      # WebSocket handlers for refresh progress
│   ├── scrapers/
│   │   ├── base.py           # Base scraper with httpx client
│   │   ├── finviz.py         # Finviz (technicals + news)
│   │   ├── openinsider.py    # OpenInsider (insider trades)
│   │   ├── news.py           # Google News (sentiment)
│   │   └── sector.py         # Sector performance (Finviz groups)
│   └── analysis/
│       ├── claude.py          # Claude CLI wrapper
│       ├── codex.py           # Codex CLI wrapper
│       ├── opencode.py        # Opencode CLI wrapper
│       ├── prompts.py         # Prompt templates per signal category
│       ├── scoring.py         # Weighted scoring and recommendation logic
│       └── engine.py          # Analysis orchestrator (scrape → LLM → DB)
├── templates/
│   ├── layout.html            # Base template (Tailwind, HTMX, Chart.js)
│   ├── dashboard.html         # Watchlist table
│   └── detail.html            # Ticker detail with charts
├── static/
│   ├── css/app.css            # Badge and score bar styles
│   └── js/app.js              # WebSocket helpers for refresh UI
└── tests/
    ├── test_db.py             # Database CRUD tests
    ├── test_scrapers.py       # Base scraper test
    └── test_claude.py         # Claude + Codex CLI wrapper tests
```

## Tech Stack

- **Backend:** FastAPI, uvicorn, aiosqlite, Pydantic
- **Frontend:** Jinja2 templates, HTMX, Tailwind CSS (CDN), Chart.js
- **Scraping:** httpx, BeautifulSoup, lxml
- **LLM:** Claude Code CLI (default), Codex CLI, or Opencode CLI
- **Database:** SQLite (stored in `data/stock_selector.db`)

## Running Tests

```bash
source .venv/bin/activate
pip install pytest pytest-asyncio pytest-httpx
python -m pytest tests/ -v
```

## Troubleshooting

**Missing module errors (e.g., `uvicorn` not found)**  
Make sure you are in the right environment and have installed dependencies:

```bash
source .venv/bin/activate
pip install -r requirements.txt
```

If you are using `pyenv` without a virtualenv, install into that environment instead:

```bash
pyenv local 3.9.1
pip install -r requirements.txt
```

## Notes

- This is a single-user local app — no authentication or multi-user support
- Web scraping selectors may break if source sites change their HTML structure
- The SQLite database is created automatically at `data/stock_selector.db` on first run
- All scraped data and LLM responses are stored for auditability

## LLM Configuration

By default the app uses Claude when `run.py` is invoked without args. To switch providers, pass a CLI argument:

```bash
python run.py            # default: claude
python run.py codex      # use codex
python run.py claude     # explicit claude
python run.py opencode   # use opencode
```

By default, Codex uses `codex exec --json {prompt}`. You can override:

```bash
# Use Claude instead
export STOCK_SELECTOR_LLM=claude

# Use Opencode instead
export STOCK_SELECTOR_LLM=opencode

# Customize Codex CLI invocation (prompt via stdin unless {prompt} is used)
export CODEX_CMD='codex exec --json {prompt}'
# Example with prompt substitution and extra flags
export CODEX_CMD='codex exec --json --some-flag {prompt}'

# Customize Opencode CLI invocation
export OPENCODE_CMD='opencode run {prompt} --format json'
# Example with extra flags
export OPENCODE_CMD='opencode run {prompt} --format json --model gpt-4'
```
