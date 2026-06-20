# Benchmarks / evaluation harness

This directory is the **eval substrate** (plan §12). Until it is populated with
measured runs, the confidence threshold stays conservative and the human-
escalation rate stays high — the system *earns* autonomy from evidence, it does
not assume it.

## What goes here

1. **Per-run measurements** — token/time/cost per feature, extracted from the
   ledger (`runs/<feature-id>/state.jsonl`). One row per feature; this is the
   only source of "fast" and "cheap" claims.
2. **Labeled diff corpus** — past diffs labeled good/bad plus any escape defects.
   Used to calibrate:
   - the **confidence threshold** (pick the point where false-auto-merge on a
     holdout set is ≤ target), and
   - **reviewer-reliability weights** (each reviewer's historical agreement with
     ground truth).
3. **Regression eval** — a held-out set the orchestrator must still pass after
   any prompt/routing/model change, so an "optimization" that degrades quality
   is caught before it ships.

## Units

- A **feature** = a PR-sized change with written acceptance criteria.
- Cost is **illustrative** and client-side-estimated; never quote it as billing.

## Status

Empty — no features have been dogfooded yet. MVP "done" is **≥3 real features
shipped through all deterministic gates on stack #1 with token/time recorded
here** (plan §14).
