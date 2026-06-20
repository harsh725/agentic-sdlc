"""Adversarial reviewer ensemble + reliability-weighted vote (plan §6.3).

N independent reviewers, heterogeneous in model and prompt, each prompted to
REFUTE. A ``reject`` must cite a concrete, checkable finding (file + line +
claim) or it is discarded as noise — this stops the adversarial prompt from
reflexively blocking every PR. Aggregation is a reliability-weighted majority,
not a plain majority (which collapses when >=50% of reviewers share a bias).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Verdict(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"


@dataclass
class Finding:
    file: str
    line: int | None
    claim: str
    severity: str = "minor"  # minor | major | critical

    @property
    def is_concrete(self) -> bool:
        return bool(self.file) and bool(self.claim.strip())


@dataclass
class ReviewerVerdict:
    reviewer_id: str
    model: str
    lens: str  # correctness | security | simplicity ...
    verdict: Verdict
    findings: list[Finding] = field(default_factory=list)

    def effective_verdict(self) -> Verdict:
        """A reject with no concrete finding is downgraded to approve (noise)."""
        if self.verdict is Verdict.REJECT and not any(f.is_concrete for f in self.findings):
            return Verdict.APPROVE
        return self.verdict


@dataclass
class EnsembleDecision:
    approved: bool
    approve_weight: float
    reject_weight: float
    n: int
    concrete_findings: list[Finding]
    blocking_findings: list[Finding]


def weighted_vote(
    verdicts: list[ReviewerVerdict],
    reliability: dict[str, float] | None = None,
) -> EnsembleDecision:
    """Reliability-weighted majority over effective verdicts.

    ``reliability`` maps reviewer_id -> weight (historical agreement with ground
    truth). Unknown reviewers (cold start) default to weight 1.0. A critical
    concrete finding is always blocking regardless of the vote.
    """
    reliability = reliability or {}
    approve_w = 0.0
    reject_w = 0.0
    concrete: list[Finding] = []
    blocking: list[Finding] = []

    for v in verdicts:
        w = reliability.get(v.reviewer_id, 1.0)
        concrete.extend(f for f in v.findings if f.is_concrete)
        blocking.extend(f for f in v.findings if f.is_concrete and f.severity == "critical")
        if v.effective_verdict() is Verdict.APPROVE:
            approve_w += w
        else:
            reject_w += w

    approved = approve_w > reject_w and not blocking
    return EnsembleDecision(
        approved=approved,
        approve_weight=approve_w,
        reject_weight=reject_w,
        n=len(verdicts),
        concrete_findings=concrete,
        blocking_findings=blocking,
    )
