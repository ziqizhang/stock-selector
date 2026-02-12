# Default category weights (can be overridden via settings)
DEFAULT_CATEGORY_WEIGHTS = {
    "fundamentals": 0.20,
    "analyst_consensus": 0.15,
    "insider_activity": 0.10,
    "technicals": 0.20,
    "sentiment": 0.10,
    "sector_context": 0.10,
    "risk_assessment": 0.15,
}

# Preset configurations for different investment strategies
SCORING_PRESETS = {
    "balanced": {
        "name": "Balanced",
        "description": "Default balanced approach for general investing",
        "weights": DEFAULT_CATEGORY_WEIGHTS.copy(),
    },
    "growth": {
        "name": "Growth",
        "description": "Prioritizes fundamentals, analyst consensus, and technical momentum",
        "weights": {
            "fundamentals": 0.25,
            "analyst_consensus": 0.20,
            "insider_activity": 0.05,
            "technicals": 0.25,
            "sentiment": 0.10,
            "sector_context": 0.05,
            "risk_assessment": 0.10,
        },
    },
    "value": {
        "name": "Value",
        "description": "Focuses on fundamentals, risk assessment, and insider confidence",
        "weights": {
            "fundamentals": 0.30,
            "analyst_consensus": 0.10,
            "insider_activity": 0.15,
            "technicals": 0.10,
            "sentiment": 0.05,
            "sector_context": 0.10,
            "risk_assessment": 0.20,
        },
    },
    "income": {
        "name": "Income/Dividend",
        "description": "Emphasizes fundamentals stability and risk assessment for dividend stocks",
        "weights": {
            "fundamentals": 0.30,
            "analyst_consensus": 0.10,
            "insider_activity": 0.10,
            "technicals": 0.05,
            "sentiment": 0.10,
            "sector_context": 0.15,
            "risk_assessment": 0.20,
        },
    },
    "momentum": {
        "name": "Momentum",
        "description": "Weights technicals and sentiment heavily for trend-following",
        "weights": {
            "fundamentals": 0.10,
            "analyst_consensus": 0.20,
            "insider_activity": 0.05,
            "technicals": 0.35,
            "sentiment": 0.15,
            "sector_context": 0.05,
            "risk_assessment": 0.10,
        },
    },
}


def weighted_score(signal_scores: dict[str, float], weights: dict[str, float] | None = None) -> float:
    """Calculate weighted average score from individual signal scores.
    
    Args:
        signal_scores: Dict mapping category names to their scores
        weights: Optional custom weights. If None, uses DEFAULT_CATEGORY_WEIGHTS.
    
    Returns:
        Weighted average score rounded to 2 decimal places
    """
    category_weights = weights if weights is not None else DEFAULT_CATEGORY_WEIGHTS
    
    total_weight = 0
    weighted_sum = 0
    for category, score in signal_scores.items():
        weight = category_weights.get(category, 0.1)
        weighted_sum += score * weight
        total_weight += weight
    if total_weight == 0:
        return 0.0
    return round(weighted_sum / total_weight, 2)


def score_to_recommendation(score: float) -> str:
    """Convert numeric score to buy/hold/sell recommendation."""
    if score >= 3.0:
        return "buy"
    elif score <= -3.0:
        return "sell"
    return "hold"


def validate_weights(weights: dict[str, float]) -> tuple[bool, str]:
    """Validate that weights sum to approximately 1.0 (100%).
    
    Args:
        weights: Dict mapping category names to weight values
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    required_categories = set(DEFAULT_CATEGORY_WEIGHTS.keys())
    provided_categories = set(weights.keys())
    
    # Check all required categories are present
    missing = required_categories - provided_categories
    if missing:
        return False, f"Missing categories: {', '.join(missing)}"
    
    # Check no extra categories
    extra = provided_categories - required_categories
    if extra:
        return False, f"Unknown categories: {', '.join(extra)}"
    
    # Check all weights are positive numbers
    for category, weight in weights.items():
        if not isinstance(weight, (int, float)):
            return False, f"Weight for {category} must be a number"
        if weight < 0:
            return False, f"Weight for {category} cannot be negative"
    
    # Check sum is approximately 1.0 (allowing small floating point误差)
    total = sum(weights.values())
    if not (0.99 <= total <= 1.01):
        return False, f"Weights must sum to 100% (currently {total * 100:.1f}%)"
    
    return True, ""


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    """Normalize weights so they sum exactly to 1.0."""
    total = sum(weights.values())
    if total == 0:
        return DEFAULT_CATEGORY_WEIGHTS.copy()
    return {k: round(v / total, 4) for k, v in weights.items()}
