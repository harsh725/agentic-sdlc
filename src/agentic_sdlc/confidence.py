"""Confidence scoring — the linchpin of 'avoid manual review' (plan §6.2).

A normalized weighted score in [0, 1] computed from objective signals only. An
undefined 'confidence' makes auto-merge theater, so the formula, normalization,
and the auto-merge predicate are all explicit here. Weights start equal and are
calibrated against a labeled diff corpus in ``benchmarks/`` before the threshold
is loosened (see plan §6.2 and §12).
"""

from __future__ import annotations

from dataclasses import dataclass

from agentic_sdlc.contracts import RiskLevel

# Conservative default. Auto-merge only at >= this AND zero risk flags. Loosen
# only after the threshold is calibrated against a labeled holdout set.
DEFAULT_AUTO_MERGE_THRESHOLD = 0.90

DEFAULT_WEIGHTS: dict[str, float] = {
    "reviewer_agreement": 0.35,
    "diff_coverage": 0.20,
    "mutation_score": 0.20,
    "blast_radius": 0.15,
    "defect_density": 0.10,
}


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass
class ConfidenceInputs:
    """Raw, objective signals feeding the confidence score."""

    reviewer_approve: int = 0
    reviewer_refute: int = 0
    reviewer_n: int = 0

    diff_coverage_pct: float = 0.0  # 0..100
    coverage_target_pct: float = 80.0

    mutation_survived: int = 0
    mutation_total: int = 0

    blast_lines: int = 0
    blast_critical_files: int = 0
    blast_cap: float = 800.0  # lines+weighted-files at which blast term -> 0

    defect_density: float = 0.0  # escape-defects per touched file, historical
    defect_density_cap: float = 1.0

    def signals(self) -> dict[str, float]:
        n = max(self.reviewer_n, 1)
        agreement = _clamp01((self.reviewer_approve - self.reviewer_refute + n) / (2 * n))
        coverage = _clamp01(self.diff_coverage_pct / max(self.coverage_target_pct, 1e-9))
        if self.mutation_total > 0:
            mutation = _clamp01(1 - self.mutation_survived / self.mutation_total)
        else:
            mutation = 0.0  # no mutation data -> no credit (conservative)
        blast = self.blast_lines + 5 * self.blast_critical_files
        blast_term = _clamp01(1 - min(blast / max(self.blast_cap, 1e-9), 1.0))
        density_term = _clamp01(
            1 - min(self.defect_density / max(self.defect_density_cap, 1e-9), 1.0)
        )
        return {
            "reviewer_agreement": agreement,
            "diff_coverage": coverage,
            "mutation_score": mutation,
            "blast_radius": blast_term,
            "defect_density": density_term,
        }


def compute_confidence(inputs: ConfidenceInputs, weights: dict[str, float] | None = None) -> float:
    """Weighted sum of normalized signals, in [0, 1]."""
    w = weights or DEFAULT_WEIGHTS
    total_w = sum(w.values())
    if total_w <= 0:
        raise ValueError("confidence weights must sum to a positive number")
    signals = inputs.signals()
    score = sum(w.get(k, 0.0) * v for k, v in signals.items())
    return _clamp01(score / total_w)


def should_auto_merge(
    *,
    gates_green: bool,
    confidence: float,
    risk_level: RiskLevel,
    threshold: float = DEFAULT_AUTO_MERGE_THRESHOLD,
) -> bool:
    """Auto-merge iff gates green AND confidence >= threshold AND risk is LOW.

    Fail closed: any other combination escalates to a human (plan §7).
    """
    return gates_green and confidence >= threshold and risk_level is RiskLevel.LOW
