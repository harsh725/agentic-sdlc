"""Deterministic, fail-closed risk classifier (plan §7.1).

This is the single safety valve between the auto-merge path and a dangerous
change. It is plain code (not an LLM), versioned, unit-tested, and fails closed:
any ambiguity routes the change to HIGH (mandatory human review). A HIGH verdict
forces escalation regardless of how confident the reviewer ensemble is.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

from agentic_sdlc.contracts import RiskLevel

DEFAULT_RULES_PATH = Path(__file__).resolve().parents[2] / "risk_classifier" / "rules.yaml"


@dataclass
class RiskVerdict:
    level: RiskLevel
    flags: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)

    @property
    def is_high(self) -> bool:
        return self.level is RiskLevel.HIGH


class RiskClassifier:
    """Classify a diff (changed paths + optional diff text) as LOW or HIGH."""

    def __init__(
        self,
        high_path_globs: dict[str, list[str]] | None = None,
        high_content_patterns: dict[str, list[str]] | None = None,
        ambiguous_path_globs: list[str] | None = None,
    ) -> None:
        self.high_path_globs = high_path_globs or {}
        self.high_content_patterns = {
            flag: [re.compile(p, re.IGNORECASE) for p in patterns]
            for flag, patterns in (high_content_patterns or {}).items()
        }
        self.ambiguous_path_globs = ambiguous_path_globs or []

    @classmethod
    def from_yaml(cls, path: Path | str = DEFAULT_RULES_PATH) -> RiskClassifier:
        try:
            data = yaml.safe_load(Path(path).read_text()) or {}
        except (OSError, yaml.YAMLError) as exc:
            # Fail closed: if the rule set cannot be read, every change is HIGH.
            return _AlwaysHigh(reason=f"risk rules unreadable: {exc}")
        return cls(
            high_path_globs=data.get("high_paths", {}),
            high_content_patterns=data.get("high_content", {}),
            ambiguous_path_globs=data.get("ambiguous_paths", []),
        )

    def classify(self, files: list[str], diff_text: str = "") -> RiskVerdict:
        flags: list[str] = []
        reasons: list[str] = []

        for path in files:
            norm = path.replace("\\", "/")
            for flag, globs in self.high_path_globs.items():
                if any(_matches(norm, g) for g in globs):
                    if flag not in flags:
                        flags.append(flag)
                    reasons.append(f"path '{path}' matched high-risk domain '{flag}'")

        if diff_text:
            for flag, patterns in self.high_content_patterns.items():
                for pat in patterns:
                    if pat.search(diff_text):
                        if flag not in flags:
                            flags.append(flag)
                        reasons.append(f"diff content matched high-risk pattern '{flag}'")
                        break

        if flags:
            return RiskVerdict(RiskLevel.HIGH, sorted(flags), reasons)

        # Fail closed on ambiguity: a path we cannot confidently categorise as
        # safe-looking but matching a watchlist escalates rather than guessing.
        for path in files:
            norm = path.replace("\\", "/")
            if any(_matches(norm, g) for g in self.ambiguous_path_globs):
                return RiskVerdict(
                    RiskLevel.HIGH,
                    ["ambiguous"],
                    [f"path '{path}' is ambiguous; failing closed to HIGH"],
                )

        return RiskVerdict(RiskLevel.LOW, [], ["no high-risk rule matched"])


class _AlwaysHigh(RiskClassifier):
    """Degenerate classifier used when rules cannot be loaded — fail closed."""

    def __init__(self, reason: str) -> None:
        super().__init__()
        self._reason = reason

    def classify(self, files: list[str], diff_text: str = "") -> RiskVerdict:
        return RiskVerdict(RiskLevel.HIGH, ["fail_closed"], [self._reason])


def _matches(path: str, pattern: str) -> bool:
    # fnmatch '*' does not cross '/', so support an explicit '**' recursive glob.
    if "**" in pattern:
        regex = re.escape(pattern).replace(r"\*\*", ".*").replace(r"\*", "[^/]*")
        return re.fullmatch(regex, path) is not None
    return fnmatch.fnmatch(path, pattern) or fnmatch.fnmatch(Path(path).name, pattern)
