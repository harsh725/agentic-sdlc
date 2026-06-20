"""Reviewer ensemble: weighted vote, noise discarding, blocking findings."""

from __future__ import annotations

from agentic_sdlc.reviewers import Finding, ReviewerVerdict, Verdict, weighted_vote


def approve(rid: str) -> ReviewerVerdict:
    return ReviewerVerdict(rid, "claude-sonnet-4-6", "correctness", Verdict.APPROVE)


def reject(rid: str, *, concrete: bool, severity: str = "minor") -> ReviewerVerdict:
    findings = [Finding("src/x.py", 10, "bug", severity)] if concrete else []
    return ReviewerVerdict(rid, "claude-opus-4-8", "security", Verdict.REJECT, findings)


def test_majority_approve() -> None:
    d = weighted_vote([approve("r1"), approve("r2"), reject("r3", concrete=True)])
    assert d.approved


def test_majority_reject_blocks() -> None:
    d = weighted_vote([reject("r1", concrete=True), reject("r2", concrete=True), approve("r3")])
    assert not d.approved


def test_reject_without_concrete_finding_is_noise() -> None:
    d = weighted_vote([approve("r1"), approve("r2"), reject("r3", concrete=False)])
    assert d.approved  # the empty rejection is discarded


def test_critical_finding_always_blocks() -> None:
    # Even with a 2-1 approve majority, a critical concrete finding blocks.
    d = weighted_vote(
        [approve("r1"), approve("r2"), reject("r3", concrete=True, severity="critical")]
    )
    assert not d.approved
    assert d.blocking_findings


def test_reliability_weights_applied() -> None:
    # One highly-reliable rejecter outweighs two low-reliability approvers.
    verdicts = [approve("r1"), approve("r2"), reject("r3", concrete=True)]
    weights = {"r1": 0.2, "r2": 0.2, "r3": 1.0}
    d = weighted_vote(verdicts, reliability=weights)
    assert not d.approved
