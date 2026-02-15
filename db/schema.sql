-- NOTE: This file is kept for reference only.
-- Schema changes are now managed by Alembic migrations in alembic/versions/.
-- Run: alembic upgrade head

CREATE TABLE IF NOT EXISTS tickers (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    sector TEXT,
    market TEXT DEFAULT 'US',
    resolved_symbol TEXT,
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
    input_hash TEXT,
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

CREATE TABLE IF NOT EXISTS recommendations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
    recommendation TEXT NOT NULL,
    overall_score REAL NOT NULL,
    price_at_rec REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analyses_symbol ON analyses(symbol);
CREATE INDEX IF NOT EXISTS idx_syntheses_symbol ON syntheses(symbol);
CREATE INDEX IF NOT EXISTS idx_scrape_cache_url ON scrape_cache(url);
CREATE INDEX IF NOT EXISTS idx_recommendations_symbol ON recommendations(symbol);
CREATE INDEX IF NOT EXISTS idx_recommendations_created_at ON recommendations(created_at);
