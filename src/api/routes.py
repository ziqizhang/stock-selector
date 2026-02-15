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
from src.scrapers.yfinance_provider import YFinanceProvider
from src.analysis.scoring import SCORING_PRESETS, validate_weights, normalize_weights
from src.analysis.backtest import run_backtest, HORIZONS

BASE_DIR = Path(__file__).parent.parent.parent
db = Database()
yfinance_provider = YFinanceProvider()


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
async def add_ticker(
    symbol: str = Form(...),
    name: str = Form(...),
    sector: str = Form(None),
    market: str = Form("US"),
):
    symbol = symbol.upper()

    # Try to resolve symbol first to get the correct exchange suffix
    try:
        resolved_symbol, detected_market = yfinance_provider.resolve_symbol(
            symbol, preferred_market=market
        )
    except ValueError:
        # If resolution fails, we'll try with the raw symbol
        resolved_symbol = symbol
        detected_market = market

    # Auto-detect sector if not provided by user
    detected_sector: str | None = None
    if not sector:
        sector_info = await yfinance_provider.get_sector_info(resolved_symbol)
        detected_sector = sector_info.get("sector")
    else:
        detected_sector = sector

    await db.add_ticker(
        symbol, name, detected_sector, market=detected_market, resolved_symbol=resolved_symbol
    )
    return RedirectResponse(url="/", status_code=303)


@app.post("/tickers/{symbol}/delete")
async def remove_ticker(symbol: str):
    await db.remove_ticker(symbol.upper())
    return RedirectResponse(url="/", status_code=303)


@app.get("/api/company-info/{symbol}")
async def get_company_info(symbol: str, market: str = "US"):
    """Fetch company name and sector info from yfinance for auto-fill."""
    symbol = symbol.upper()
    
    try:
        # Try to resolve symbol first
        try:
            resolved_symbol, detected_market = yfinance_provider.resolve_symbol(
                symbol, preferred_market=market
            )
        except ValueError:
            resolved_symbol = symbol
            detected_market = market
        
        # Get ticker info
        ticker = yfinance_provider._get_ticker(resolved_symbol)
        info = ticker.info or {}
        
        # Extract company name (prefer longName, fall back to shortName)
        company_name = info.get("longName") or info.get("shortName") or ""
        
        # Get sector info
        sector_info = await yfinance_provider.get_sector_info(resolved_symbol)
        
        return {
            "symbol": symbol,
            "resolved_symbol": resolved_symbol,
            "market": detected_market,
            "name": company_name,
            "sector": sector_info.get("sector"),
            "industry": sector_info.get("industry"),
        }
    except Exception as e:
        return {
            "symbol": symbol,
            "resolved_symbol": symbol,
            "market": market,
            "name": "",
            "sector": None,
            "industry": None,
            "error": str(e),
        }


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


# Settings endpoints for configurable scoring weights
@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    """Render the settings page with current weights and presets."""
    current_weights = await db.get_scoring_weights()
    active_preset = await db.get_active_preset()
    
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "current_weights": current_weights,
        "active_preset": active_preset,
        "presets": SCORING_PRESETS,
    })


@app.get("/api/settings/weights")
async def get_weights():
    """Get current scoring weights."""
    weights = await db.get_scoring_weights()
    preset = await db.get_active_preset()
    return {
        "weights": weights,
        "preset": preset,
    }


@app.post("/api/settings/weights")
async def update_weights(request: Request):
    """Update scoring weights."""
    data = await request.json()
    weights = data.get("weights", {})
    
    # Validate weights
    is_valid, error_message = validate_weights(weights)
    if not is_valid:
        return {"success": False, "error": error_message}
    
    # Normalize weights to ensure they sum to exactly 1.0
    normalized_weights = normalize_weights(weights)
    
    # Save to database
    await db.set_scoring_weights(normalized_weights)
    await db.set_active_preset("custom")
    
    return {"success": True, "weights": normalized_weights}


@app.post("/api/settings/preset/{preset_name}")
async def apply_preset(preset_name: str):
    """Apply a scoring preset."""
    if preset_name not in SCORING_PRESETS:
        return {"success": False, "error": f"Unknown preset: {preset_name}"}
    
    preset = SCORING_PRESETS[preset_name]
    await db.set_scoring_weights(preset["weights"])
    await db.set_active_preset(preset_name)
    
    return {
        "success": True,
        "preset": preset_name,
        "weights": preset["weights"],
    }


@app.get("/api/settings/presets")
async def get_presets():
    """Get all available scoring presets."""
    return {
        "presets": {
            name: {
                "name": data["name"],
                "description": data["description"],
                "weights": data["weights"],
            }
            for name, data in SCORING_PRESETS.items()
        }
    }


@app.get("/backtest", response_class=HTMLResponse)
async def backtest_page(request: Request, symbol: str | None = None):
    """Display backtest results comparing past recommendations to actual price movement."""
    provider = YFinanceProvider()
    try:
        summary = await run_backtest(db, provider, symbol=symbol)
    finally:
        await provider.close()

    tickers = await db.list_tickers()

    return templates.TemplateResponse("backtest.html", {
        "request": request,
        "summary": summary,
        "horizons": HORIZONS,
        "selected_symbol": symbol,
        "tickers": tickers,
    })
