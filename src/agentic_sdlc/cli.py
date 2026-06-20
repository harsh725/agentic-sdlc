"""Command-line entry point.

``agentic-sdlc demo``    — run the deterministic spine offline (no API key).
``agentic-sdlc gate``    — run the gates for a repo; print JSON.
``agentic-sdlc risk``    — classify changed files as LOW/HIGH risk; print JSON.
``agentic-sdlc decide``  — auto-merge vs escalate verdict; print JSON.
``agentic-sdlc run``     — drive a feature through the orchestrator (needs the
                          ``orchestrator`` extra + ANTHROPIC_API_KEY).

The demo/gate/risk/decide commands are pure and need no API key — they back the
``/sdlc-*`` skills and the local MCP server used inside Claude Code.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from agentic_sdlc.confidence import ConfidenceInputs, compute_confidence, should_auto_merge
from agentic_sdlc.contracts import RiskLevel
from agentic_sdlc.reviewers import Finding, ReviewerVerdict, Verdict, weighted_vote
from agentic_sdlc.risk_classifier import RiskClassifier


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _demo() -> int:
    print("Agentic SDLC — deterministic-spine demo (offline, no API calls)\n")

    classifier = RiskClassifier.from_yaml()
    cases = [
        (["src/widgets/button.py"], "a low-risk UI tweak"),
        (["src/auth/session.py"], "an auth change"),
        (["infra/main.tf"], "an infrastructure change"),
        (["db/migrations/0007_drop_users.sql"], "a destructive migration"),
    ]
    print("1) Risk classifier (fail-closed):")
    for files, label in cases:
        v = classifier.classify(files)
        print(f"   {label:32s} -> {v.level.value:4s} flags={v.flags}")

    print("\n2) Adversarial reviewer ensemble (reliability-weighted vote):")
    verdicts = [
        ReviewerVerdict("r1", "claude-opus-4-8", "correctness", Verdict.APPROVE),
        ReviewerVerdict("r2", "claude-sonnet-4-6", "security", Verdict.APPROVE),
        ReviewerVerdict(
            "r3",
            "claude-sonnet-4-6",
            "simplicity",
            Verdict.REJECT,
            findings=[Finding("src/x.py", 12, "duplicated helper", "minor")],
        ),
    ]
    decision = weighted_vote(verdicts)
    print(
        f"   approve_w={decision.approve_weight} reject_w={decision.reject_weight} "
        f"-> approved={decision.approved}"
    )
    noise = [ReviewerVerdict("r4", "claude-sonnet-4-6", "x", Verdict.REJECT)]
    print(
        "   reject with no concrete finding is discarded -> "
        f"approved={weighted_vote(noise).approved}"
    )

    print("\n3) Confidence score + auto-merge predicate:")
    strong = ConfidenceInputs(
        reviewer_approve=3,
        reviewer_refute=0,
        reviewer_n=3,
        diff_coverage_pct=95,
        mutation_total=40,
        mutation_survived=2,
        blast_lines=40,
    )
    weak = ConfidenceInputs(
        reviewer_approve=2,
        reviewer_refute=1,
        reviewer_n=3,
        diff_coverage_pct=55,
        mutation_total=40,
        mutation_survived=18,
        blast_lines=600,
    )
    c_strong = compute_confidence(strong)
    c_weak = compute_confidence(weak)
    print(f"   strong diff: confidence={c_strong:.3f}")
    print(f"   weak diff:   confidence={c_weak:.3f}")

    print("\n4) The auto-merge decision (gates green AND confidence AND low risk):")
    for label, conf, risk in [
        ("strong + low risk", c_strong, RiskLevel.LOW),
        ("strong + HIGH risk (auth)", c_strong, RiskLevel.HIGH),
        ("weak + low risk", c_weak, RiskLevel.LOW),
    ]:
        merged = should_auto_merge(gates_green=True, confidence=conf, risk_level=risk)
        outcome = "AUTO-MERGE" if merged else "ESCALATE to human"
        print(f"   {label:28s} -> {outcome}")

    print("\nDeterministic spine OK. Live runs add the Claude Agent SDK on top.")
    return 0


def _run(args: argparse.Namespace) -> int:
    from agentic_sdlc.config import OrchestratorConfig
    from agentic_sdlc.orchestrator import Orchestrator

    config = OrchestratorConfig(repo=args.repo, feature_id=args.feature)
    orch = Orchestrator(config)
    terminal = asyncio.run(orch.run_feature(args.request, now=_now()))
    print(f"Terminal phase: {terminal.value}")
    print(f"Ledger: {orch.ledger.path}  totals={orch.ledger.totals()}")
    return 0 if terminal.value in ("DONE", "ESCALATED") else 1


def _emit(payload: object) -> int:
    """Print a JSON payload (machine-readable for skills/agents) and return 0."""
    print(json.dumps(payload, indent=2))
    return 0


def _read_diff(args: argparse.Namespace) -> str:
    if getattr(args, "diff_file", None):
        return Path(args.diff_file).read_text()
    return ""


def _gate(args: argparse.Namespace) -> int:
    from agentic_sdlc import service

    return _emit(service.run_gates(args.repo, args.gateset))


def _risk(args: argparse.Namespace) -> int:
    from agentic_sdlc import service

    return _emit(service.classify_risk(args.files, _read_diff(args)))


def _decide(args: argparse.Namespace) -> int:
    from agentic_sdlc import service

    return _emit(
        service.decide_merge(
            args.files,
            repo=args.repo,
            gateset_path=args.gateset,
            diff_text=_read_diff(args),
            reviewer_approve=args.reviewer_approve,
            reviewer_refute=args.reviewer_refute,
            reviewer_n=args.reviewer_n,
            diff_coverage_pct=args.coverage,
            mutation_total=args.mutation_total,
            mutation_survived=args.mutation_survived,
        )
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentic-sdlc")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("demo", help="run the deterministic spine offline")

    run = sub.add_parser("run", help="drive a feature through the orchestrator (needs API key)")
    run.add_argument("request", help="the feature request")
    run.add_argument("--repo", default=".", help="path to the host repository")
    run.add_argument("--feature", default="feature", help="feature id (run folder)")

    gate = sub.add_parser("gate", help="run the deterministic gates and print JSON")
    gate.add_argument("--repo", default=".", help="repo to gate")
    gate.add_argument("--gateset", default=None, help="path to a gateset.yaml")

    risk = sub.add_parser("risk", help="classify changed files as LOW/HIGH risk (JSON)")
    risk.add_argument("--files", nargs="+", required=True, help="changed file paths")
    risk.add_argument("--diff-file", default=None, help="optional path to a diff to scan")

    decide = sub.add_parser("decide", help="auto-merge vs escalate verdict (JSON)")
    decide.add_argument("--files", nargs="+", required=True, help="changed file paths")
    decide.add_argument("--repo", default=".", help="repo to gate")
    decide.add_argument("--gateset", default=None, help="path to a gateset.yaml")
    decide.add_argument("--diff-file", default=None, help="optional path to a diff to scan")
    decide.add_argument("--coverage", type=float, default=0.0, help="per-diff coverage %%")
    decide.add_argument("--reviewer-approve", type=int, default=0)
    decide.add_argument("--reviewer-refute", type=int, default=0)
    decide.add_argument("--reviewer-n", type=int, default=0)
    decide.add_argument("--mutation-total", type=int, default=0)
    decide.add_argument("--mutation-survived", type=int, default=0)

    args = parser.parse_args(argv)
    dispatch = {
        "demo": lambda _a: _demo(),
        "run": _run,
        "gate": _gate,
        "risk": _risk,
        "decide": _decide,
    }
    handler = dispatch.get(args.command)
    if handler is None:
        parser.print_help()
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
