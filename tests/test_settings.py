"""Tests for configurable scoring weights (Issue #12)."""

import pytest
import pytest_asyncio
import json
from fastapi.testclient import TestClient
from src.api.routes import app
from src.db import Database
from src.analysis.scoring import (
    weighted_score,
    score_to_recommendation,
    validate_weights,
    normalize_weights,
    DEFAULT_CATEGORY_WEIGHTS,
    SCORING_PRESETS,
)


@pytest_asyncio.fixture
async def db(tmp_path):
    """Create a test database with initialized schema."""
    database = Database(str(tmp_path / "test.db"))
    await database.init()
    yield database
    await database.close()


class TestWeightValidation:
    """Test weight validation functions."""

    def test_validate_weights_valid(self):
        """Test validation passes for valid weights."""
        weights = DEFAULT_CATEGORY_WEIGHTS.copy()
        is_valid, error = validate_weights(weights)
        assert is_valid is True
        assert error == ""

    def test_validate_weights_missing_category(self):
        """Test validation fails when category is missing."""
        weights = {k: v for k, v in DEFAULT_CATEGORY_WEIGHTS.items() if k != "fundamentals"}
        is_valid, error = validate_weights(weights)
        assert is_valid is False
        assert "Missing categories" in error

    def test_validate_weights_extra_category(self):
        """Test validation fails with unknown category."""
        weights = {**DEFAULT_CATEGORY_WEIGHTS, "unknown_category": 0.1}
        is_valid, error = validate_weights(weights)
        assert is_valid is False
        assert "Unknown categories" in error

    def test_validate_weights_negative(self):
        """Test validation fails with negative weight."""
        weights = DEFAULT_CATEGORY_WEIGHTS.copy()
        weights["fundamentals"] = -0.1
        is_valid, error = validate_weights(weights)
        assert is_valid is False
        assert "cannot be negative" in error

    def test_validate_weights_sum_not_100(self):
        """Test validation fails when weights don't sum to 100%."""
        weights = {k: v * 0.5 for k, v in DEFAULT_CATEGORY_WEIGHTS.items()}  # Sum to 50%
        is_valid, error = validate_weights(weights)
        assert is_valid is False
        assert "must sum to 100%" in error

    def test_validate_weights_tolerance(self):
        """Test validation allows small floating point误差."""
        weights = DEFAULT_CATEGORY_WEIGHTS.copy()
        weights["fundamentals"] += 0.005  # Make sum 100.5%
        is_valid, error = validate_weights(weights)
        assert is_valid is True  # Should pass with tolerance


class TestWeightNormalization:
    """Test weight normalization."""

    def test_normalize_weights(self):
        """Test weights are normalized to sum to 1.0."""
        weights = {k: 1.0 for k in DEFAULT_CATEGORY_WEIGHTS.keys()}  # Equal weights
        normalized = normalize_weights(weights)
        total = sum(normalized.values())
        assert abs(total - 1.0) < 0.001  # Allow small floating point误差

    def test_normalize_weights_zero_total(self):
        """Test normalization falls back to defaults when total is zero."""
        weights = {k: 0 for k in DEFAULT_CATEGORY_WEIGHTS.keys()}
        normalized = normalize_weights(weights)
        assert normalized == DEFAULT_CATEGORY_WEIGHTS


class TestWeightedScore:
    """Test weighted score calculation."""

    def test_weighted_score_with_defaults(self):
        """Test score calculation with default weights."""
        signal_scores = {
            "fundamentals": 5.0,
            "analyst_consensus": 3.0,
            "insider_activity": 2.0,
            "technicals": 4.0,
            "sentiment": 1.0,
            "sector_context": 0.0,
            "risk_assessment": -2.0,
        }
        score = weighted_score(signal_scores)
        assert isinstance(score, float)
        assert -10 <= score <= 10

    def test_weighted_score_with_custom_weights(self):
        """Test score calculation with custom weights."""
        signal_scores = {
            "fundamentals": 5.0,
            "analyst_consensus": 3.0,
        }
        custom_weights = {
            "fundamentals": 0.7,
            "analyst_consensus": 0.3,
        }
        score = weighted_score(signal_scores, weights=custom_weights)
        expected = round(5.0 * 0.7 + 3.0 * 0.3, 2)
        assert score == expected

    def test_weighted_score_empty(self):
        """Test score with empty signal scores."""
        score = weighted_score({})
        assert score == 0.0


class TestScoreToRecommendation:
    """Test recommendation conversion."""

    def test_buy_recommendation(self):
        """Test buy recommendation for high scores."""
        assert score_to_recommendation(5.0) == "buy"
        assert score_to_recommendation(3.0) == "buy"
        assert score_to_recommendation(10.0) == "buy"

    def test_sell_recommendation(self):
        """Test sell recommendation for low scores."""
        assert score_to_recommendation(-5.0) == "sell"
        assert score_to_recommendation(-3.0) == "sell"
        assert score_to_recommendation(-10.0) == "sell"

    def test_hold_recommendation(self):
        """Test hold recommendation for neutral scores."""
        assert score_to_recommendation(0.0) == "hold"
        assert score_to_recommendation(2.9) == "hold"
        assert score_to_recommendation(-2.9) == "hold"


class TestScoringPresets:
    """Test scoring presets."""

    def test_all_presets_have_required_categories(self):
        """Test all presets include all required categories."""
        required_categories = set(DEFAULT_CATEGORY_WEIGHTS.keys())
        for preset_name, preset_data in SCORING_PRESETS.items():
            preset_categories = set(preset_data["weights"].keys())
            assert preset_categories == required_categories, f"Preset {preset_name} missing categories"

    def test_all_presets_sum_to_100(self):
        """Test all preset weights sum to 100%."""
        for preset_name, preset_data in SCORING_PRESETS.items():
            total = sum(preset_data["weights"].values())
            assert abs(total - 1.0) < 0.01, f"Preset {preset_name} weights sum to {total}"

    def test_preset_structure(self):
        """Test all presets have required fields."""
        for preset_name, preset_data in SCORING_PRESETS.items():
            assert "name" in preset_data
            assert "description" in preset_data
            assert "weights" in preset_data
            assert isinstance(preset_data["weights"], dict)


class TestDatabaseSettings:
    """Test database settings methods."""

    @pytest.mark.asyncio
    async def test_get_scoring_weights_default(self, db):
        """Test getting default weights when no settings exist."""
        weights = await db.get_scoring_weights()
        assert weights == DEFAULT_CATEGORY_WEIGHTS

    @pytest.mark.asyncio
    async def test_set_and_get_scoring_weights(self, db):
        """Test saving and retrieving custom weights."""
        custom_weights = {
            "fundamentals": 0.30,
            "analyst_consensus": 0.20,
            "insider_activity": 0.05,
            "technicals": 0.25,
            "sentiment": 0.10,
            "sector_context": 0.05,
            "risk_assessment": 0.05,
        }
        await db.set_scoring_weights(custom_weights)
        
        retrieved_weights = await db.get_scoring_weights()
        assert retrieved_weights == custom_weights

    @pytest.mark.asyncio
    async def test_get_active_preset_default(self, db):
        """Test getting active preset when none set."""
        preset = await db.get_active_preset()
        assert preset is None

    @pytest.mark.asyncio
    async def test_set_and_get_active_preset(self, db):
        """Test saving and retrieving active preset."""
        await db.set_active_preset("growth")
        preset = await db.get_active_preset()
        assert preset == "growth"

    @pytest.mark.asyncio
    async def test_settings_persistence(self, db):
        """Test that settings persist across multiple operations."""
        # Set weights
        await db.set_scoring_weights(SCORING_PRESETS["growth"]["weights"])
        await db.set_active_preset("growth")
        
        # Retrieve and verify
        weights = await db.get_scoring_weights()
        preset = await db.get_active_preset()
        
        assert weights == SCORING_PRESETS["growth"]["weights"]
        assert preset == "growth"


class TestSettingsIntegration:
    """Integration tests for settings feature."""

    @pytest.mark.asyncio
    async def test_weighted_score_uses_db_weights(self, db):
        """Test that weighted_score can use weights from database."""
        # Set custom weights
        custom_weights = {
            "fundamentals": 0.50,
            "analyst_consensus": 0.10,
            "insider_activity": 0.10,
            "technicals": 0.10,
            "sentiment": 0.10,
            "sector_context": 0.05,
            "risk_assessment": 0.05,
        }
        await db.set_scoring_weights(custom_weights)
        
        # Get weights from DB and use them
        weights = await db.get_scoring_weights()
        signal_scores = {
            "fundamentals": 10.0,
            "analyst_consensus": 0.0,
            "insider_activity": 0.0,
            "technicals": 0.0,
            "sentiment": 0.0,
            "sector_context": 0.0,
            "risk_assessment": 0.0,
        }
        
        score = weighted_score(signal_scores, weights=weights)
        # Should be heavily weighted toward fundamentals (10 * 0.5 = 5.0)
        assert score == 5.0
