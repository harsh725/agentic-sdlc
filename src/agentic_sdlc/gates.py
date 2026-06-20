"""Deterministic ground-truth gates + anti-gaming invariants (plan §6.1, §6.5).

A gate runs a real command and branches on its exit code. Code is the oracle —
never an LLM's opinion of its own work. The anti-gaming invariants stop a
self-healing agent from turning red green by deleting tests, lowering coverage,
or editing gate config.
"""

from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class GateSpec:
    name: str
    cmd: str
    # If True a non-zero exit blocks; if False the gate is advisory (recorded
    # but never blocking — used for quarantined flaky suites).
    blocking: bool = True


@dataclass
class GateResult:
    name: str
    exit_code: int
    blocking: bool
    stdout_tail: str = ""
    stderr_tail: str = ""

    @property
    def passed(self) -> bool:
        return self.exit_code == 0


@dataclass
class GateRunReport:
    results: list[GateResult] = field(default_factory=list)

    @property
    def all_blocking_passed(self) -> bool:
        return all(r.passed for r in self.results if r.blocking)

    def failures(self) -> list[GateResult]:
        return [r for r in self.results if r.blocking and not r.passed]


def load_gateset(path: Path | str) -> list[GateSpec]:
    """Load gate specs from a YAML file (``gates:`` list of name/cmd/blocking)."""
    data = yaml.safe_load(Path(path).read_text()) or {}
    return [
        GateSpec(name=g["name"], cmd=g["cmd"], blocking=g.get("blocking", True))
        for g in data.get("gates", [])
    ]


def run_gate(spec: GateSpec, cwd: Path | str = ".", timeout: int = 1800) -> GateResult:
    """Execute one gate command, capturing exit code and output tails."""
    try:
        proc = subprocess.run(  # noqa: S603 - commands come from versioned gateset config
            shlex.split(spec.cmd),
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return GateResult(
            name=spec.name,
            exit_code=proc.returncode,
            blocking=spec.blocking,
            stdout_tail=_tail(proc.stdout),
            stderr_tail=_tail(proc.stderr),
        )
    except FileNotFoundError as exc:
        return GateResult(spec.name, 127, spec.blocking, stderr_tail=str(exc))
    except subprocess.TimeoutExpired:
        return GateResult(spec.name, 124, spec.blocking, stderr_tail="timeout")


def run_gateset(specs: list[GateSpec], cwd: Path | str = ".", timeout: int = 1800) -> GateRunReport:
    return GateRunReport([run_gate(s, cwd=cwd, timeout=timeout) for s in specs])


def _tail(text: str, lines: int = 40) -> str:
    return "\n".join(text.splitlines()[-lines:])


# --- Anti-gaming invariants (plan §6.5) -----------------------------------


@dataclass
class QualitySnapshot:
    """Metrics captured before/after a self-heal attempt to detect cheating."""

    test_count: int
    assertion_count: int
    coverage_pct: float
    skip_count: int


def enforce_no_regression(before: QualitySnapshot, after: QualitySnapshot) -> list[str]:
    """Return a list of invariant violations (empty == clean).

    A self-healing agent may not reduce the test surface or weaken the gates to
    make failures disappear.
    """
    violations: list[str] = []
    if after.test_count < before.test_count:
        violations.append(f"test count dropped {before.test_count} -> {after.test_count}")
    if after.assertion_count < before.assertion_count:
        violations.append(
            f"assertion count dropped {before.assertion_count} -> {after.assertion_count}"
        )
    if after.coverage_pct < before.coverage_pct:
        violations.append(
            f"coverage dropped {before.coverage_pct:.1f}% -> {after.coverage_pct:.1f}%"
        )
    if after.skip_count > before.skip_count:
        violations.append(f"new test skips added {before.skip_count} -> {after.skip_count}")
    return violations
