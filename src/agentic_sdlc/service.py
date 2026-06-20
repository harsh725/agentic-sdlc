"""Service layer: the deterministic spine as plain JSON-able functions.

Single source of truth for "classify risk / run gates / score confidence /
decide merge", exposed two ways — the CLI subcommands and the local MCP server —
so both behave identically. Everything here is pure (no Claude Agent SDK, no API
key) and unit-tested in tests/test_service.py.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from agentic_sdlc.confidence import (
    DEFAULT_AUTO_MERGE_THRESHOLD,
    ConfidenceInputs,
    compute_confidence,
    should_auto_merge,
)
from agentic_sdlc.contracts import RiskLevel
from agentic_sdlc.gates import load_gateset, run_gateset
from agentic_sdlc.risk_classifier import RiskClassifier


def classify_risk(files: list[str], diff_text: str = "") -> dict[str, Any]:
    """Deterministically classify a change as LOW or HIGH risk (fail-closed)."""
    verdict = RiskClassifier.from_yaml().classify(files, diff_text)
    return {
        "level": verdict.level.value,
        "is_high": verdict.is_high,
        "flags": verdict.flags,
        "reasons": verdict.reasons,
    }


def run_gates(repo: str = ".", gateset_path: str | None = None) -> dict[str, Any]:
    """Run the deterministic gate commands for a repo and branch on exit codes."""
    path = Path(gateset_path) if gateset_path else Path(repo) / "gates" / "gateset.yaml"
    if not path.exists():
        return {
            "found": False,
            "gateset_path": str(path),
            "all_blocking_passed": False,
            "gates": [],
            "failures": [],
            "note": "no gateset found; add gates/gateset.yaml to enable gate checks",
        }
    report = run_gateset(load_gateset(path), cwd=repo)
    return {
        "found": True,
        "gateset_path": str(path),
        "all_blocking_passed": report.all_blocking_passed,
        "gates": [
            {"name": r.name, "exit_code": r.exit_code, "passed": r.passed, "blocking": r.blocking}
            for r in report.results
        ],
        "failures": [r.name for r in report.failures()],
    }


def score_confidence(
    *,
    reviewer_approve: int = 0,
    reviewer_refute: int = 0,
    reviewer_n: int = 0,
    diff_coverage_pct: float = 0.0,
    coverage_target_pct: float = 80.0,
    mutation_total: int = 0,
    mutation_survived: int = 0,
    blast_lines: int = 0,
    blast_critical_files: int = 0,
) -> dict[str, Any]:
    """Compute the normalized confidence score from objective signals."""
    inputs = ConfidenceInputs(
        reviewer_approve=reviewer_approve,
        reviewer_refute=reviewer_refute,
        reviewer_n=reviewer_n,
        diff_coverage_pct=diff_coverage_pct,
        coverage_target_pct=coverage_target_pct,
        mutation_total=mutation_total,
        mutation_survived=mutation_survived,
        blast_lines=blast_lines,
        blast_critical_files=blast_critical_files,
    )
    return {
        "confidence": round(compute_confidence(inputs), 4),
        "signals": {k: round(v, 4) for k, v in inputs.signals().items()},
    }


def decide_merge(
    files: list[str],
    *,
    repo: str = ".",
    gateset_path: str | None = None,
    diff_text: str = "",
    threshold: float = DEFAULT_AUTO_MERGE_THRESHOLD,
    reviewer_approve: int = 0,
    reviewer_refute: int = 0,
    reviewer_n: int = 0,
    diff_coverage_pct: float = 0.0,
    mutation_total: int = 0,
    mutation_survived: int = 0,
) -> dict[str, Any]:
    """The auto-merge verdict: gates green AND confidence >= threshold AND risk LOW.

    Fail closed — anything else is 'escalate' (a human must look). Blast radius is
    derived from the number of changed files when not otherwise provided.
    """
    risk = classify_risk(files, diff_text)
    gates = run_gates(repo, gateset_path)
    conf = score_confidence(
        reviewer_approve=reviewer_approve,
        reviewer_refute=reviewer_refute,
        reviewer_n=reviewer_n,
        diff_coverage_pct=diff_coverage_pct,
        mutation_total=mutation_total,
        mutation_survived=mutation_survived,
        blast_lines=len(files) * 20,
    )
    gates_green = gates["all_blocking_passed"]
    confidence = conf["confidence"]
    risk_level = RiskLevel.HIGH if risk["is_high"] else RiskLevel.LOW

    auto = should_auto_merge(
        gates_green=gates_green,
        confidence=confidence,
        risk_level=risk_level,
        threshold=threshold,
    )
    reasons: list[str] = []
    if not gates_green:
        reasons.append("gates not green" + ("" if gates["found"] else " (no gateset configured)"))
    if risk["is_high"]:
        reasons.append(f"high-risk change: {', '.join(risk['flags'])}")
    if confidence < threshold:
        reasons.append(f"confidence {confidence:.2f} < threshold {threshold:.2f}")

    return {
        "decision": "auto_merge" if auto else "escalate",
        "gates_green": gates_green,
        "risk": risk["level"],
        "risk_flags": risk["flags"],
        "confidence": confidence,
        "threshold": threshold,
        "reasons": reasons or ["all conditions met: gates green, low risk, confident"],
        "detail": {"gates": gates, "confidence": conf, "risk": risk},
    }
