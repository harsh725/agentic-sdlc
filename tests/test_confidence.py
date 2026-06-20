"""Confidence formula + the auto-merge predicate (plan §6.2, §7)."""

from __future__ import annotations

import pytest

from agentic_sdlc.confidence import (
    DEFAULT_WEIGHTS,
    ConfidenceInputs,
    compute_confidence,
    should_auto_merge,
)
from agentic_sdlc.contracts import RiskLevel

STRONG = ConfidenceInputs(
    reviewer_approve=3,
    reviewer_refute=0,
    reviewer_n=3,
    diff_coverage_pct=95,
    mutation_total=40,
    mutation_survived=2,
    blast_lines=40,
)
WEAK = ConfidenceInputs(
    reviewer_approve=2,
    reviewer_refute=1,
    reviewer_n=3,
    diff_coverage_pct=55,
    mutation_total=40,
    mutation_survived=18,
    blast_lines=600,
)


def test_weights_sum_to_one() -> None:
    assert abs(sum(DEFAULT_WEIGHTS.values()) - 1.0) < 1e-9


def test_strong_beats_weak() -> None:
    assert compute_confidence(STRONG) > compute_confidence(WEAK)


def test_strong_is_high_confidence() -> None:
    assert compute_confidence(STRONG) >= 0.9


def test_score_in_unit_interval() -> None:
    for inp in (STRONG, WEAK, ConfidenceInputs()):
        assert 0.0 <= compute_confidence(inp) <= 1.0


def test_auto_merge_requires_all_three() -> None:
    strong = compute_confidence(STRONG)
    weak = compute_confidence(WEAK)
    # strong + low risk + green -> merge
    assert should_auto_merge(gates_green=True, confidence=strong, risk_level=RiskLevel.LOW)
    # high risk never merges regardless of confidence
    assert not should_auto_merge(gates_green=True, confidence=strong, risk_level=RiskLevel.HIGH)
    # red gates never merge
    assert not should_auto_merge(gates_green=False, confidence=strong, risk_level=RiskLevel.LOW)
    # weak confidence escalates
    assert not should_auto_merge(gates_green=True, confidence=weak, risk_level=RiskLevel.LOW)


def test_zero_weights_rejected() -> None:
    with pytest.raises(ValueError, match="positive"):
        compute_confidence(STRONG, weights={"reviewer_agreement": 0.0})
