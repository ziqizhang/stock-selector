"""Backtest engine: compare historical recommendations against actual price movement."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from src.db import Database
from src.scrapers.yfinance_provider import YFinanceProvider


HORIZONS = [30, 90, 180]  # days


@dataclass
class BacktestResult:
    """Result of evaluating a single recommendation."""
    id: int
    symbol: str
    name: str
    recommendation: str
    overall_score: float
    price_at_rec: float | None
    created_at: str
    outcomes: dict[int, dict]  # horizon -> {price_now, pct_change, correct}


@dataclass
class BacktestSummary:
    """Aggregate hit-rate statistics."""
    total: int = 0
    correct: int = 0
    results: list[BacktestResult] = field(default_factory=list)
    hit_rates: dict[int, dict] = field(default_factory=dict)  # horizon -> {total, correct, rate}


def _is_correct(recommendation: str, pct_change: float) -> bool:
    """Determine if a recommendation was correct given price movement.

    - buy: correct if price went up (pct_change > 0)
    - sell: correct if price went down (pct_change < 0)
    - hold: correct if price stayed within +/-5%
    """
    if recommendation == "buy":
        return pct_change > 0
    elif recommendation == "sell":
        return pct_change < 0
    else:  # hold
        return abs(pct_change) <= 5.0


async def run_backtest(
    db: Database,
    provider: YFinanceProvider,
    symbol: str | None = None,
) -> BacktestSummary:
    """Run backtest for all (or one ticker's) historical recommendations.

    Fetches recommendations from the DB, looks up current/historical prices
    via yfinance, and calculates hit rates at 30/90/180 day horizons.
    """
    recs = await db.get_recommendations(symbol=symbol)
    summary = BacktestSummary()

    # Initialise per-horizon counters
    for h in HORIZONS:
        summary.hit_rates[h] = {"total": 0, "correct": 0, "rate": 0.0}

    now = datetime.utcnow()

    for rec in recs:
        price_at_rec = rec.get("price_at_rec")
        if price_at_rec is None:
            continue

        rec_date = datetime.fromisoformat(rec["created_at"])
        ticker_row = await db.get_ticker(rec["symbol"])
        resolved = (ticker_row or {}).get("resolved_symbol") or rec["symbol"]

        outcomes: dict[int, dict] = {}

        for horizon in HORIZONS:
            target_date = rec_date + timedelta(days=horizon)
            if target_date > now:
                # Not enough time has passed for this horizon
                continue

            # Get price at the target date
            target_str = target_date.strftime("%Y-%m-%d")
            price_then = await provider.get_historical_price(resolved, target_str)
            if price_then is None:
                continue

            pct_change = (price_then - price_at_rec) / price_at_rec * 100
            correct = _is_correct(rec["recommendation"], pct_change)

            outcomes[horizon] = {
                "price_then": round(price_then, 2),
                "pct_change": round(pct_change, 2),
                "correct": correct,
            }

            summary.hit_rates[horizon]["total"] += 1
            if correct:
                summary.hit_rates[horizon]["correct"] += 1

        result = BacktestResult(
            id=rec["id"],
            symbol=rec["symbol"],
            name=rec.get("name", rec["symbol"]),
            recommendation=rec["recommendation"],
            overall_score=rec["overall_score"],
            price_at_rec=price_at_rec,
            created_at=rec["created_at"],
            outcomes=outcomes,
        )
        summary.results.append(result)

    # Calculate rates
    for h in HORIZONS:
        bucket = summary.hit_rates[h]
        if bucket["total"] > 0:
            bucket["rate"] = round(bucket["correct"] / bucket["total"] * 100, 1)

    summary.total = len(summary.results)
    summary.correct = sum(
        1 for r in summary.results
        if any(o.get("correct") for o in r.outcomes.values())
    )

    return summary
