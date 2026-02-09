import asyncio

import aiosqlite
from pathlib import Path

ALEMBIC_DIR = Path(__file__).resolve().parent.parent / "alembic"
ALEMBIC_INI = Path(__file__).resolve().parent.parent / "alembic.ini"


class Database:
    def __init__(self, db_path: str = "data/stock_selector.db"):
        self.db_path = db_path
        self.db: aiosqlite.Connection | None = None

    def _run_migrations(self) -> None:
        """Run Alembic migrations synchronously (called via ``asyncio.to_thread``)."""
        from alembic import command
        from alembic.config import Config

        cfg = Config(str(ALEMBIC_INI))
        cfg.set_main_option("script_location", str(ALEMBIC_DIR))
        cfg.set_main_option("sqlalchemy.url", f"sqlite:///{self.db_path}")
        command.upgrade(cfg, "head")

    async def init(self):
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(self._run_migrations)
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA foreign_keys = ON")

    async def close(self):
        if self.db:
            await self.db.close()

    async def add_ticker(
        self, symbol: str, name: str, sector: str | None = None,
        market: str = "US", resolved_symbol: str | None = None,
    ):
        await self.db.execute(
            "INSERT OR IGNORE INTO tickers (symbol, name, sector, market, resolved_symbol) VALUES (?, ?, ?, ?, ?)",
            (symbol.upper(), name, sector, market, resolved_symbol),
        )
        await self.db.commit()

    async def update_ticker_resolution(
        self, symbol: str, resolved_symbol: str, market: str,
    ):
        await self.db.execute(
            "UPDATE tickers SET resolved_symbol = ?, market = ? WHERE symbol = ?",
            (resolved_symbol, market, symbol.upper()),
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

    async def get_dashboard_data(self) -> list[dict]:
        cursor = await self.db.execute(
            """SELECT t.symbol, t.name, t.sector, t.market, t.added_at,
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
