"""baseline schema

Revision ID: 0001
Revises:
Create Date: 2025-01-01 00:00:00.000000
"""
from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE IF NOT EXISTS tickers (
            symbol TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            sector TEXT,
            added_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
            category TEXT NOT NULL,
            score REAL NOT NULL,
            confidence TEXT NOT NULL,
            narrative TEXT,
            raw_data TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS syntheses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            symbol TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
            overall_score REAL NOT NULL,
            recommendation TEXT NOT NULL,
            narrative TEXT,
            signal_scores TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS scrape_cache (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            content TEXT,
            fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            expires_at DATETIME NOT NULL
        )
    """)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_analyses_symbol ON analyses(symbol)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_syntheses_symbol ON syntheses(symbol)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_scrape_cache_url ON scrape_cache(url)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_scrape_cache_url")
    op.execute("DROP INDEX IF EXISTS idx_syntheses_symbol")
    op.execute("DROP INDEX IF EXISTS idx_analyses_symbol")
    op.execute("DROP TABLE IF EXISTS scrape_cache")
    op.execute("DROP TABLE IF EXISTS syntheses")
    op.execute("DROP TABLE IF EXISTS analyses")
    op.execute("DROP TABLE IF EXISTS tickers")
