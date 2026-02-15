"""SQLAlchemy Table metadata for Alembic autogenerate.

This module is only used by alembic/env.py for schema diffing.
The application uses raw SQL queries via aiosqlite — it never imports this module.
"""

from sqlalchemy import (
    Column,
    DateTime,
    Integer,
    MetaData,
    REAL,
    Table,
    Text,
    ForeignKey,
    Index,
    text,
)

metadata = MetaData()

tickers = Table(
    "tickers",
    metadata,
    Column("symbol", Text, primary_key=True),
    Column("name", Text, nullable=False),
    Column("sector", Text),
    Column("market", Text, server_default=text("'US'")),
    Column("resolved_symbol", Text),
    Column("added_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
)

analyses = Table(
    "analyses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "symbol",
        Text,
        ForeignKey("tickers.symbol", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("category", Text, nullable=False),
    Column("score", REAL, nullable=False),
    Column("confidence", Text, nullable=False),
    Column("narrative", Text),
    Column("raw_data", Text),
    Column("input_hash", Text),
    Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
)

syntheses = Table(
    "syntheses",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "symbol",
        Text,
        ForeignKey("tickers.symbol", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("overall_score", REAL, nullable=False),
    Column("recommendation", Text, nullable=False),
    Column("narrative", Text),
    Column("signal_scores", Text),
    Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
)

scrape_cache = Table(
    "scrape_cache",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("url", Text, nullable=False),
    Column("content", Text),
    Column("fetched_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
    Column("expires_at", DateTime, nullable=False),
)

recommendations = Table(
    "recommendations",
    metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column(
        "symbol",
        Text,
        ForeignKey("tickers.symbol", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("recommendation", Text, nullable=False),
    Column("overall_score", REAL, nullable=False),
    Column("price_at_rec", REAL),
    Column("created_at", DateTime, server_default=text("CURRENT_TIMESTAMP")),
)

Index("idx_analyses_symbol", analyses.c.symbol)
Index("idx_syntheses_symbol", syntheses.c.symbol)
Index("idx_scrape_cache_url", scrape_cache.c.url)
Index("idx_recommendations_symbol", recommendations.c.symbol)
Index("idx_recommendations_created_at", recommendations.c.created_at)
