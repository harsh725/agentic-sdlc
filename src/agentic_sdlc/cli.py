"""Command-line entry point.

``agentic-sdlc demo``  — run the deterministic spine offline (no API key) so the
                        gates -> risk -> confidence -> decision pipeline can be
                        demonstrated and trusted in isolation.
``agentic-sdlc run``   — drive a real feature through the orchestrator (needs the
                        ``orchestrator`` extra + ANTHROPIC_API_KEY).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from datetime import UTC, datetime

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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="agentic-sdlc")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("demo", help="run the deterministic spine offline")
    run = sub.add_parser("run", help="drive a feature through the orchestrator")
    run.add_argument("request", help="the feature request")
    run.add_argument("--repo", default=".", help="path to the host repository")
    run.add_argument("--feature", default="feature", help="feature id (run folder)")

    args = parser.parse_args(argv)
    if args.command == "demo":
        return _demo()
    if args.command == "run":
        return _run(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
