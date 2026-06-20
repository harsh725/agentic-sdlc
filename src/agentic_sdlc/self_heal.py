"""Self-healing loop control: retry caps + no-progress / oscillation abort.

Plan §6.5. Caps the retry count, and — critically — detects *non-progress* so
the agent cannot thrash between two failing states or burn budget making
near-identical failed edits. Pure logic; the orchestrator owns the actual
re-delegation and rollback.
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass, field


@dataclass
class HealController:
    max_retries: int = 3
    similarity_abort: float = 0.95  # diffs this similar to a prior failed attempt
    _attempts: int = 0
    _prior_failed_diffs: list[str] = field(default_factory=list)
    _prior_failset: list[frozenset[str]] = field(default_factory=list)

    @property
    def attempts(self) -> int:
        return self._attempts

    def should_continue(self) -> bool:
        return self._attempts < self.max_retries

    def register_attempt(self, diff_text: str, failing_tests: set[str]) -> tuple[bool, str]:
        """Record a failed attempt; return (continue?, reason).

        Aborts early (returns False) when the retry budget is exhausted, when a
        new diff is near-identical to a prior failed one (oscillation), or when
        the failing-test set is not shrinking.
        """
        self._attempts += 1

        for prior in self._prior_failed_diffs:
            ratio = difflib.SequenceMatcher(None, prior, diff_text).ratio()
            if ratio >= self.similarity_abort:
                return False, f"no progress: diff {ratio:.0%} similar to a prior attempt"

        failset = frozenset(failing_tests)
        if self._prior_failset and failset and failset >= self._prior_failset[-1]:
            # Failing set did not shrink (superset or equal) -> not converging.
            if failset == self._prior_failset[-1]:
                return False, "no progress: identical failing-test set across retries"

        self._prior_failed_diffs.append(diff_text)
        self._prior_failset.append(failset)

        if not self.should_continue():
            return False, f"retry cap reached ({self.max_retries})"
        return True, f"retry {self._attempts}/{self.max_retries}"
