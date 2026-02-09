"""Tests for Alembic migration lifecycle."""

import pytest
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

ALEMBIC_DIR = str(Path(__file__).resolve().parent.parent / "alembic")
ALEMBIC_INI = str(Path(__file__).resolve().parent.parent / "alembic.ini")


def _make_config(db_path: str) -> Config:
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("script_location", ALEMBIC_DIR)
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def test_upgrade_to_head_creates_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    cfg = _make_config(db_path)
    command.upgrade(cfg, "head")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        assert "tickers" in tables
        assert "analyses" in tables
        assert "syntheses" in tables
        assert "scrape_cache" in tables
        assert "alembic_version" in tables

        columns = {c["name"] for c in inspector.get_columns("tickers")}
        assert "market" in columns
        assert "resolved_symbol" in columns


def test_downgrade_to_base_drops_tables(tmp_path):
    db_path = str(tmp_path / "test.db")
    cfg = _make_config(db_path)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        inspector = inspect(conn)
        tables = inspector.get_table_names()
        # Only alembic_version should remain
        app_tables = {"tickers", "analyses", "syntheses", "scrape_cache"}
        assert app_tables.isdisjoint(set(tables))


def test_upgrade_is_idempotent(tmp_path):
    """Running upgrade head twice should not fail."""
    db_path = str(tmp_path / "test.db")
    cfg = _make_config(db_path)
    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # should not raise

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        inspector = inspect(conn)
        columns = {c["name"] for c in inspector.get_columns("tickers")}
        assert "market" in columns
        assert "resolved_symbol" in columns


def test_migration_0002_idempotent_on_existing_columns(tmp_path):
    """If columns already exist (from old schema.sql), 0002 still succeeds."""
    db_path = str(tmp_path / "test.db")
    engine = create_engine(f"sqlite:///{db_path}")

    # Simulate a DB created by the old schema.sql (with market + resolved_symbol)
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE tickers (
                symbol TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sector TEXT,
                market TEXT DEFAULT 'US',
                resolved_symbol TEXT,
                added_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE analyses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
                category TEXT NOT NULL, score REAL NOT NULL,
                confidence TEXT NOT NULL, narrative TEXT, raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE syntheses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                symbol TEXT NOT NULL REFERENCES tickers(symbol) ON DELETE CASCADE,
                overall_score REAL NOT NULL, recommendation TEXT NOT NULL,
                narrative TEXT, signal_scores TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("""
            CREATE TABLE scrape_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                url TEXT NOT NULL, content TEXT,
                fetched_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                expires_at DATETIME NOT NULL
            )
        """))
        conn.commit()

    # Now run migrations — should stamp and succeed without errors
    cfg = _make_config(db_path)
    command.upgrade(cfg, "head")

    with engine.connect() as conn:
        inspector = inspect(conn)
        columns = {c["name"] for c in inspector.get_columns("tickers")}
        assert "market" in columns
        assert "resolved_symbol" in columns
