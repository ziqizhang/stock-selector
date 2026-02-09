import logging
from src.analysis.engine import _validate_signal_result


def test_score_within_range_unchanged():
    result = _validate_signal_result({"score": 5, "confidence": "high"})
    assert result["score"] == 5
    assert result["confidence"] == "high"


def test_score_above_max_clamped():
    result = _validate_signal_result({"score": 25, "confidence": "medium"})
    assert result["score"] == 10


def test_score_below_min_clamped():
    result = _validate_signal_result({"score": -15, "confidence": "low"})
    assert result["score"] == -10


def test_boundary_scores_unchanged():
    assert _validate_signal_result({"score": 10})["score"] == 10
    assert _validate_signal_result({"score": -10})["score"] == -10


def test_missing_score_defaults_to_zero():
    result = _validate_signal_result({"confidence": "high"})
    assert result["score"] == 0


def test_invalid_confidence_defaults_to_low():
    result = _validate_signal_result({"score": 3, "confidence": "very_high"})
    assert result["confidence"] == "low"


def test_missing_confidence_defaults_to_low():
    result = _validate_signal_result({"score": 3})
    assert result["confidence"] == "low"


def test_valid_confidence_values_preserved():
    for level in ("low", "medium", "high"):
        result = _validate_signal_result({"score": 0, "confidence": level})
        assert result["confidence"] == level


def test_original_dict_not_mutated():
    original = {"score": 50, "confidence": "invalid", "narrative": "test"}
    result = _validate_signal_result(original)
    assert original["score"] == 50
    assert original["confidence"] == "invalid"
    assert result["score"] == 10
    assert result["confidence"] == "low"
    assert result["narrative"] == "test"


def test_clamping_logs_warning(caplog):
    with caplog.at_level(logging.WARNING):
        _validate_signal_result({"score": 20, "confidence": "high"})
    assert "out of range" in caplog.text


def test_invalid_confidence_logs_warning(caplog):
    with caplog.at_level(logging.WARNING):
        _validate_signal_result({"score": 5, "confidence": "extreme"})
    assert "Invalid confidence" in caplog.text
