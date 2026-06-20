"""Gate execution branches on exit codes; anti-gaming invariants hold."""

from __future__ import annotations

from agentic_sdlc.gates import (
    GateSpec,
    QualitySnapshot,
    enforce_no_regression,
    run_gate,
    run_gateset,
)


def test_passing_gate() -> None:
    r = run_gate(GateSpec("ok", "true"))
    assert r.passed and r.exit_code == 0


def test_failing_gate() -> None:
    r = run_gate(GateSpec("bad", "false"))
    assert not r.passed and r.exit_code != 0


def test_missing_binary_is_127() -> None:
    r = run_gate(GateSpec("missing", "definitely-not-a-real-binary-xyzzy"))
    assert r.exit_code == 127


def test_gateset_all_blocking_passed() -> None:
    report = run_gateset([GateSpec("a", "true"), GateSpec("b", "true")])
    assert report.all_blocking_passed
    assert not report.failures()


def test_gateset_advisory_failure_does_not_block() -> None:
    report = run_gateset([GateSpec("a", "true"), GateSpec("flaky", "false", blocking=False)])
    assert report.all_blocking_passed  # advisory failure is recorded, not blocking


def test_no_regression_detects_cheating() -> None:
    before = QualitySnapshot(test_count=10, assertion_count=30, coverage_pct=82.0, skip_count=0)
    deleted_test = QualitySnapshot(9, 27, 80.0, 0)
    added_skip = QualitySnapshot(10, 30, 82.0, 2)
    lowered_cov = QualitySnapshot(10, 30, 70.0, 0)
    assert enforce_no_regression(before, deleted_test)
    assert enforce_no_regression(before, added_skip)
    assert enforce_no_regression(before, lowered_cov)
    assert not enforce_no_regression(before, QualitySnapshot(11, 35, 85.0, 0))
