# Agentic SDLC — Implementation Plan (v2)

**Last updated:** 2026-06-20
**Status:** Ready for an MVP spike (single stack)
**Repository name:** `agentic-sdlc`
**Supersedes:** `agentic-sdlc-plan.md` (v0.1) — see [Appendix A: Corrections](#appendix-a-corrections-from-v01) for every fact this version fixes.

> **How to read the numbers in this document.** Every star count and price below is a point-in-time fact captured **2026-06-20** with a primary source. Every cost, speed, and ROI figure is labeled **_illustrative_** and is a hypothesis to be replaced with measured data from your own pilot (`benchmarks/`). Treat no metric as load-bearing until you have measured it on your own traffic. v0.1 failed precisely because it shipped fabricated precision (a library with "218.3K stars" that actually has 2.6K; "$52.80/year"); v2's discipline is the opposite.

---

## Table of Contents

1. [TL;DR](#1-tldr)
2. [What this is — and what changed from v0.1](#2-what-this-is--and-what-changed-from-v01)
3. [Goals & non-goals](#3-goals--non-goals)
4. [Core principles](#4-core-principles)
5. [Architecture](#5-architecture)
6. [The foolproof quality engine](#6-the-foolproof-quality-engine)
7. [Replacing the human reviewer (the auto-merge decision)](#7-replacing-the-human-reviewer-the-auto-merge-decision)
8. [Token economics & optimization](#8-token-economics--optimization)
9. [Caffeinated mode](#9-caffeinated-mode)
10. [Security for unattended operation](#10-security-for-unattended-operation)
11. [Observability & the agent audit trail](#11-observability--the-agent-audit-trail)
12. [The benchmark / evaluation harness](#12-the-benchmark--evaluation-harness)
13. [Latency model & gate dependency graph](#13-latency-model--gate-dependency-graph)
14. [MVP-first roadmap](#14-mvp-first-roadmap)
15. [Repository structure](#15-repository-structure)
16. [Success metrics](#16-success-metrics)
17. [Risks & mitigations](#17-risks--mitigations)
18. [Goal-coverage map](#18-goal-coverage-map)
19. [Appendix A: Corrections from v0.1](#appendix-a-corrections-from-v01)
20. [Appendix B: References](#appendix-b-references-captured-2026-06-20)

---

## 1. TL;DR

**Agentic SDLC** is a custom **orchestrator agent** — specialized (not fine-tuned) for the software development lifecycle — that drives a feature from a one-line request through code, test, security, review, staging, and monitoring, **merging low-risk changes with no human in the loop** and escalating only the changes that genuinely need a human.

It rests on three load-bearing ideas:

1. **Code is the oracle, never the LLM.** Every gate keys off a *real exit code* (compiler, tests, linter, scanner), enforced by hooks and GitHub required checks that can physically block a merge. LLM self-assessment is never trusted as a correctness signal.
2. **Adversarial multi-agent review + confidence scoring + a deterministic risk classifier** replace the human reviewer for the majority of changes, while *guaranteeing* a human sees anything touching auth, data, money, or infrastructure.
3. **The real ROI is engineer time, not tokens.** API spend for this system is a rounding error (**~$30–220/year illustrative**, see §8) next to the engineer-hours it returns. We optimize for correctness, latency, and throughput — and keep token cost low as a secondary concern.

It runs **unattended and overnight** in "caffeinated mode" (§9): the laptop stays awake only while the orchestrator is actively working and sleeps the moment the work queue drains or the process exits.

**The honest scope:** v0.1's "4 weeks, 4 language stacks, 3 custom MCP servers, public launch" is ~3–4× over-scoped for one person. v2 is **MVP-first**: prove the pipeline on **one** stack (Python or TypeScript) by shipping **≥3 real features** through every deterministic gate, recording actual numbers — *then* generalize.

---

## 2. What this is — and what changed from v0.1

v0.1 had the right *skeleton* (orchestrator + specialized sub-agents + 7-phase gated pipeline) but three classes of fatal problem. v2 keeps the skeleton and fixes the substance.

| Area | v0.1 problem | v2 fix |
|---|---|---|
| **Facts** | Agent-of-Empires listed at **218.3K stars** (real: **2,613** — off by ~83×); duplicated/fabricated MCP star counts; archived servers cited as live. | Every figure re-verified against its source repo with a capture date; star column de-emphasized; archived deps removed. ([Appendix A](#appendix-a-corrections-from-v01)) |
| **Economics** | "67% token reduction" that the plan's own table contradicts (it sums to 25%); a flat "$10/M tokens" rate that no Claude model has; "$52.80/year"; model-token cost assigned to *human* review minutes; ROI quoted as both 700% and 1,674%. | Verified per-model input/output pricing; an honest, ranged, explicitly-illustrative cost model; ROI re-anchored in **engineer-hours**. ([§8](#8-token-economics--optimization)) |
| **Design** | "Fine-tuned orchestrator" (fine-tuning of current Claude models does not exist); "Haiku for *all* sub-agents" (false economy); bespoke `subagent_manager.py` reinventing what the SDK does natively; gates that rely on LLM self-assertion; *no* mechanism for the headline "avoid manual review"; **caffeinated mode entirely absent**. | Specialization via prompts/Skills/tools/context (§5.6); role-based model routing (§5.4); SDK-native subagents (§5.1); a five-layer foolproof engine with a real confidence/risk/escalation spec (§6–7); a completion-aware caffeinate design (§9). |

---

## 3. Goals & non-goals

### Goals (each is traced to a concrete mechanism in [§18](#18-goal-coverage-map))

1. A custom **orchestrator** agent, **specialized** for SDLC, producing high-quality code to consistent standards.
2. **Foolproof** quality: deterministic gates, structural enforcement, bounded self-healing.
3. **Token-saving** optimization: caching, batching, context editing, and model routing across **Opus 4.8 / Sonnet 4.6 / Haiku 4.5**.
4. **Fast** development *and* fast automated review/validation feedback.
5. **Minimize manual review/validation** — replace human reviewers with adversarial agents + confidence-gated escalation wherever it is safe to do so.
6. **High test coverage** and **strong CI/CD**.
7. Use open-source building blocks (e.g. **Agent-of-Empires**) **but not be limited to them**.
8. **Caffeinated mode**: stay awake during active development only; sleep when work completes.

### Non-goals (stated so scope stays honest)

- **No model fine-tuning.** It is not available for current Claude models and is not used. "Specialized" ≠ "fine-tuned" (§5.6).
- **Not a replacement for Claude Code or the Agent SDK** — it is built *on* them.
- **Not "zero humans."** A human remains mandatory on high-risk diffs and on net-new-feature acceptance (§6.4, §7). The goal is *minimal*, *risk-targeted* human involvement, not none.
- **Not multi-stack on day one.** One stack first (§14).

---

## 4. Core principles

1. **Code is the oracle.** Correctness is decided by exit codes from real tools, never by a model's opinion of its own work. (Intrinsic self-correction *without* an external signal measurably *degrades* accuracy — models flip correct answers to wrong; Huang et al., ICLR 2024, arXiv:2310.01798. We therefore never let an author agent "review itself.")
2. **Enforcement is structural, not advisory.** A gate is a hook that runs *your* command and can `block`, plus a GitHub **required status check** behind branch protection. A human (or agent) literally cannot merge red. Checklists in prose are documentation, not gates.
3. **Independence beats reflection.** Reviewers are separate agents with *different* models and *different* prompts so their errors are uncorrelated.
4. **Fail closed.** Any ambiguity in risk classification, any unparseable agent output, any exhausted retry → **escalate to a human**, never silently proceed.
5. **Bounded autonomy.** Every loop has a hard ceiling: `maxTurns`, `max_budget_usd`, a retry cap, and file checkpointing so a bad edit is rolled back, never compounded.
6. **Measure, don't assert.** No headline metric ships until it is populated from a real pilot run.

---

## 5. Architecture

### 5.1 Foundation choice (the keystone decision)

Claude Code (the CLI/IDE) and the **Claude Agent SDK** (`claude-agent-sdk` for Python, `@anthropic-ai/claude-agent-sdk` for TypeScript) run the *same* underlying agent loop, tool system, context management, and subagent machinery. Choose by mode:

- **Build the programmatic orchestrator + sub-agents on the Claude Agent SDK (Python).** This is the correct backbone for unattended, CI-driven, headless SDLC automation. **Python SDK: ~7.36K stars (7,364), MIT, actively maintained** — `anthropics/claude-agent-sdk-python`.
- **Use the Claude Code CLI for interactive, human-in-the-loop development** and its native primitives: subagents (`.claude/agents/*.md`), `--worktree`, the `claude agents` background-session view, `/batch`, and (experimental) Agent Teams.
- **Use the building blocks; do not rebuild them.** `AgentDefinition(description, prompt, tools, disallowedTools, model, skills, memory, maxTurns, background, effort, permissionMode)`; the built-in **Agent tool** for delegation; **hooks** (`PreToolUse`/`PostToolUse`/`Stop`/`SessionStart`/`SessionEnd`/`UserPromptSubmit`); **sessions** (`resume` / `fork_session`); `enable_file_checkpointing` + `rewind_files`; budget rails (`maxTurns`, `max_budget_usd`).
- **For production-scale unattended runs,** evaluate **hosted/managed agent execution** (Anthropic runs the agent loop in a per-session sandbox via REST) before self-hosting your own cron loops. Path: prototype locally on the SDK → move the steady-state runner to managed execution.

**Deleted from v0.1:** the hand-rolled `subagent_manager.py` (the SDK spawns and manages subagents natively via `ClaudeAgentOptions(agents={...})` + the Agent tool); `task_tracker.py` (use SDK sessions + the audit log in §11); `phase_gates.py` shrinks to a thin shell-out wrapper that runs commands and reads exit codes.

### 5.2 The team: orchestrator + specialized sub-agents

```
┌────────────────────────────────────────────────────────────┐
│ ORCHESTRATOR  (Opus 4.8) — SDK-defined, not hand-rolled     │
│  • Drives the 7-phase state machine (§5.3)                  │
│  • Delegates via the built-in Agent tool to role-tiered     │
│    AgentDefinitions, each in its own isolated context       │
│  • Branches ONLY on structured JSON returns + exit codes    │
│    (never on prose or an agent's self-assessment)           │
│  • Enforces gates via PostToolUse/Stop hooks that BLOCK     │
│  • Rails: maxTurns, max_budget_usd, file checkpointing      │
└───────────────┬────────────────────────────────────────────┘
                │ delegates (Agent tool) to declarative agents:
   ├─ code-writer       Sonnet 4.6  (Opus 4.8 for architectural work)
   ├─ test-specialist   Sonnet 4.6 author + Haiku 4.5 aggregation
   ├─ security-auditor  Sonnet 4.6  (Opus 4.8 for auth/crypto/infra)
   ├─ reviewer-pool     N heterogeneous: Opus 4.8 + Sonnet 4.6 mix
   ├─ infra/deploy      Sonnet 4.6  (human-gated on IaC)
   └─ scout/explore     Haiku 4.5   (read-only search, logs, format)
```

Sub-agents are **declarative config** (`AgentDefinition` objects or `.claude/agents/*.md` with YAML frontmatter), **not six bespoke Python packages**. Each gets its **own isolated context window** and returns **only a structured JSON result** (the contract in §5.3). Nesting depth is capped at **5** (a fixed platform limit, not configurable).

### 5.3 The orchestrator state machine (the core deliverable — fully specified)

The orchestrator is a **durable, resumable state machine**, not a free-running chat loop. This section is the spec the completeness review flagged as missing in v0.1.

**States** (one per SDLC phase, plus terminal/exception states):
`PLAN → CODE → VALIDATE → TEST → REVIEW → STAGING → MONITOR → DONE`, plus `ESCALATED`, `BUDGET_EXHAUSTED`, `FAILED`.

**Canonical sub-agent result contract.** Every delegated agent MUST return exactly this JSON (validated against a JSON Schema before the orchestrator acts on it):

```jsonc
{
  "status": "ok" | "gate_failed" | "needs_input" | "error",
  "phase": "CODE",                       // which phase produced this
  "files_changed": ["src/auth.ts"],       // paths touched
  "commands_run": [{"cmd": "pytest -q", "exit_code": 0}],
  "test_results": {"passed": 142, "failed": 0, "skipped": 0},
  "coverage_delta": {"diff_pct": 94.1, "total_pct": 81.0},
  "risk_flags": ["auth"],                 // from the risk classifier (§7)
  "confidence": 0.0,                       // computed by the orchestrator, NOT self-reported
  "summary": "…",                          // human-readable, for the audit log only
  "next_action": "advance" | "retry" | "escalate" | "halt"
}
```

**Hard rules:**
- **`confidence` and `risk_flags` are computed by the orchestrator from objective signals (§7), never accepted from the sub-agent's self-report.** A field a sub-agent fills in about its own quality is treated as advisory text only.
- A **malformed or missing-field response → `next_action: escalate`** (fail closed). The schema validator is deterministic code, not an LLM.
- The orchestrator branches on `commands_run[].exit_code` and gate outputs — *not* on `summary`.

**Durable state ledger.** Phase state is persisted to an append-only `runs/<feature-id>/state.jsonl` (one record per transition: `{ts, feature_id, from_state, to_state, trigger, agent, model, tokens_in, tokens_out, cost_usd, gate, exit_code}`). On crash, the orchestrator resumes from the **last committed gate**, not from scratch — SDK session-resume restores conversation context, but the ledger is the source of truth for *which phase passed*. This ledger doubles as the audit trail (§11) and the data source for `benchmarks/` (§12). Idempotency: re-entering a phase re-runs its (deterministic) gates; a phase is "done" only when its required checks are green on the current commit SHA.

### 5.4 Model-routing table (role-based)

Routing is by **role**, set per agent via `AgentDefinition.model`. Pricing is per-MTok (input/output), verified 2026-06-20. **Output is 5× input on every model**, so the model you pick for *output-heavy* steps (code generation, review write-ups) dominates the bill far more than any compression tool.

| Role / task | Model | $/MTok (in/out) | Why |
|---|---|---|---|
| Orchestration / planning | **Opus 4.8** | $5 / $25 | Strongest reasoning; 1M context for large-repo state. Drop to Sonnet 4.6 on simple repos. |
| Hard / architectural coding | **Opus 4.8** | $5 / $25 | Gnarly multi-file refactors. Reserve **Fable 5** ($10/$50) only for the rare hardest reasoning. |
| Default feature coding | **Sonnet 4.6** | $3 / $15 | Best speed/intelligence balance; 1M context. Escalate to Opus 4.8 on retry (§6.5). |
| Adversarial code review | **Sonnet 4.6 + Opus 4.8 mix** | — | Heterogeneity decorrelates errors. Vary model *and* prompt. |
| Security audit | **Sonnet 4.6** (Opus 4.8 for auth/crypto/infra) | — | Adversarial reasoning matters; **never Haiku on security**. |
| Read-only scouts, log scraping, test-result aggregation, secret-scan triage, formatting, boilerplate | **Haiku 4.5**, `effort: low` | $1 / $5 | Fast/cheap, high-volume, low-reasoning. **200K context** — never orchestrate a large repo on it. |

> **Why "Haiku for all sub-agents" (v0.1) is wrong:** cheap-but-wrong code from an under-powered code-writer triggers retry churn (each retry costs *more* than doing it right once) or, worse, leaks bugs past the gates. Routing is an economic decision about the *retry tax*, not just sticker price.

**Runtime escalation (not a static table).** Escalation is triggered by **objective signals**, never an agent saying "I'm stuck":
- ≥2 consecutive gate failures on the same diff → bump the code-writer from Sonnet 4.6 → Opus 4.8 for the next retry.
- A `risk_flags` hit on a hard domain (crypto, concurrency) → start that agent on Opus 4.8.
- Approaching the per-feature budget (§8.4) → *downgrade* non-critical work (extra reviewers, scouts) to Haiku and reduce reviewer N. Mid-task swaps fork a fresh session for the new model (cache for the old model is not reused), so escalate at phase boundaries where possible.

### 5.5 Parallelism (git worktrees)

Use the four native parallelism surfaces; do not reinvent them:

1. **Sub-agents** — isolated context per agent; returns a summary, not its whole transcript.
2. **Worktrees** — `claude --worktree <name>` (isolated checkout under `.claude/worktrees/`) or `isolation: worktree` in subagent frontmatter (auto-cleaned if unchanged). **Mandatory for any agents that edit files in parallel**, so concurrent edits never collide. ~4–8 concurrent worktrees per developer is a commonly reported reliable range.
3. **`claude agents` view** — dispatch/monitor background sessions, each auto-moved to its own worktree.
4. **Agent Teams** (experimental, Opus 4.6+) — coordinated sessions with a shared task list and a lead that routes messages.
5. **Built-in `/batch` skill** — splits one change into many worktree-isolated sub-agents, each opening its own PR.

**Concurrency model, stated honestly:** there is **no "max N agents" dial.** Practical limits are your token/rate limits plus the fixed depth-5 nesting cap. A session manager (Agent-of-Empires, or `claude agents`) is what imposes a practical cap and gives you the "which agent is stuck/waiting/done" view.

### 5.6 "Specialized, not fine-tuned"

There is **no model training in this system, and none is available** for current Claude models. The orchestrator is "fine-tuned *for* SDLC" only in the sense that its *system* is specialized through six levers:

1. `system_prompt` / per-agent `AgentDefinition.prompt` encoding the SDLC method and your standards.
2. **Skills** (`.claude/skills/*/SKILL.md`, auto-loaded) packaging repeatable workflows (planning, gate-running, release).
3. Tight per-agent **`tools` whitelists** (a reviewer cannot write; a scout cannot push).
4. **`CLAUDE.md` memory** carrying project conventions and the global standards you already maintain.
5. **MCP tools** exposing your build/test/deploy/VCS as first-class actions.
6. **Per-sub-agent context isolation** so each agent sees only what its role needs.

The result behaves like a domain-specialized SDLC engine with **zero training cost or data**.

### 5.7 MCP policy (lean + scoped)

Minimal verified core: **GitHub MCP** (PR/issue/CI; ~30.8K stars) and a **Filesystem MCP** sandboxed to allowed directories. **FastMCP** (~25.7K stars) is the framework for any custom build MCPs (Android Gradle / iOS Xcode / Web Bundler) you write *later*. Add **Playwright MCP** (~34.1K) only when you have a web/E2E surface.

- **Drop the v0.1 Postgres/SQLite MCP rows** — both were listed at a duplicated/fabricated 15.6K stars; they are archived reference subdirectories of `modelcontextprotocol/servers` ("no longer maintained, no security guarantees"). Use a maintained third-party DB MCP or talk to a test DB through your test harness instead.
- **Scope every server to the specific sub-agents that need it** via `mcpServers` frontmatter. Every loaded MCP server injects its tool descriptions into context (token cost) and widens the attack surface (§10).

### 5.8 Agent-of-Empires — correct positioning + alternatives

**What it actually is** (verified 2026-06-20): `agent-of-empires/agent-of-empires` — **~2.6K stars (2,613), MIT, Rust**, actively maintained. A terminal session manager that runs *multiple* AI coding-agent CLIs (Claude Code, Codex, Gemini, Copilot, Factory Droid, etc.) in parallel, wrapping **tmux + git worktrees + optional Docker sandboxing**, with a TUI and a **Beta** web/PWA mobile dashboard (remote access via tunnel, status detection, diff viewer, notifications).

**Correct fit:** a **human-facing operator control plane** — it *launches and monitors* parallel agent sessions and answers v0.1's "which agent is stuck/waiting/done." It does **not** implement phase gates, programmatic sub-agent coordination, or acceptance/coverage logic. **Position it as an optional viewing/launching layer *alongside* the SDK orchestrator — never the backbone.** Validate it is still maintained at adoption time and treat the web dashboard as Beta.

**Alternatives ("not limited to it"):** Claude Code's built-in `claude agents` / Agent Teams / `/batch` (zero extra dependencies — try these first); Conductor (Melty Labs Mac GUI over the worktree-per-task pattern); Shipyard; ComposioHQ/agent-orchestrator (adds autonomous CI-fix / merge-conflict / review handling); Claude Squad; tmux/zellij multiplexers.

---

## 6. The foolproof quality engine

### 6.1 The five layers

1. **Deterministic ground-truth gates.** Every gate runs a real command and branches on its **exit code**, enforced two ways: locally by `PostToolUse`/`Stop` hooks that **block**, and on the server by **GitHub branch-protection required status checks + a merge queue + CODEOWNERS**. A human cannot merge red; only Actions/Checks-API results count as required checks.
2. **Adversarial multi-agent review** (§6.3).
3. **Confidence scoring** (§6.2).
4. **Risk-based human escalation** (§7).
5. **Self-healing retry loops** (§6.5).

### 6.2 Confidence scoring (the formula — the linchpin of "avoid manual review")

The completeness review correctly flagged that an undefined "confidence" makes the auto-merge gate theater. So it is defined as a **normalized weighted score in [0,1]**, computed by deterministic orchestrator code from objective signals:

```
confidence = Σ wᵢ · sᵢ        (weights sum to 1; each sᵢ normalized to [0,1])
```

| Signal `sᵢ` | Source | Normalization |
|---|---|---|
| Reviewer-agreement margin | fraction of the reviewer pool that votes "approve" minus the refute share | `(approve − refute + N)/(2N)` |
| Per-diff coverage | coverage of changed lines | `min(diff_cov / target, 1)` |
| Mutation score (changed files) | surviving mutants on the diff | `1 − survived/total` |
| Blast radius (inverse) | changed lines + number of critical-path files touched | `1 − min(blast/blast_cap, 1)` |
| Historical defect density (inverse) | escape-defect rate of the touched files (from the audit log) | `1 − min(density/cap, 1)` |

**Calibration (not guesswork):**
- **Bootstrap** with equal weights and a conservative threshold (e.g. auto-merge only at `confidence ≥ 0.9` *and* zero risk flags). Be deliberately over-cautious at the start.
- **Calibrate** against a labeled corpus of past diffs in `benchmarks/` (known-good vs known-bad). Pick the threshold where the false-auto-merge rate on the holdout set is ≤ your target (start near 0).
- **Close the loop:** every diff that auto-merges and *later* causes an escape defect (caught in staging/monitor) is fed back to re-weight the signals. Until you have ≥ ~50 labeled outcomes, keep the threshold high and the human-escalation rate high.

> If you have not yet built the labeled corpus, the honest default is: **escalate everything that is not trivially low-risk.** Confidence-gated auto-merge *earns* its scope as the data accumulates.

### 6.3 The reviewer ensemble (spec)

- **N = 3** independent reviewer agents by default (tune via benchmarks), **heterogeneous in both model and prompt** (e.g. 2× Sonnet 4.6 + 1× Opus 4.8, each with a different review lens: correctness, security, simplicity/maintainability).
- Each reviewer returns a **structured verdict**: `{verdict: approve|reject, severity, findings:[{file, line, claim, severity}]}`. Reviewers are prompted to **REFUTE** (find the strongest reason this is wrong) to counter rubber-stamping.
- **Anti-false-positive guard:** a `reject` must cite a concrete, checkable finding (file+line+claim). A refutation with no concrete finding is discarded as noise so the adversarial prompt cannot reflexively block every PR.
- **Aggregation:** **reliability-weighted majority vote**, not plain majority (plain majority collapses when ≥50% of reviewers share a bias). Reliability weights start equal (cold start) and are updated from each reviewer's historical agreement-with-ground-truth as the audit log accumulates labeled outcomes. Disagreement that survives weighting → the change does not meet "high confidence" → escalate.

### 6.4 The 7 phases → concrete automated checks

| Phase | Deterministic gate(s) — branch on exit code | Tools | Enforcement |
|---|---|---|---|
| **1 PLAN** | Acceptance criteria present + structured; **pre-classify risk** of the intended paths | `UserPromptSubmit` hook validates an AC template; risk classifier (§7) | Hook blocks if AC missing |
| **2 CODE** | Compiles/typechecks; lint clean; format clean (diff mode); **no secrets** pre-commit | `tsc --noEmit` / `go build` / `mypy --strict`; `eslint` / `golangci-lint` / `flake8`+`black`; **gitleaks** pre-commit + push protection | `PostToolUse` hook + required check |
| **3 VALIDATE** (security — **layered & parallel**, not a one-shot) | Secrets (verified-live), SAST, SCA/CVE, IaC, SBOM + signing | **trufflehog** (live-cred verification) + gitleaks; **semgrep** (PR-time) + **CodeQL** (deep dataflow/taint); `npm/pip audit` + `govulncheck` + **Trivy/Grype**; **Checkov/Trivy** IaC; **Syft** SBOM + **cosign/Sigstore** → SLSA build provenance via OIDC. All emit **SARIF** to one Security tab. **Pin & verify scanner versions** (the scanners are themselves a supply-chain surface). | All required status checks |
| **4 TEST** | build → unit → (integration, contract) → e2e; parallel only on **independent** legs; **per-diff coverage** (not total); **mutation score on changed files**; property-based edge cases; flaky **detect → quarantine → fix-or-delete SLA** | `pytest --cov` / `jest` / `go test`; **testcontainers** (real DB/queue); **Pact** (contract); **Hypothesis / fast-check / jqwik** (property); **Stryker / PIT / mutmut** (mutation) | Per-diff coverage + mutation required; quarantined flakes off the blocking path but visible |
| **5 REVIEW** | Adversarial ensemble consensus + confidence score; risk classifier routes high-risk → **2 human approvals** | reviewer-pool (§6.3); CODEOWNERS | Auto-merge only if green **and** high confidence **and** low risk |
| **6 STAGING** | Progressive delivery (feature flag → canary → **automated canary analysis vs SLOs**) + auto-rollback / flag-kill on breach | Argo Rollouts / Flagger; OpenTelemetry SLIs (error rate, p95, a key business metric); error budget | Required; flag-kill is faster than redeploy |
| **7 MONITOR** | **Error-budget / SLO gate — not a 24h timer**; a regression attributable to a specific flag → auto-disable | OpenTelemetry traces/metrics/logs; per-service SLOs | Error budget is the gate |

### 6.5 Self-healing loop (with anti-gaming guards)

On any gate failure, the orchestrator feeds the **structured failure** (logs, stack trace, SARIF, the failing diff) back to the **code-writer** agent to patch, then re-runs the gates. This is where v0.1 was silent and where agents most often cheat — so the guards are explicit:

- **Cap at ~3 retries**, then escalate to a human. Bounded additionally by `maxTurns` + `max_budget_usd`.
- **No-progress / oscillation abort:** if two consecutive retries produce diffs with high similarity to a prior failed attempt, or the failing-test set does not shrink, abort early and escalate (don't burn the retry budget thrashing).
- **Anti-gaming invariants** (checked by deterministic code, not trust):
  - **Gate config is immutable on the auto path** — the agent cannot edit thresholds, CI workflow files, or `.gitleaks`/semgrep configs to make red turn green. Changes to gate config force human review.
  - **Test count and assertion count must not decrease**, and **no `@skip`/`xfail`/`it.only`** may be added on the auto path. Deleting/weakening a failing test is a gate failure, not a fix.
  - **Coverage and mutation thresholds cannot be lowered** by the agent.
- **Rollback, never compound:** bad edits are reverted via `enable_file_checkpointing` + `rewind_files` before the next attempt.

---

## 7. Replacing the human reviewer (the auto-merge decision)

This is the mechanism behind goal #5. A change **auto-merges with no human** only when **all three** hold:

```
auto_merge  ⟺  all required gates GREEN
            AND confidence ≥ calibrated_threshold     (§6.2)
            AND risk_class == LOW                      (§7, deterministic)
```

Otherwise it **escalates to a human** (fail closed).

### 7.1 The risk classifier (deterministic — the single safety valve)

The classifier is the one thing standing between auto-merge and a dangerous change, so it is **deterministic code**, layered, and **fails closed**:

- **Path rules (globs):** anything under auth/`**/auth/**`, crypto, `**/migrations/**`, `infra/**`/`*.tf`/`*.yaml` k8s, payments/billing, `**/*.proto` / public-API schemas → **HIGH**.
- **Content rules (regex/keywords):** diffs touching password/token/secret handling, SQL/`exec`/deserialization sinks, CORS/`AllowAll`, IAM policy → **HIGH**.
- **Semantic reachability (where feasible):** an import-graph/AST check so an auth change reached *transitively* through an innocuous-looking helper is still caught (defends against the obvious false-negative).
- **Versioned & tested:** the rule set lives in `risk-classifier/`, is unit-tested against labeled diffs, and is itself gate-config (so an agent can't edit it on the auto path).
- **Fail closed:** unknown/ambiguous classification → **HIGH → human**. A change the classifier cannot confidently call LOW is never auto-merged.

HIGH-risk changes require **2 human approvals via CODEOWNERS** regardless of confidence. A human also validates **acceptance criteria for net-new features** even when all gates are green — gates verify *the code is correct*, not *that it's the right feature*. (This residual human step is deliberate and bounded; it is the honest boundary of "avoid manual review," not a contradiction of it.)

### 7.2 Human-escalation UX (so escalation is real, not a dead-end)

- **Notification:** push the escalation to the human via the available notification path (e.g. the `PushNotification` / `RemoteTrigger` surfaces, Slack, or GitHub review-request) with a one-screen handoff: what changed, why it escalated (risk flag / low confidence / retries exhausted), the failing signal, and a link to the worktree/PR.
- **SLA & fallback:** if no human responds within a configured window, the change **holds** (never auto-merges by timeout), the worktree is preserved, and — critically — the **caffeinate assertion is *released*** while waiting (§9) so a multi-hour human wait does not hold the laptop awake.
- **Resumable:** on approval, the orchestrator resumes from the `REVIEW` state in the ledger (§5.3).

---

## 8. Token economics & optimization

### 8.1 Verified pricing (per MTok, USD; captured 2026-06-20)

| Model | Input | Output | Context |
|---|---|---|---|
| **Opus 4.8** | $5 | $25 | 1M |
| **Sonnet 4.6** | $3 | $15 | 1M |
| **Haiku 4.5** | $1 | $5 | 200K |
| **Fable 5** | $10 | $50 | 1M |

**Output = 5× input on every model.** There is **no flat "$10/M" rate** (v0.1's error). Note: Opus/Sonnet 4.6+ use a newer tokenizer that produces **~30% more tokens** for the same text — re-measure baselines rather than carrying old numbers over.

### 8.2 Levers, ranked by real impact (report each independently — they do **not** sum or multiply)

1. **Role-based model routing (biggest lever).** Because output is 5× input, routing output-heavy steps to the right model beats any compression trick (§5.4).
2. **Prompt-cache the stable prefix.** Cache `CLAUDE.md`, phase-gate checklists, coding standards, tool/MCP schemas, and large unchanging file context behind a cache breakpoint. **Cache read = 0.1× input (90% off the cached prefix only); cache write = 1.25× (5-min TTL) / 2× (1-hr TTL).** A 5-min cache pays off after **1 reuse**; a 1-hr cache after **2 reuses**.
3. **Sub-agent context isolation.** Each sub-agent receives only the context its role needs (not the full orchestrator transcript) → caps input growth and avoids quadratic blow-up. This is a *token* lever, not just a parallelism one.
4. **Context editing.** `clear_tool_uses_20250919` (drop oldest tool outputs past a threshold, keep the most recent few; `clear_tool_inputs: true` to also drop call params), `clear_thinking_20251015`, server-side `compact_20260112`. Tune against caching — over-clearing invalidates the cached prefix.
5. **Scoped retrieval.** Feed targeted file slices + grep/symbol results, not whole directories. The cheapest token is the one never sent.
6. **Batch API (flat 50% off) — async only.** Use **only** for genuinely non-interactive work: nightly security sweeps, bulk test-failure summarization, weekly cost/quality reports, doc regeneration. **Never in the interactive coding loop** (~24h latency). It stacks with caching.
7. **Headroom (optional).** If adopted (~36–40K stars; Apache-2.0; input/context compression — "compress tool outputs, logs, files, RAG chunks *before* they reach the LLM"), label its "60–95%" as **self-reported input-side** compression, validate it on your own traffic, and note it **fights caching** (compressing a prefix lowers cache-hit value). It is *not* "output compression" (v0.1's error).

### 8.3 Cache-layout policy (resolving the caching ↔ context-editing ↔ isolation tension)

The three token levers above interact, and naïvely combining them *raises* cost. Concrete policy:

- **Cached prefix (stable):** system prompt, `CLAUDE.md`, gate/standards docs, tool & MCP schemas. Put one cache breakpoint at the end of this block. This block changes rarely → high cache-hit value.
- **Mutable tail (uncached):** the evolving conversation, tool outputs, retrieved file slices.
- **Context editing only clears from the mutable tail**, never the cached prefix, and `clear_at_least` is set so each clear reclaims enough tokens to be worth the prefix re-write it might trigger.
- **Across isolated sub-agents:** each sub-agent has its own context, so a shared standards prefix is **re-cached per agent** (each pays one cache-write). Keep the shared prefix lean, and prefer a *small* shared standards block + agent-specific context over duplicating a huge prefix into every sub-agent.

### 8.4 Token-budget governor (runtime, not just accounting)

- **Per-feature budget** (`max_budget_usd` on the orchestrator) with **per-agent sub-budgets**.
- On approaching the cap: **degrade gracefully** — downgrade non-critical agents (extra reviewers, scouts) to Haiku, reduce reviewer N, *then* if still over, **checkpoint in-flight worktrees and escalate** rather than hard-killing mid-edit (which would strand a worktree).
- Every step's tokens/cost are written to the ledger (§5.3), giving real per-feature numbers for `benchmarks/`.

### 8.5 Honest, illustrative cost model (validate with a 3–5 feature pilot — **these are NOT measured**)

- Price **input / output / cached-input separately, per model**, weighted by the orchestrator/sub-agent mix.
- A mid-size feature might be **~150–400K input** (mostly cacheable repo/context) **+ ~15–40K output**, varying **5–50×** with codebase size, retrieval scope, and tool-call volume.
- Uncached, single-model: `300K in × $5 + 30K out × $25 =` **~$2.25 (Opus)**; ~$0.45 (Haiku).
- With ~90% input cache hits + Haiku for bulk sub-agent work: **~$0.21–1.03/feature**.
- A realistic Opus-orchestrator + Haiku/Sonnet-worker mix: **~$0.30–2.25/feature → ~$30–220/year at ~96 features.**
- **Budget for the retry tax:** failed features cost *more*; cheap-but-wrong models increase retries.

### 8.6 Strategic reframe

API spend (~$30–220/yr, illustrative) is a **rounding error** next to engineer time (order ~$10K/yr of returned hours, illustrative — state every assumption: features/month × hours/feature × fully-loaded $/hr). **Optimize for correctness, latency, and throughput; keep token cost low as a secondary goal.** "Token reduction" is a subsection here, not the headline. *(Token break-even vs a manual baseline lands around feature #3 on v0.1's own table — but the number that matters is engineer-hours, not tokens.)*

---

## 9. Caffeinated mode

Keep the laptop awake **only while the orchestrator is actively working**; sleep the moment work completes, the process exits, or it crashes. Slots into the two empty hooks (`session-start.sh` / `session-end.sh`). **Opt-in** via a `CAFFEINATE_MODE` flag — never force it on silently on battery or shared machines.

### 9.1 Core design

Tie `caffeinate` to the **long-lived orchestrator PID** (not the ephemeral hook PID) via `-w`, so it **auto-releases the instant the orchestrator exits/crashes/is killed**. Defense in depth = `-w` (normal release) **+** `-t` (idle/heartbeat timeout, so a crashed-but-not-exited run can't hold the machine forever) **+** a session-end reaper (kill the recorded PID and sweep zombies).

**Flag reference (`man caffeinate`):** `-i` prevent system idle sleep · `-m` prevent disk idle sleep · `-d` prevent *display* sleep (**drop** for a headless run — wastes battery) · `-s` prevent system sleep (**AC-only, no-op on battery — drop**) · `-u` declare user activity (**redundant for headless — drop**) · `-t <sec>` auto-release after timeout · `-w <pid>` hold until PID exits.

**`session-start.sh` (core):**
```bash
mkdir -p ~/.agentic-sdlc
ORCH_PID=${ORCHESTRATOR_PID:-$PPID}
if pmset -g ps | grep -q 'AC Power'; then TIMEOUT=14400; else TIMEOUT=1800; fi  # 4h AC / 30m battery
caffeinate -i -m -w "$ORCH_PID" -t "$TIMEOUT" &
echo $! > ~/.agentic-sdlc/caffeinate.pid
```

**`session-end.sh` (safety net):**
```bash
PIDFILE=~/.agentic-sdlc/caffeinate.pid
[ -f "$PIDFILE" ] && kill "$(cat "$PIDFILE")" 2>/dev/null; rm -f "$PIDFILE"
pkill -f 'caffeinate.*-w' 2>/dev/null || true
```

### 9.2 Completion-awareness (the part v0.1's goal actually hinges on)

`-w <PID>` only handles process **exit**. But "work completes" can happen while the orchestrator is *still alive and idle* — most importantly when it is **blocked waiting on a human escalation** (§7.2). So:

- **Heartbeat assertion, not a permanent one.** While actively working, the orchestrator re-spawns a short `caffeinate -i -t 120` every ~90s. If it stalls/crashes, the assertion lapses within ~2 minutes — the machine sleeps on its own.
- **Release-but-stay-alive on idle:** when the **work queue drains** or the orchestrator enters `ESCALATED`/`needs_input`, it **stops issuing heartbeats** (releasing the wake assertion) while the process stays alive to receive the human's answer. The laptop sleeps; the run resumes from the ledger when the human responds and the orchestrator wakes/reconnects. This is exactly the "sleep when work completes" behavior the goal asks for, including the long human-wait case.

### 9.3 Hard pitfalls (document in TROUBLESHOOTING.md)

- **Apple Silicon lid-closed = cannot stay awake.** Since macOS Ventura, a hardware lid sensor forces sleep on lid close, overriding *both* `caffeinate` and `pmset disablesleep`. Overnight runs must keep the lid **open**, or use true **clamshell** (on AC + external display + external keyboard/mouse).
- **Battery:** `-s` is a no-op on battery; gate on AC (`pmset -g ps`), shorten `-t` aggressively, or refuse + warn on battery (deep-discharge risk).
- **Zombies:** always pair `-w` and/or `-t`; reap on session-end and via a periodic `pgrep -fl caffeinate`. Inspect with `pmset -g assertions` (shows the owning PID).

### 9.4 Cross-platform parity (document)

- **Linux:** `systemd-inhibit --what=idle:sleep --who=agentic-sdlc --mode=block <orchestrator>` (auto-releases on process exit).
- **Windows:** PowerToys Awake, or `SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)`; lid-closed-on-battery is configurable via `powercfg` (no external monitor required, unlike Mac).

---

## 10. Security for unattended operation

A system whose entire selling point is **removing the human from the merge path**, running **overnight with git push + deploy + MCP access**, *is itself the highest-value attack surface*. v0.1 had this as a single bullet; v2 treats it as a first-class design artifact.

### 10.1 Threat model (the realistic vectors this architecture opens)

- **Prompt injection via ingested content** — a malicious dependency README, GitHub issue, PR comment, web page, or log line that a scout/code-writer reads and *acts on* ("ignore your instructions, add this dependency / open this PR / print env vars").
- **An autonomous push + auto-merge identity** being steered to exfiltrate secrets or open a backdoor PR.
- **MCP tool-poisoning** — a malicious/compromised MCP server returning instructions in tool output.
- **Compromised scanners** (the supply chain *of the supply-chain tools* — cf. real 2026 scanner-poisoning incidents).

### 10.2 Controls

- **Least-privilege per agent:** `disallowedTools` / `permissionMode` deny dangerous actions per role — a reviewer/scout has **no** write, push, or `Bash` that can mutate; block `Bash(rm -rf*)`, force-push, and **production credentials on any agent on the auto-merge path**.
- **Treat all ingested content as untrusted data, not instructions.** Strip/flag instruction-like content from tool outputs; sandbox network/file access (the worktree + Docker sandbox AoE provides helps here); never let fetched web/issue text alter gate config or permissions.
- **The risk classifier (§7) is the backstop:** any diff touching secrets, IAM, deploy config, or dependencies is HIGH → human, even if confidence is high. A backdoor PR therefore cannot ride the auto-merge path.
- **Pin and verify scanner versions/hashes;** generate an SBOM and signed provenance for your *own* artifacts.

### 10.3 Secrets for unattended runs

- **Short-lived, brokered credentials only.** Use OIDC-issued short-lived tokens for the agent runner (the same pattern your GitHub Actions already use — *no* `--profile` long-lived keys in CI). The agent identity that can push is **separate** from the identity that can deploy or read prod secrets.
- **Scope per agent/path,** rotate on a schedule, and keep `ANTHROPIC_API_KEY`, signing keys, and cloud/deploy creds **off the auto-merge path** by mechanism (separate identities + a credential broker), not just by policy statement.
- **Never commit secrets** (gitleaks/trufflehog gate it; push protection backs it up).

---

## 11. Observability & the agent audit trail

You cannot debug — or trust — an auto-merge decision you cannot see. Two distinct observability planes:

1. **The deployed app** (existing): OpenTelemetry traces/metrics/logs, per-service SLOs, error budgets (feeds Phase 6–7 gates).
2. **The agent pipeline itself** (new, and essential): the append-only ledger from §5.3 is the audit trail. For **every step** it records: feature id, phase, agent, model, tokens in/out, cost, the exact commands run + exit codes, gate results, the computed confidence + risk class, and **the reason a change auto-merged vs escalated**. 

This makes every autonomous decision **auditable and root-causable**, is the data source that populates `benchmarks/` (§12), and is what lets you root-cause a bad auto-merge after the fact. A bad-merge post-mortem becomes "read the ledger for that feature id," not "guess."

---

## 12. The benchmark / evaluation harness

v0.1 deferred every number to "validate with benchmarks" without ever specifying the benchmarks. The harness is itself a deliverable:

- **Unit of measurement:** define "a feature" (e.g. a PR-sized change with written acceptance criteria) so token/time/cost are comparable across runs.
- **Instrumentation:** the ledger (§11) captures per-run token/time/cost automatically — no manual bookkeeping.
- **Labeled corpus:** accumulate past diffs labeled good/bad (and any escape defects) to **calibrate the confidence threshold and reviewer-reliability weights** (§6.2–6.3). This is the substrate the "avoid manual review" goal depends on.
- **Regression eval:** a held-out set the orchestrator must still pass after any prompt/routing/model change, so an "optimization" that quietly degrades quality is caught before it ships.

Until the corpus exists, **the confidence gate stays conservative and the escalation rate stays high** — the system *earns* autonomy from measured evidence.

---

## 13. Latency model & gate dependency graph

"Fast" must be falsifiable, so replace v0.1's fictional minute-timers with a dependency DAG and measured targets.

- **Gate DAG (what can run in parallel):** `compile/lint/format/secrets` run immediately and in parallel on the diff; `unit` depends on `build`; `integration`/`contract` depend on `build`+`unit`; `e2e` depends on a deployed artifact; `coverage`/`mutation` depend on the test run. The scheduler honors this DAG and parallelizes only the independent legs (v0.1's "5+10+8 = 20 min" was wrong — sequential is 23, true parallel is ~max(10), and the legs aren't freely parallel anyway).
- **Target to measure (not assert):** **time-to-first-actionable-signal** (how fast the developer learns compile/lint/secret failures) and **end-to-end wall-clock per feature**, both recorded to `benchmarks/`. The genuine *latency win* of this system is **confidence-gated auto-merge of low-risk green diffs** removing the human-review wait — not invented per-phase timers.

---

## 14. MVP-first roadmap

> **Why v0.1's timeline isn't credible:** it claims "4 hours setup" / "4 weeks" while the roadmap itself sums to ~46 hands-on hours, every estimate prices happy-path typing with no write-run-debug iteration, and it ships **4 stacks + 4 examples + 6 agent packages + 3 custom MCPs + a public launch *before a single real feature passes through the pipeline*.** That is ~3–4× over-scoped for one person.

**Decouple effort-hours from calendar.** State availability explicitly (e.g. "~8 focused hrs/week → ~6–8 weeks to MVP"). Apply a **2–3× iteration multiplier** to every agent/workflow/MCP task and a **25–30% buffer**. Reset all of v0.1's pre-checked `[x]` boxes to `[ ]`.

**The lean path:**

1. **Pick ONE real host project** on ONE stack you already work in — **Python or TypeScript** (the Agent SDK is native to both). Defer Go / Flutter / iOS / Android / monorepo.
2. **Spike the Claude Agent SDK** in a throwaway repo (~1 day) to de-risk the orchestrator *before* estimating the rest.
3. **Walking skeleton:** orchestrator + **3 sub-agents** (code-writer, test, review) as **declarative config**, not 6 Python packages. (`subagent_manager.py` deleted.)
4. **Deterministic gates:** ONE CI workflow running `tsc`/`pytest --cov`/`eslint`/`gitleaks`, blocking on real exit codes as GitHub **required checks**. Skip the 6-workflow / canary / monitoring-cron breadth for now.
5. **Dogfood:** ship **≥3 real features** through the loop in your own repo, recording **actual token/time** into `benchmarks/`.
6. **Only then generalize:** add stack #2 → examples → optional custom MCPs → (separately, gated on measured evidence) public launch.

**MVP "done" (outcome-based, not date-based):** *"≥3 real features shipped through all deterministic gates on stack #1, with measured token/time recorded in `benchmarks/`, and confidence-gated auto-merge enabled for at least the lowest-risk class."*

**Explicitly deferred out of MVP:** 3 of 4 stacks, the monorepo example, all 3 custom MCP servers, `skills/`, Agent-of-Empires, Headroom/Batch integration, and the entire public-launch phase.

> **Mobile caveat (named, not buried):** the user's broader target set is mobile-heavy (Android/iOS/Flutter), and "code is the oracle" is **materially harder** there — device/simulator farms, signing, flaky UI E2E, no cheap hermetic build. The deterministic-gate guarantees you prove on Python/TS **may not transfer cleanly** to mobile. Treat mobile as a distinct R&D track with its own gate strategy, not "add stack #N."

---

## 15. Repository structure

Same top-level shape as v0.1, with these **deltas**:

- **Delete** `agents/orchestrator-agent/src/subagent_manager.py` and `task_tracker.py`; **collapse** the 6 standalone agent packages into declarative `AgentDefinition`s / `.claude/agents/*.md`; **reduce** `phase_gates.py` to a shell-out wrapper that runs commands and returns exit codes.
- **Add** the two hook bodies: `framework/templates/.claude/hooks/session-start.sh` + `session-end.sh` (caffeinated mode, §9).
- **Add** `risk-classifier/` (versioned, unit-tested path/content/reachability rules, §7.1).
- **Add** `reviewers/` (N heterogeneous reviewer prompts, §6.3) and `gates/` (runners that branch on exit codes).
- **Add** `runs/` (the append-only per-feature state/audit ledger, §5.3 / §11) and a real `benchmarks/` harness (§12), not just markdown stubs.
- **Add** supply-chain config: Syft SBOM, cosign signing, SLSA provenance, Checkov/Trivy IaC, semgrep + CodeQL, with **pinned & verified** scanner versions.
- **Add** progressive-delivery config (feature flags, Argo Rollouts/Flagger, OpenTelemetry SLOs) and GitHub **branch-protection rulesets + merge-queue + CODEOWNERS**.
- **Fix** the dependency tables: drop the star column (or cite repo + capture date), remove the archived Postgres/SQLite MCP rows, correct AoE (~2.6K) and Headroom (input-side compression), **pin concrete model IDs everywhere**, and update the commit trailer to the current lineup.

---

## 16. Success metrics

Replace v0.1's "50% faster / 67% tokens / 87% manual / ROI 700–1,674% / break-even #2" with **measured ranges from the pilot**, each labeled illustrative until populated from `benchmarks/`:

- **API spend:** ~$30–220/yr (illustrative; a rounding error). **ROI anchored in engineer-hours**, every assumption stated.
- **Quality:** per-diff coverage threshold, mutation score on changed files, flaky rate, **escape-defect rate**, **% auto-merged vs escalated**, mean self-heal retries/feature, MTTR via auto-rollback.
- **Latency:** time-to-first-actionable-signal, end-to-end wall-clock/feature (§13).
- **Adoption metrics** (stars, teams) are **post-launch only**, gated on a defensible README — never planning-phase commitments.

---

## 17. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Agent non-determinism makes gates flaky | Deterministic exit-code gates (not LLM self-report); `maxTurns` + `max_budget_usd`; flaky quarantine + SLA |
| SDK learning curve blows the orchestrator estimate | Spike the SDK in a throwaway repo first; 2–3× iteration multiplier |
| Cross-stack CI debugging explodes the timeline | Single-stack MVP; generalize only after ≥3 dogfooded features |
| Premature public launch → credibility hit + solo-maintainer burnout | Defer launch out of MVP; replace every unverified metric with measured numbers; launch privately first |
| Unattended overnight runs silently die on sleep | Caffeinated mode: PID-tied `caffeinate` + heartbeat + lid-open/clamshell guidance (§9) |
| Compounding bad edits / runaway cost | `enable_file_checkpointing` + `rewind_files`; bounded self-heal (≤3) → escalation; budget governor (§8.4) |
| Majority-vote review collapses under correlated bias | Heterogeneous models/prompts + reliability-weighted voting (§6.3) |
| Auto-merge ships a dangerous diff | Deterministic, fail-closed risk classifier → 2 human approvals on auth/PII/migration/IaC/payment/public-API (§7.1) |
| Self-healing agent games the gates | Immutable gate config + non-decreasing test/assertion/coverage invariants + no-skip + no-progress abort (§6.5) |
| Production regression with reduced human review | Feature flags + canary + SLO/error-budget auto-rollback / flag-kill (§6.4) |
| Agents are an attack surface (prompt injection, tool poisoning, backdoor PR) | Untrusted-content handling, least-privilege `disallowedTools`, risk-classifier backstop, brokered short-lived creds (§10) |
| Supply-chain / backdoored scanners | Pin + verify scanner versions/hashes; SBOM + signed provenance |
| Fabricated dependency data drives tool choice | Re-verify every dependency against its real repo before building on it; drop archived servers |
| "Confidence" gate is theater | Calibrate the formula against a labeled corpus; keep the threshold high until ≥~50 labeled outcomes (§6.2, §12) |

---

## 18. Goal-coverage map

| Goal | v0.1 verdict | How v2 delivers it (concrete mechanism) |
|---|---|---|
| **1. Custom SDLC orchestrator, specialized, high quality** | Partial (right skeleton; wrong "fine-tuning" frame; redundant manager) | SDK-built orchestrator (Opus 4.8) as a **durable state machine** (§5.3) delegating to declarative role-tiered agents; **"specialized, not fine-tuned"** via prompts/Skills/tools/CLAUDE.md/MCP/isolation (§5.6) |
| **2. Foolproof quality** | Not delivered (LLM self-assertion, advisory checklists) | Five-layer engine (§6): exit-code gates + blocking hooks + required checks + merge queue + CODEOWNERS; bounded, anti-gaming self-heal; checkpointing/rewind. Code is the only oracle |
| **3. Token-saving (caching/batching/context-editing/routing)** | Partial-wrong (Haiku-for-all; fabricated $10/M & 67%) | Role-based routing (§5.4), cache-layout policy (§8.3), isolation, context editing, scoped retrieval, batch-async-only; honest ranged cost model; runtime budget governor (§8.4) |
| **4. Fast dev + fast review/validation feedback** | Partial (fictional timers; wrong parallel math; universal human gate) | Gate-dependency DAG + measured time-to-first-signal (§13); real worktree parallelism on independent legs (§5.5); latency win = **confidence-gated auto-merge** of low-risk green diffs (§7) |
| **5. Avoid manual review** | Partial (single self-reviewer + blanket human gate = the opposite) | N heterogeneous refute-prompted reviewers + reliability-weighted vote + **calibrated numeric confidence** + **deterministic fail-closed risk classifier** → only high-risk/low-confidence escalate; the rest auto-merge (§6.2, §6.3, §7) |
| **6. High testing + strong CI/CD** | Partial-good (best area; weak total-coverage gate) | Per-diff coverage + diff-scoped mutation + property + Pact contract + flaky quarantine/SLA; SBOM + cosign/SLSA; branch protection + merge queue + CODEOWNERS; progressive delivery + SLO auto-rollback (§6.4) |
| **7. Open-source incl. Agent-of-Empires (not limited to)** | Delivered on positioning, false on facts (83× star error) | AoE corrected to ~2.6K, scoped as **optional operator dashboard** never the backbone; alternatives listed; cite repos not stars; archived MCPs dropped (§5.8) |
| **8. Caffeinated mode** | Absent | PID-tied `caffeinate -i -m -w <ORCH_PID> -t <timeout>` + **completion-aware heartbeat** that releases on idle/escalation while staying alive; AC/battery gating; zombie reaper; lid-closed warning; opt-in flag; cross-platform parity (§9) |

---

## Appendix A: Corrections from v0.1

### A1. Star counts / repo facts (verified 2026-06-20)

| v0.1 claim | Corrected | Source |
|---|---|---|
| Agent-of-Empires **218.3K stars**, "session manager" | **2,613 stars**, MIT, Rust; off by ~83×. Optional operator dashboard, not backbone | `api.github.com/repos/agent-of-empires/agent-of-empires` |
| (Implied) AoE > Claude Code | Claude Code **133,404** ≈ **51× larger** than AoE | `api.github.com/repos/anthropics/claude-code` |
| Claude Code 133.3K | ~133.4K — correct, keep | same |
| Agent SDK Python 7.36K | 7,364 — correct, keep | `api.github.com/repos/anthropics/claude-agent-sdk-python` |
| GitHub MCP 30.8K / Playwright 34.1K / FastMCP 25.7K | All verified correct — keep | respective repos |
| **Postgres MCP 15.6K + SQLite MCP 15.6K** | **Fabricated + duplicated.** Both are **archived** subdirs of `modelcontextprotocol/servers` ("no longer maintained"). Remove | `github.com/modelcontextprotocol/servers-archived` |
| Headroom 39.3K, "60–95% **output** compression" | ~36–40K, Apache-2.0; it is **input/context** compression ("before they reach the LLM"), self-reported. Star count was ~right; the *characterization* was wrong | `github.com/chopratejas/headroom` |
| AWS MCP 9.3K, Agent SDK TS 1.55K, Docker MCP "-" | Re-verify before publishing; **drop the star column** and cite repos + capture date | — |

### A2. Token / pricing / ROI

| v0.1 claim | Corrected |
|---|---|
| "67% reduction (55K → 18K)" | Internally contradicted (the plan's own table sums to 41K = 25%). Both endpoints unsourced. Replace with a measured pilot range |
| "$10/M tokens" flat | No Claude model is flat-rate. Per MTok in/out: **Opus 4.8 $5/$25, Sonnet 4.6 $3/$15, Haiku 4.5 $1/$5, Fable 5 $10/$50**. Output = 5× input |
| "caching 60% + batch 40% + Headroom 20% = 67%" | Wrong on every term and they don't compose. Cache **read = 0.1× (90% off cached prefix only)**, **write = 1.25×/2×**; batch = **flat 50%, async-only**; Headroom = input-side, fights caching. Report each independently |
| Per-feature baseline (review 30min=15K, etc.) | Conceptually broken — assigns *model-token* cost to *human* minutes (a human reviewing a PR spends 0 model tokens). Re-derive from instrumented runs |
| ROI 700% vs 1,674% | 1,674% double-counts. Define once: `(baseline − (setup + optimized run)) / setup`. Anchor in **dollars/engineer-hours**, not tokens |
| Break-even #2 / #3 / #3–4 | Stated three ways. On v0.1's own table, first positive cumulative is **feature #3**. Better: break even in **engineer-hours** |
| "$52.80/yr, 1.97M tokens, $33.10 saved" | Three incompatible optimized totals + false cent-precision on a non-existent unit. Honest API spend **~$30–220/yr** |

### A3. Model / framing

| v0.1 | Corrected |
|---|---|
| Version-less "Opus" / "Haiku" | Pin **Opus 4.8 / Sonnet 4.6 / Haiku 4.5 / Fable 5** everywhere. Haiku 4.5 = 200K ctx vs 1M |
| "Haiku for all sub-agents" | False economy. Haiku for read-only/mechanical only; builders/reviewers/security need Sonnet 4.6+ |
| "Fine-tuned orchestrator" | Fine-tuning of current models **does not exist**. Reframe as **specialized** (prompts/Skills/tools/CLAUDE.md/MCP/context) |
| `subagent_manager.py` | Redundant — the SDK spawns/manages subagents natively. Delete |
| Commit trailer "Claude Opus 4.6" | Update to current lineup |

---

## Appendix B: References (captured 2026-06-20)

- GitHub REST API (`api.github.com/repos/...`) for all star counts (Agent-of-Empires, Claude Code, Claude Agent SDK Python/TS, GitHub MCP, Playwright MCP, FastMCP, modelcontextprotocol/servers + servers-archived, Headroom).
- `platform.claude.com` pricing & context-editing / prompt-caching documentation for per-model prices, cache read/write multipliers, Batch API 50%, and context-editing strategies.
- `code.claude.com` — Claude Agent SDK, subagents, hooks, worktrees, Agent Teams, `/batch`.
- Huang et al., *Large Language Models Cannot Self-Correct Reasoning Yet*, ICLR 2024 (arXiv:2310.01798) — basis for "code is the oracle."
- `man caffeinate`, `pmset` — macOS power assertions; Linux `systemd-inhibit`; Windows `SetThreadExecutionState` / `powercfg`.

> **Every quantitative figure here is either (a) cited above with a 2026-06-20 capture date, or (b) explicitly labeled _illustrative_ and owed to a measured pilot. Nothing in this plan should be quoted as fact without one of those two backings.**
