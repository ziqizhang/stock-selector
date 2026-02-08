# Stock Selector — Design Document

## Overview

A personal stock tracker and analysis dashboard that helps decide whether to buy, hold, or sell stocks. Runs locally as a web app, uses web scraping for data and Claude Code CLI (Max subscription) for AI-powered analysis and scoring.

## Architecture

Three-layer local web app:

- **Backend (FastAPI)** — REST API for watchlist management, analysis orchestration, WebSocket for streaming refresh progress
- **Frontend (HTMX + Tailwind CSS + Chart.js)** — server-rendered, lightweight, no JS build pipeline
- **Scraping Layer** — modular scrapers per data source using httpx + BeautifulSoup (playwright as fallback for JS-heavy sites)
- **LLM Layer** — calls `claude --print -p "<prompt>"` via subprocess; no API key needed, uses existing Max subscription

### Startup Flow

Run `python run.py`, opens in browser. If any ticker data is older than 24 hours, prompts: "Your analysis data is stale — refresh now?"

### LLM Integration

- Each signal category gets its own prompt template with scraped data
- A synthesis prompt combines all signal results into an overall recommendation
- Prompts instruct Claude to return structured JSON (scores) + markdown narratives
- One ticker analysis = ~3-5 Claude CLI calls (one per signal group + synthesis)
- Full watchlist refresh (5-15 tickers) = ~15-75 calls

## Signal Categories

Each category scored from **-10 (strong sell) to +10 (strong buy)** with confidence level (low/medium/high):

### 1. Fundamentals
- P/E ratio, revenue growth, margins, debt levels, earnings trends
- Compared against sector averages
- Sources: Yahoo Finance, Macrotrends

### 2. Analyst Consensus
- Price targets (low/median/high), buy/hold/sell ratings distribution
- Recent upgrades/downgrades
- Sources: Yahoo Finance analyst pages, TipRanks

### 3. Insider & Institutional Activity
- Recent insider buys/sells (cluster buys are bullish signals)
- Institutional ownership changes
- Sources: OpenInsider, Finviz, SEC EDGAR

### 4. Technicals
- Support/resistance levels, RSI, moving averages, volume trends, MACD, Bollinger Bands
- Sources: Finviz, StockAnalysis.com

### 5. Sentiment & News
- Recent news events explaining surges/drops
- Social media sentiment, earnings call tone
- Sources: Google News, Reddit (r/stocks, r/wallstreetbets), Finviz news

### 6. Sector Context
- Broader sector performance, stock-specific vs sector-wide movement
- Sector rotation trends
- Sources: sector ETF performance, Google News

### 7. Risk Assessment
- Bear case / bull case summary
- Volatility, beta, max drawdown potential
- Upcoming catalysts (earnings dates, FDA decisions, etc.)

### Overall Score
Weighted average of all categories. Synthesis narrative explains the reasoning and provides a buy/hold/sell recommendation.

## Data Model (SQLite)

### tickers
| Column    | Type     | Notes          |
|-----------|----------|----------------|
| symbol    | TEXT PK  |                |
| name      | TEXT     |                |
| sector    | TEXT     |                |
| added_at  | DATETIME |                |

### analyses
| Column     | Type     | Notes                        |
|------------|----------|------------------------------|
| id         | INTEGER PK |                            |
| symbol     | TEXT FK  | references tickers           |
| category   | TEXT     | e.g., "fundamentals"         |
| score      | REAL     | -10 to +10                   |
| confidence | TEXT     | low/medium/high              |
| narrative  | TEXT     | markdown                     |
| raw_data   | TEXT     | JSON blob of scraped data    |
| created_at | DATETIME |                              |

### syntheses
| Column        | Type     | Notes                     |
|---------------|----------|---------------------------|
| id            | INTEGER PK |                         |
| symbol        | TEXT FK  | references tickers         |
| overall_score | REAL     |                           |
| recommendation| TEXT     | buy/hold/sell              |
| narrative     | TEXT     | full markdown summary      |
| signal_scores | TEXT     | JSON of all category scores|
| created_at    | DATETIME |                           |

### scrape_cache
| Column     | Type     | Notes                |
|------------|----------|----------------------|
| id         | INTEGER PK |                    |
| url        | TEXT     |                      |
| content    | TEXT     |                      |
| fetched_at | DATETIME |                      |
| expires_at | DATETIME | TTL for re-fetching  |

Design decisions:
- Historical analyses kept for score-over-time tracking
- Raw scraped data stored alongside LLM analysis for auditability
- No user/auth tables — single-user local app

## UI Layout

### Dashboard (home page)
- Watchlist table: symbol, name, sector, overall score (color-coded), recommendation badge (BUY/HOLD/SELL), last refreshed
- Sortable columns, score as default sort
- "Refresh All" button, staleness prompt on load
- "Add Ticker" input in header

### Ticker Detail Page
- Hero: ticker name, current price, overall score + recommendation
- Score breakdown: horizontal bar chart per signal category (-10 to +10)
- Expandable sections per signal category with score, confidence, narrative, raw data toggle
- Score history chart (line graph across refreshes)
- Bull case / Bear case side-by-side cards
- "Refresh This Ticker" and "Remove from Watchlist" buttons

### Refresh Flow
- Progress indicator showing each step: "Scraping fundamentals... Analyzing with Claude..."
- Results stream in as each signal category completes
- ~1-2 minutes per ticker

## Project Structure

```
stock-selector/
├── run.py                  # Entry point
├── pyproject.toml          # Dependencies
├── db/
│   └── schema.sql          # SQLite schema
├── src/
│   ├── api/
│   │   ├── routes.py       # FastAPI routes
│   │   └── websocket.py    # WebSocket for refresh progress
│   ├── scrapers/
│   │   ├── base.py         # Base scraper class
│   │   ├── yahoo.py        # Yahoo Finance
│   │   ├── finviz.py       # Finviz
│   │   ├── openinsider.py  # Insider transactions
│   │   ├── news.py         # Google News
│   │   └── sector.py       # Sector/ETF performance
│   ├── analysis/
│   │   ├── engine.py       # Orchestrates scraping + LLM
│   │   ├── prompts.py      # Prompt templates
│   │   ├── claude.py       # Claude CLI wrapper
│   │   └── scoring.py      # Score normalization
│   ├── db.py               # SQLite queries
│   └── models.py           # Pydantic models
├── static/
│   ├── css/
│   └── js/
├── templates/
│   ├── layout.html
│   ├── dashboard.html
│   └── detail.html
└── docs/
    └── plans/
```

### Dependencies
FastAPI, uvicorn, httpx, beautifulsoup4, playwright, Jinja2, Pydantic, Chart.js, Tailwind CSS, HTMX
