CATEGORY_WEIGHTS = {
    "fundamentals": 0.20,
    "analyst_consensus": 0.15,
    "insider_activity": 0.10,
    "technicals": 0.20,
    "sentiment": 0.10,
    "sector_context": 0.10,
    "risk_assessment": 0.15,
}


def weighted_score(signal_scores: dict[str, float]) -> float:
    """Calculate weighted average score from individual signal scores."""
    total_weight = 0
    weighted_sum = 0
    for category, score in signal_scores.items():
        weight = CATEGORY_WEIGHTS.get(category, 0.1)
        weighted_sum += score * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 2)


def score_to_recommendation(score: float) -> str:
    if score >= 3.0:
        return "buy"
    elif score <= -3.0:
        return "sell"
    return "hold"
