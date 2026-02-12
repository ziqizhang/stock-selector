import pytest
from src.analysis.scoring import weighted_score, score_to_recommendation, DEFAULT_CATEGORY_WEIGHTS


# --- DEFAULT_CATEGORY_WEIGHTS tests ---

def test_category_weights_has_all_expected_keys():
    expected = {
        "fundamentals", "analyst_consensus", "insider_activity",
        "technicals", "sentiment", "sector_context", "risk_assessment",
    }
    assert set(DEFAULT_CATEGORY_WEIGHTS.keys()) == expected


def test_category_weights_sum_to_one():
    assert round(sum(DEFAULT_CATEGORY_WEIGHTS.values()), 10) == 1.0


# --- weighted_score tests ---

def test_weighted_score_all_categories():
    scores = {k: 5.0 for k in DEFAULT_CATEGORY_WEIGHTS}
    assert weighted_score(scores) == 5.0


def test_weighted_score_varied_scores():
    scores = {
        "fundamentals": 8.0,
        "analyst_consensus": 6.0,
        "insider_activity": 2.0,
        "technicals": 7.0,
        "sentiment": -3.0,
        "sector_context": 4.0,
        "risk_assessment": 5.0,
    }
    expected = sum(
        scores[k] * DEFAULT_CATEGORY_WEIGHTS[k] for k in scores
    ) / sum(DEFAULT_CATEGORY_WEIGHTS[k] for k in scores)
    assert weighted_score(scores) == round(expected, 2)


def test_weighted_score_subset_of_categories():
    scores = {"fundamentals": 10.0, "technicals": -10.0}
    w_fund = DEFAULT_CATEGORY_WEIGHTS["fundamentals"]
    w_tech = DEFAULT_CATEGORY_WEIGHTS["technicals"]
    expected = (10.0 * w_fund + -10.0 * w_tech) / (w_fund + w_tech)
    assert weighted_score(scores) == round(expected, 2)


def test_weighted_score_empty_dict():
    assert weighted_score({}) == 0.0


def test_weighted_score_unknown_category_uses_fallback():
    scores = {"unknown_cat": 6.0}
    # fallback weight is 0.1
    assert weighted_score(scores) == 6.0


def test_weighted_score_rounds_to_two_decimals():
    # Use values that would produce more than 2 decimal places
    scores = {"fundamentals": 3.33, "technicals": 6.67}
    result = weighted_score(scores)
    assert result == round(result, 2)


# --- score_to_recommendation tests ---

def test_recommendation_buy():
    assert score_to_recommendation(5.0) == "buy"


def test_recommendation_sell():
    assert score_to_recommendation(-5.0) == "sell"


def test_recommendation_hold():
    assert score_to_recommendation(0.0) == "hold"


def test_recommendation_buy_boundary():
    assert score_to_recommendation(3.0) == "buy"


def test_recommendation_sell_boundary():
    assert score_to_recommendation(-3.0) == "sell"


def test_recommendation_hold_just_below_buy():
    assert score_to_recommendation(2.99) == "hold"


def test_recommendation_hold_just_above_sell():
    assert score_to_recommendation(-2.99) == "hold"
