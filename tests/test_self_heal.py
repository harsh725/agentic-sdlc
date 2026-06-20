"""Self-heal loop: retry caps + no-progress / oscillation abort (plan §6.5)."""

from __future__ import annotations

from agentic_sdlc.self_heal import HealController


def test_retries_then_caps() -> None:
    h = HealController(max_retries=3)
    # Each attempt has a distinct diff and a shrinking failing set, so only the
    # retry cap stops it.
    cont1, _ = h.register_attempt("diff A", {"t1", "t2", "t3"})
    cont2, _ = h.register_attempt("diff B different", {"t1", "t2"})
    cont3, reason = h.register_attempt("diff C entirely other", {"t1"})
    assert cont1 and cont2
    assert not cont3
    assert "cap" in reason


def test_oscillation_aborts_early() -> None:
    h = HealController(max_retries=5)
    h.register_attempt("a fairly long diff body that repeats", {"t1", "t2"})
    cont, reason = h.register_attempt("a fairly long diff body that repeats", {"t1"})
    assert not cont
    assert "no progress" in reason


def test_identical_failing_set_aborts() -> None:
    h = HealController(max_retries=5)
    h.register_attempt("first attempt diff", {"t1", "t2"})
    cont, reason = h.register_attempt("a totally different second diff", {"t1", "t2"})
    assert not cont
    assert "no progress" in reason
