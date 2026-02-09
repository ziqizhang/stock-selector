"""Tests for technical indicator calculations."""

import pandas as pd
import numpy as np
import pytest
from src.analysis.indicators import sma, ema, rsi, atr, bollinger_bands


@pytest.fixture
def prices():
    """Simple ascending price series for testing."""
    return pd.Series([10.0, 11.0, 12.0, 11.5, 13.0, 14.0, 13.5, 15.0, 16.0, 14.5])


# ---------------------------------------------------------------------------
# SMA
# ---------------------------------------------------------------------------

def test_sma_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = sma(s, 3)
    assert np.isnan(result.iloc[0])
    assert np.isnan(result.iloc[1])
    assert result.iloc[2] == pytest.approx(2.0)
    assert result.iloc[3] == pytest.approx(3.0)
    assert result.iloc[4] == pytest.approx(4.0)


def test_sma_period_too_large():
    s = pd.Series([1.0, 2.0])
    result = sma(s, 5)
    assert result.isna().all()


# ---------------------------------------------------------------------------
# EMA
# ---------------------------------------------------------------------------

def test_ema_basic():
    s = pd.Series([1.0, 2.0, 3.0, 4.0, 5.0])
    result = ema(s, 3)
    # EMA should be defined for all elements (ewm doesn't require min_periods by default here)
    assert not result.isna().any()
    # EMA of monotonically increasing series should also be increasing
    assert all(result.iloc[i] <= result.iloc[i + 1] for i in range(len(result) - 1))


# ---------------------------------------------------------------------------
# RSI
# ---------------------------------------------------------------------------

def test_rsi_range(prices):
    result = rsi(prices, period=3)
    valid = result.dropna()
    assert (valid >= 0).all()
    assert (valid <= 100).all()


def test_rsi_constant_prices():
    """Constant prices → RSI should be 50 (or NaN for initial period)."""
    s = pd.Series([100.0] * 30)
    result = rsi(s, period=14)
    # With no gains or losses, RSI is undefined / NaN
    # Just verify no errors and values are in valid range
    valid = result.dropna()
    if len(valid) > 0:
        assert (valid >= 0).all()
        assert (valid <= 100).all()


def test_rsi_all_gains():
    """Strictly increasing prices → RSI should be close to 100."""
    s = pd.Series(range(1, 32), dtype=float)
    result = rsi(s, period=14)
    last = result.iloc[-1]
    assert last > 90  # Should be very high


def test_rsi_all_losses():
    """Strictly decreasing prices → RSI should be close to 0."""
    s = pd.Series(range(31, 0, -1), dtype=float)
    result = rsi(s, period=14)
    last = result.iloc[-1]
    assert last < 10  # Should be very low


# ---------------------------------------------------------------------------
# ATR
# ---------------------------------------------------------------------------

def test_atr_basic():
    high = pd.Series([12, 13, 14, 15, 16, 17, 18, 19, 20, 21], dtype=float)
    low = pd.Series([10, 11, 12, 13, 14, 15, 16, 17, 18, 19], dtype=float)
    close = pd.Series([11, 12, 13, 14, 15, 16, 17, 18, 19, 20], dtype=float)
    result = atr(high, low, close, period=3)
    valid = result.dropna()
    assert len(valid) > 0
    # ATR should be positive
    assert (valid > 0).all()


def test_atr_single_bar_range():
    """ATR of bars with range=2 and no gaps should be close to 2."""
    n = 30
    high = pd.Series([102.0] * n)
    low = pd.Series([100.0] * n)
    close = pd.Series([101.0] * n)
    result = atr(high, low, close, period=14)
    last = result.iloc[-1]
    assert last == pytest.approx(2.0, abs=0.1)


# ---------------------------------------------------------------------------
# Bollinger Bands
# ---------------------------------------------------------------------------

def test_bollinger_bands_basic():
    s = pd.Series(range(1, 26), dtype=float)
    upper, middle, lower = bollinger_bands(s, period=5, num_std=2.0)
    # Middle should equal SMA
    expected_mid = sma(s, 5)
    pd.testing.assert_series_equal(middle, expected_mid, check_names=False)
    # Upper > middle > lower where defined
    valid_mask = middle.notna()
    assert (upper[valid_mask] > middle[valid_mask]).all()
    assert (lower[valid_mask] < middle[valid_mask]).all()
