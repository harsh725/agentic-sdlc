"""Service layer = the spine as JSON dicts (backs the CLI + MCP server)."""

from __future__ import annotations

from pathlib import Path

from agentic_sdlc import service


def _gateset(tmp_path: Path, cmd: str) -> str:
    p = tmp_path / "gs.yaml"
    p.write_text(f'gates:\n  - name: g\n    cmd: "{cmd}"\n')
    return str(p)


def test_classify_risk_dict() -> None:
    assert service.classify_risk(["src/auth/session.py"])["is_high"] is True
    low = service.classify_risk(["src/widgets/button.py"])
    assert low["level"] == "LOW" and not low["is_high"]


def test_run_gates_missing_gateset() -> None:
    out = service.run_gates(repo="/tmp", gateset_path="/no/such/gateset.yaml")
    assert out["found"] is False
    assert out["all_blocking_passed"] is False


def test_run_gates_pass_and_fail(tmp_path: Path) -> None:
    ok = service.run_gates(repo=str(tmp_path), gateset_path=_gateset(tmp_path, "true"))
    assert ok["found"] and ok["all_blocking_passed"]
    bad = service.run_gates(repo=str(tmp_path), gateset_path=_gateset(tmp_path, "false"))
    assert not bad["all_blocking_passed"]
    assert "g" in bad["failures"]


def test_score_confidence_dict() -> None:
    out = service.score_confidence(reviewer_approve=3, reviewer_n=3, diff_coverage_pct=95)
    assert 0.0 <= out["confidence"] <= 1.0
    assert "reviewer_agreement" in out["signals"]


def test_decide_merge_auto_merges_when_strong(tmp_path: Path) -> None:
    out = service.decide_merge(
        ["src/widgets/button.py"],
        repo=str(tmp_path),
        gateset_path=_gateset(tmp_path, "true"),
        reviewer_approve=3,
        reviewer_n=3,
        diff_coverage_pct=95,
        mutation_total=40,
        mutation_survived=2,
    )
    assert out["decision"] == "auto_merge"
    assert out["gates_green"] and out["risk"] == "LOW"


def test_decide_merge_escalates_high_risk(tmp_path: Path) -> None:
    out = service.decide_merge(
        ["src/auth/session.py"],  # HIGH risk -> always escalate
        repo=str(tmp_path),
        gateset_path=_gateset(tmp_path, "true"),
        reviewer_approve=3,
        reviewer_n=3,
        diff_coverage_pct=95,
        mutation_total=40,
        mutation_survived=2,
    )
    assert out["decision"] == "escalate"
    assert "auth" in out["risk_flags"]


def test_decide_merge_escalates_without_gates() -> None:
    out = service.decide_merge(["src/x.py"], gateset_path="/no/such.yaml")
    assert out["decision"] == "escalate"
    assert any("gates not green" in r for r in out["reasons"])
