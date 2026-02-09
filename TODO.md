# Stock Selector — TODO / Roadmap

> This file tracks planned features, improvements, and technical debt.
> Items are organized by priority and category. Convert to GitHub Issues when ready.
>
> **Priority key:** P0 = critical (fix now), P1 = high, P2 = medium, P3 = nice to have

---

## P0: Critical — Tech Debt & Bugs

These are existing risks and bugs that should be fixed before adding new features.

### 1. Validate LLM score output `[tech-debt]`
The app stores whatever score the LLM returns with no validation. If Claude/Codex returns `{"score": 50}`, it's stored as-is, corrupting charts and recommendations.

**Fix:** Clamp scores to [-10, +10] in `engine.py` after each `llm.analyze()` call. Log a warning if clamping was needed. Also validate that `confidence` is one of `low/medium/high` and default to `low` if not.

**Files:** `src/analysis/engine.py`

---

### 2. Wire up scrape cache (it's implemented but unused) `[tech-debt]`
`db.py` has `save_scrape_cache()` and `get_cached_scrape()` with a 24h TTL, but `engine.py` never calls them. Every refresh re-scrapes all sources even if data was fetched minutes ago.

**Fix:** In each scraper's `fetch()` or in `engine.py`, check the cache before making HTTP requests. Save responses to cache after fetching. Respect the 24h TTL. This also reduces the risk of IP bans.

**Files:** `src/analysis/engine.py`, `src/scrapers/base.py`, `src/db.py`

---

### 3. Add rate limiting to scrapers `[tech-debt]`
"Refresh All" on 20 tickers fires 20+ HTTP requests to Finviz in rapid succession. This will get the user's IP banned.

**Fix:** Add a per-domain rate limiter (e.g., 1 request per second per domain) in `BaseScraper.fetch()`. Use `asyncio.Semaphore` or a simple token-bucket implementation.

**Files:** `src/scrapers/base.py`

---

### 4. Fix README inconsistency — default LLM provider `[tech-debt]`
The README says "Codex CLI (default)" in several places, but `run.py` defaults to Claude (`os.environ.setdefault("STOCK_SELECTOR_LLM", "claude")`). The README contradicts itself.

**Fix:** Update README to consistently say Claude is the default, or change `run.py` to match the README. Align on one source of truth.

**Files:** `README.md`, possibly `run.py`

---

### 5. Remove dead Yahoo scraper `[tech-debt]`
`src/scrapers/yahoo.py` exists but is imported nowhere and used by nothing. It's dead code that will confuse contributors.

**Fix:** Delete `src/scrapers/yahoo.py`. Remove any references in README. (Note: we may re-introduce Yahoo via yfinance later — that will be a new, proper implementation.)

**Files:** `src/scrapers/yahoo.py`, `README.md`

---

## P1: High Priority — Features

### 6. Selective refresh from dashboard `[feature]` `[ux]`
Currently the dashboard only has "Refresh All" (all tickers sequentially). Users need to refresh a subset without navigating to each detail page.

**Implementation:**
- Add a checkbox column to the watchlist table on the dashboard
- Add a "Refresh Selected" button (disabled when nothing is checked, hidden when all are checked — show "Refresh All" instead)
- New WebSocket endpoint: `WS /ws/refresh-selected` that accepts a list of symbols
- New handler in `websocket.py` similar to `handle_refresh_all()` but filtered to selected symbols
- Progress display should show "(2/5) Analyzing AAPL..." style updates

**Files:** `templates/dashboard.html`, `static/js/app.js`, `src/api/routes.py`, `src/api/websocket.py`

---

### 7. Migrate primary data source to yfinance `[data-sources]`
Replace raw Finviz HTML scraping with the `yfinance` Python library for fundamentals, technicals, and analyst data. yfinance is more stable than CSS-selector scraping, supports international tickers, and provides a Python API.

**Scope:**
- Install `yfinance` as a dependency
- Create `src/scrapers/yfinance_provider.py` implementing the same interface as current scrapers
- Migrate fundamentals data (P/E, EPS, margins, debt, dividends, etc.)
- Migrate technicals data (price history, moving averages, RSI, volume — may need `ta` library for indicators)
- Migrate analyst data (price targets, recommendations, institutional holders)
- Keep Google News scraping for sentiment (yfinance has limited news)
- Keep OpenInsider scraping for US insider data (yfinance doesn't cover this)
- Remove Finviz scraper dependency for core data (keep as optional fallback if desired)
- Update `engine.py` to use the new provider

**Note:** yfinance is technically an unofficial Yahoo Finance scraper under the hood, but it's a maintained library with a stable API that handles rate limiting and parsing internally.

**Files:** new `src/scrapers/yfinance_provider.py`, `src/analysis/engine.py`, `requirements.txt`

---

### 8. UK market support (FTSE 100/250) `[feature]` `[international]`
Add support for London Stock Exchange tickers alongside existing US support.

**Sub-tasks:**

#### 8a. Market-aware ticker model
- Add a `market` field to the `tickers` table (e.g., "US", "UK") — default "US" for backwards compatibility
- Update `TickerCreate` model and the "Add Ticker" form to include market selection
- yfinance uses `.L` suffix for LSE tickers (e.g., `HSBA.L`, `VOD.L`) — handle this transparently

#### 8b. UK insider data — RNS/Investegate scraper
- Build a scraper for UK director dealings via RNS (Regulatory News Service) or Investegate
- Source: `investegate.co.uk` provides free, scrapeable director dealing disclosures
- Parse: director name, transaction type (buy/sell), shares, value, date
- Replaces OpenInsider for UK tickers

#### 8c. UK sector ETF mapping
- Map UK sectors to iShares UK ETFs for sector-relative analysis:
  - Financials → IUKD.L (UK Dividend), Technology → no direct UK tech ETF (use global XLK or EQQQ.L)
  - Energy → ISF.L or IUKP.L, Healthcare → WUKH.L, etc.
- Add UK entries to the `SECTOR_ETFS` dict in `sector.py`
- Sector scraper should use UK-relevant sector performance data when analyzing UK tickers

#### 8d. Route data sources by market
- `engine.py` should check the ticker's market and route to the appropriate scrapers:
  - US: yfinance + OpenInsider + Google News + Finviz Groups
  - UK: yfinance + RNS/Investegate + Google News + UK sector data
- Prompt templates may need minor adjustments for currency (GBP vs USD) and regulatory context

**Files:** `src/models.py`, `src/db.py`, `db/schema.sql`, `templates/dashboard.html`, new `src/scrapers/investegate.py`, `src/scrapers/sector.py`, `src/analysis/engine.py`, `src/analysis/prompts.py`

---

## P2: Medium Priority — Improvements

### 9. LLM provider abstraction layer `[tech-debt]`
`ClaudeCLI` and `CodexCLI` are separate classes with duplicated parsing logic and no shared interface. Adding a third provider means more duplication.

**Fix:** Create an `LLMProvider` abstract base class with `async analyze(prompt) -> dict`. Have `ClaudeCLI` and `CodexCLI` extend it. Add a factory function: `create_llm_provider(name) -> LLMProvider`. This also makes testing easier (mock the interface, not the subprocess).

**Files:** new `src/analysis/llm_base.py`, `src/analysis/claude.py`, `src/analysis/codex.py`, `src/analysis/engine.py`

---

### 10. Make Google News scraping more resilient `[data-sources]` `[tech-debt]`
Google News CSS selectors (`div.SoaBEf`, `div.MBeuO`, `div.OSrXXb`) are extremely brittle. Google changes class names frequently.

**Options (pick one or combine):**
- Use a news RSS feed instead (Google News RSS is free: `news.google.com/rss/search?q=...`)
- Use `newspaper3k` or `feedparser` library to parse RSS
- Add selector fallback logic — try multiple known selector patterns
- Add a health check: if scraper returns 0 results, log a warning and flag the signal as degraded

**Files:** `src/scrapers/news.py`, possibly `requirements.txt`

---

### 11. Cache LLM responses when scraped data hasn't changed `[tech-debt]`
Each refresh runs 8 LLM calls per ticker even if the underlying scraped data is identical (within the 24h cache window). This wastes LLM credits/time.

**Fix:** Hash the scraped data input for each signal. Before calling the LLM, check if an analysis exists with the same data hash. If so, reuse the previous analysis. Only re-analyze when input data actually changes.

**Files:** `src/analysis/engine.py`, `src/db.py`

---

### 12. User-configurable scoring weights `[feature]` `[ux]`
All tickers use the same hardcoded category weights (fundamentals 20%, technicals 20%, etc.). A growth investor and a value investor have very different priorities.

**Implementation:**
- Add a settings page or a config section on the dashboard
- Allow users to adjust the 7 category weights (sliders or number inputs, must sum to 100%)
- Store weights in a `settings` table or a JSON config file
- `scoring.py` reads weights from config instead of hardcoded dict
- Consider presets: "Growth", "Value", "Income/Dividend", "Momentum"

**Files:** `src/analysis/scoring.py`, `src/db.py`, new `templates/settings.html`, `src/api/routes.py`

---

### 13. Improve test coverage `[tech-debt]`
Current tests cover DB CRUD, base scraper fetch, and LLM wrapper parsing. No tests for:
- `engine.py` (the orchestrator — most critical code)
- `prompts.py` (prompt templates)
- `scoring.py` (weighted scoring logic)
- `routes.py` (API endpoints)
- `websocket.py` (WebSocket handlers)
- Integration tests (end-to-end with mocked scrapers + LLM)

**Priority order:** scoring.py (pure logic, easy to test) → engine.py (mock scrapers + LLM) → routes.py (FastAPI test client)

**Files:** `tests/test_scoring.py`, `tests/test_engine.py`, `tests/test_routes.py`

---

## P3: Nice to Have — Future Ideas

### 14. Portfolio view with allocation sizing `[feature]`
Show a portfolio-level view: total invested, per-ticker allocation %, risk exposure by sector. Suggest rebalancing based on scores.

### 15. Alert system for score changes `[feature]`
Notify (email, desktop notification, or just a dashboard badge) when a ticker's score changes significantly (e.g., drops from buy to hold).

### 16. Compare tickers side-by-side `[feature]` `[ux]`
Select 2-3 tickers and see their signal scores compared in a radar chart or table. Useful for deciding between similar stocks.

### 17. Export analysis to PDF/CSV `[feature]`
Allow exporting a ticker's full analysis (synthesis + signals + charts) as a PDF report or CSV data dump.

### 18. Dark mode `[ux]`
Add a dark/light theme toggle. Tailwind makes this straightforward with `dark:` variant classes.

### 19. Backtest recommendations `[feature]`
Track historical recommendations vs actual price movement. Show a "hit rate" — how often buy/hold/sell signals were correct over 30/90/180 days.

---

## Dependency on Each Other

```
[5. Remove dead Yahoo scraper]
        ↓
[7. Migrate to yfinance] ← required before →  [8. UK market support]
        ↓                                              ↓
[8a. Market-aware ticker model]              [8b. RNS scraper]
        ↓                                              ↓
[8d. Route data sources by market] ←──────── [8c. UK sector ETFs]
```

```
[2. Wire up scrape cache] → [11. Cache LLM responses]
```

```
[3. Rate limiting] — independent, do anytime
[1. Score validation] — independent, do anytime
[6. Selective refresh] — independent, do anytime
```

---

## How to Contribute

1. Pick an item from this list
2. Create a branch: `feature/<short-name>` or `fix/<short-name>`
3. Implement and test
4. Open a PR referencing the TODO item number (e.g., "Implements TODO #6")
5. Check off the item once merged

Each P0/P1 item is designed to be a self-contained unit of work that one person can tackle in a single session using a git worktree for parallel development.
