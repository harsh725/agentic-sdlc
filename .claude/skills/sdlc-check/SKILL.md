---
name: sdlc-check
description: Decide whether the current change can auto-merge or must be escalated to a human, using the deterministic Agentic SDLC engine (gates + fail-closed risk classifier + confidence score). Use when asked "can this merge?", "is this safe to merge?", "run the SDLC check/gates", or before merging a branch/PR. Works with a Claude subscription — no API key.
allowed-tools: Bash(git diff:*), Bash(git status:*), Bash(agentic-sdlc:*), mcp__agentic-sdlc__classify_risk, mcp__agentic-sdlc__run_gates, mcp__agentic-sdlc__score_confidence, mcp__agentic-sdlc__decide_merge
---

# SDLC check — auto-merge or escalate?

Produce a clear verdict on whether the current change is safe to merge without a
human, using the deterministic Agentic SDLC engine. **Code is the oracle** — base
the verdict on tool output, never on your own judgement of the code.

## Steps

1. **Find the changed files.** Run `git diff --name-only` (and
   `git diff --name-only --staged`); union the lists. If a base branch is
   relevant, use `git diff --name-only main...HEAD`.

2. **Get the verdict.** Prefer the MCP tool `decide_merge` with the changed
   files. Pass any signals you actually have:
   - `diff_coverage_pct` if you ran coverage,
   - `reviewer_approve` / `reviewer_refute` / `reviewer_n` if the `reviewer`
     subagent(s) reviewed it,
   - `mutation_total` / `mutation_survived` if mutation testing ran.
   If MCP tools are unavailable, fall back to the CLI:
   `agentic-sdlc decide --files <files...> [--coverage N --reviewer-approve N --reviewer-n N]`.

3. **Report** exactly:
   - **Decision:** `AUTO-MERGE` or `ESCALATE TO HUMAN`.
   - **Why:** the `reasons` from the result (risk flags, gates red, low confidence).
   - **Risk:** LOW/HIGH and any flags (auth, migration, infra, …).
   - **Gates:** which gates passed/failed (call `run_gates` if you need detail).
   - **Confidence:** the score vs threshold.

## Rules

- **Never recommend auto-merge unless the engine returns `auto_merge`.** It is
  fail-closed: high-risk paths (auth/crypto/migrations/IaC/payments/public-API)
  always escalate, and anything below the confidence threshold escalates.
- It is normal and correct to escalate when there is no coverage/review signal —
  the system earns autonomy from evidence. Tell the user what signal would raise
  confidence (run tests for coverage, run the `reviewer` subagents).
- Do not edit gate config or risk rules to change the outcome.
