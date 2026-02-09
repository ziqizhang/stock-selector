import json
import markdown
from contextlib import asynccontextmanager
from markupsafe import Markup
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pathlib import Path
from src.db import Database
from src.api.websocket import handle_refresh, handle_refresh_all, handle_refresh_selected

BASE_DIR = Path(__file__).parent.parent.parent
db = Database()


def md_to_html(text: str) -> Markup:
    """Convert markdown text to safe HTML."""
    if not text:
        return Markup("")
    return Markup(markdown.markdown(text, extensions=["extra", "tables"]))


@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init()
    yield
    await db.close()


app = FastAPI(lifespan=lifespan)
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.filters["markdown"] = md_to_html


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    rows = await db.get_dashboard_data()
    is_stale = await db.get_staleness()
    return templates.TemplateResponse("dashboard.html", {
        "request": request,
        "tickers": rows,
        "is_stale": is_stale,
    })


@app.post("/tickers")
async def add_ticker(symbol: str = Form(...), name: str = Form(...), sector: str = Form(None)):
    await db.add_ticker(symbol.upper(), name, sector)
    return RedirectResponse(url="/", status_code=303)


@app.post("/tickers/{symbol}/delete")
async def remove_ticker(symbol: str):
    await db.remove_ticker(symbol.upper())
    return RedirectResponse(url="/", status_code=303)


@app.get("/ticker/{symbol}", response_class=HTMLResponse)
async def ticker_detail(request: Request, symbol: str):
    ticker = await db.get_ticker(symbol.upper())
    if not ticker:
        return RedirectResponse(url="/")
    synthesis = await db.get_latest_synthesis(symbol.upper())
    analyses = await db.get_latest_analyses(symbol.upper())
    history = await db.get_synthesis_history(symbol.upper())
    signal_scores = {}
    if synthesis and synthesis.get("signal_scores"):
        signal_scores = json.loads(synthesis["signal_scores"])
    return templates.TemplateResponse("detail.html", {
        "request": request,
        "ticker": ticker,
        "synthesis": synthesis,
        "analyses": analyses,
        "history": history,
        "signal_scores": signal_scores,
    })


@app.websocket("/ws/refresh/{symbol}")
async def ws_refresh_ticker(websocket: WebSocket, symbol: str):
    await websocket.accept()
    try:
        await handle_refresh(websocket, symbol.upper(), db)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/refresh-all")
async def ws_refresh_all(websocket: WebSocket):
    await websocket.accept()
    try:
        await handle_refresh_all(websocket, db)
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/refresh-selected")
async def ws_refresh_selected(websocket: WebSocket):
    await websocket.accept()
    try:
        message = await websocket.receive_text()
        symbols = json.loads(message)
        if not isinstance(symbols, list) or not all(isinstance(s, str) for s in symbols):
            await websocket.close(code=1003, reason="Expected JSON array of strings")
            return
        if len(symbols) == 0:
            await websocket.send_text(json.dumps({"type": "all_done"}))
            await websocket.close()
            return
        await handle_refresh_selected(websocket, db, symbols)
    except (WebSocketDisconnect, json.JSONDecodeError):
        pass
