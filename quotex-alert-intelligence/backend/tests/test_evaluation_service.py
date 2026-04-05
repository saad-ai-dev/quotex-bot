"""
Evaluation service tests for determine_outcome.

ALERT-ONLY system -- tests verify that prediction outcome determination
works correctly for all direction/candle combinations. No financial
outcomes are involved.
"""

import pytest

from app.services.evaluation_service import EvaluationService
from app.core.constants import Outcome, Direction


# ---------------------------------------------------------------------------
# determine_outcome tests
# ---------------------------------------------------------------------------

def test_determine_outcome_up_bullish_win():
    """Predicted UP + actual bullish => WIN."""
    result = EvaluationService.determine_outcome(Direction.UP, "bullish")
    assert result == Outcome.WIN


def test_determine_outcome_up_bearish_loss():
    """Predicted UP + actual bearish => LOSS."""
    result = EvaluationService.determine_outcome(Direction.UP, "bearish")
    assert result == Outcome.LOSS


def test_determine_outcome_down_bearish_win():
    """Predicted DOWN + actual bearish => WIN."""
    result = EvaluationService.determine_outcome(Direction.DOWN, "bearish")
    assert result == Outcome.WIN


def test_determine_outcome_down_bullish_loss():
    """Predicted DOWN + actual bullish => LOSS."""
    result = EvaluationService.determine_outcome(Direction.DOWN, "bullish")
    assert result == Outcome.LOSS


def test_determine_outcome_doji_neutral():
    """Any prediction + doji candle => NEUTRAL."""
    result = EvaluationService.determine_outcome(Direction.UP, "doji")
    assert result == Outcome.NEUTRAL


def test_determine_outcome_neutral_candle():
    """Any prediction + neutral candle => NEUTRAL."""
    result = EvaluationService.determine_outcome(Direction.DOWN, "neutral")
    assert result == Outcome.NEUTRAL


def test_determine_outcome_none_unknown():
    """Any prediction + None actual direction => UNKNOWN."""
    result = EvaluationService.determine_outcome(Direction.UP, None)
    assert result == Outcome.UNKNOWN


def test_determine_outcome_no_trade_returns_unknown():
    """NO_TRADE prediction with any actual candle returns UNKNOWN.
    ALERT-ONLY: NO_TRADE means no directional prediction was made.
    """
    result = EvaluationService.determine_outcome(Direction.NO_TRADE, "bullish")
    assert result == Outcome.UNKNOWN
