# Phase Model

OWB organizes workspace maturity into phases. Phase 0 (cold start) and Phase 1 (interactive sessions) are fully operational and represent the project's scope ceiling. Phase 2 and Phase 3 are documented below for historical context but have been extracted to a separate product (see DRN-066).

## Phase Overview

| Phase | Name | Description | Status |
|-------|------|-------------|--------|
| **0** | Cold Start | First `owb init`. Workspace scaffolded, no sessions yet. | Complete |
| **1** | Interactive | Human drives sessions. Vault captures decisions and context. Security scanner active. Token tracking available. | **Operational** |
| **2** | Build Farm | Hybrid model routing: cheaper models for code generation, Claude for oversight. Sandbox execution. Cost optimization. | Out of scope (see [DRN-066](https://github.com/originalrgsec/open-workspace-builder)) |
| **3** | Director Model | Orchestrator manages multiple agents. Delegation policies. | Out of scope (see [DRN-066](https://github.com/originalrgsec/open-workspace-builder)) |

## Phase 1: Interactive (Current)

Phase 1 is fully operational. This is the standard OWB experience:

- **Workspace scaffolding**: `owb init` generates vault, context files, skills, development rules
- **Drift detection**: `owb diff` and `owb migrate` keep workspaces current
- **Security scanning**: Three-layer scanner (structural, pattern, semantic) blocks malicious content
- **Skill evaluation**: `owb eval` scores skills before they enter the workspace
- **Token tracking**: `owb metrics tokens` reports consumption and API-equivalent costs
- **Cost management**: Local ledger, budget alerts, monthly forecasting, per-story attribution
- **Supply chain scanning**: `owb audit deps` and `owb audit package` scan dependencies
- **Stage tracking**: `owb stage status` and `owb stage promote` manage workspace maturity progression
- **Pre-commit hooks and secrets scanning**: `owb init` deploys `.pre-commit-config.yaml` with gitleaks and ruff hooks
- **Package quarantine and pin advancement**: 7-day quarantine via `uv.toml`, `owb audit pins` checks for stale pins
- **Pre-install SCA gate**: `owb audit package` blocks installation of packages that fail health or license checks
- **Trivy multi-ecosystem scanning**: `owb audit deps` uses Trivy for vulnerability scanning across Python, Node, Go, and Rust ecosystems
- **Baseline metrics collection**: `owb metrics baseline` captures workspace health snapshots for trend tracking

All CLI commands documented in the [CLI Reference](../reference/cli.md) are Phase 1 features.

## Phase 2 and Phase 3 (Out of Scope)

> **DRN-066 (2026-04-09):** OWB is rescoped to solo-developer-only. Phase 2 (Build Farm) and Phase 3 (Director Model) have been extracted to a separate Volcanix commercial product. OWB remains at Phase 1 as its operational ceiling. The existing LiteLLM integration means OWB's codebase is already model-agnostic; if your needs grow beyond Phase 1, the commercial platform will address multi-agent orchestration, sandbox execution, and hybrid model routing.

Research findings from the Sprint 13 model hosting spike (Qwen 3.5 27B, Together AI, Ollama) informed this decision. The Max plan's subsidy makes hybrid routing uneconomical for a solo developer at current volume. Phase 2 becomes relevant when programmatic API access or regulatory local-execution requirements apply — use cases served by the commercial platform.

## Checking Your Phase

Use `owb stage status` to evaluate exit criteria for your current phase. Use `owb stage promote` to advance when all criteria are met.

If you ran `owb init` and are using the workspace in interactive sessions, you are in Phase 1.
