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
