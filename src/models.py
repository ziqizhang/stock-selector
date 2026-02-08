from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum


class Recommendation(str, Enum):
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"


class Confidence(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class SignalCategory(str, Enum):
    FUNDAMENTALS = "fundamentals"
    ANALYST_CONSENSUS = "analyst_consensus"
    INSIDER_ACTIVITY = "insider_activity"
    TECHNICALS = "technicals"
    SENTIMENT = "sentiment"
    SECTOR_CONTEXT = "sector_context"
    RISK_ASSESSMENT = "risk_assessment"


class TickerCreate(BaseModel):
    symbol: str
    name: str
    sector: str | None = None


class TickerResponse(BaseModel):
    symbol: str
    name: str
    sector: str | None
    added_at: str | None


class SignalResult(BaseModel):
    category: SignalCategory
    score: float = Field(ge=-10, le=10)
    confidence: Confidence
    narrative: str
    raw_data: dict


class SynthesisResult(BaseModel):
    overall_score: float = Field(ge=-10, le=10)
    recommendation: Recommendation
    narrative: str
    signal_scores: dict[str, float]


class DashboardRow(BaseModel):
    symbol: str
    name: str
    sector: str | None
    overall_score: float | None
    recommendation: str | None
    last_refreshed: str | None


class RefreshProgress(BaseModel):
    symbol: str
    step: str
    category: str | None = None
    done: bool = False
