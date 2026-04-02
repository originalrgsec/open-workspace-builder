# Phase Model

OWB organizes workspace maturity into four phases. Each phase adds capabilities on top of the previous one. Most users operate in Phase 1 and that is the recommended starting point.

## Phase Overview

| Phase | Name | Description | Status |
|-------|------|-------------|--------|
| **0** | Cold Start | First `owb init`. Workspace scaffolded, no sessions yet. | Complete |
| **1** | Interactive | Human drives sessions. Vault captures decisions and context. Security scanner active. Token tracking available. | **Operational** |
| **2** | Build Farm | Hybrid model routing: cheaper models for code generation, Claude for oversight. Sandbox execution. Cost optimization. | In design |
| **3** | Director Model | Orchestrator manages multiple agents. Delegation policies. Team infrastructure. | Concept |

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

## Phase 2: Build Farm (In Design)

Phase 2 introduces hybrid model routing to reduce costs and improve throughput. The design is informed by the [model hosting research spike](https://github.com/originalrgsec/open-workspace-builder) completed in Sprint 13.

### What Phase 2 will offer

- **Hybrid model routing**: Route code generation tasks to cheaper open-weight models (e.g., Qwen 3.5 27B via Together AI or local Ollama) while keeping Claude for oversight, review, and complex reasoning
- **Sandbox execution**: Untrusted model output runs in isolated environments before merging
- **Environment portability**: `owb env bootstrap` sets up reproducible development environments with phase-appropriate tooling
- **Cost optimization**: Estimated 30-80% reduction in API costs depending on deployment model

### Key findings from research

- **Model**: Qwen 3.5 27B (dense) offers the best coding performance per GB of RAM (SWE-bench 72.4, LiveCodeBench 80.7, fits in ~17 GB at Q4)
- **Provider**: Together AI is the recommended US-based provider (broadest Qwen catalog, competitive pricing, native LiteLLM support)
- **Local framework**: Ollama for current hardware (native Anthropic API compatibility), MLX/vllm-mlx for future high-memory systems
- **Economics**: The Max plan's 3.5x subsidy makes hybrid uneconomical for a single user at current volume. Hybrid becomes relevant at team scale or when programmatic API access is needed.

### When to consider Phase 2

Phase 2 preparation is relevant if any of these apply:

1. You need to scale to multiple users and per-seat costs matter
2. You need programmatic API access for automation pipelines
3. Regulatory requirements mandate local model execution
4. Your consumption exceeds what the Max plan subsidizes

If none of these apply, Phase 1 is the right choice. The existing LiteLLM integration means OWB's codebase is already model-agnostic; Phase 2 is about operational infrastructure, not code changes.

## Phase 3: Director Model (Concept)

Phase 3 envisions an orchestrator that manages multiple agents working on different parts of a project simultaneously. This phase is not in active development. Key concepts:

- Delegation policies controlling which tasks route to which agents
- Sandbox and permission boundaries per agent
- Team infrastructure for shared model serving
- Delegation policies controlling which tasks route to which agents (stage promotion moved to Phase 1)

Phase 3 depends on orchestrator ecosystem maturity (e.g., Claude Agent Teams, which remain experimental as of March 2026).

## Checking Your Phase

Use `owb stage status` to evaluate exit criteria for your current phase. Use `owb stage promote` to advance when all criteria are met.

If you ran `owb init` and are using the workspace in interactive sessions, you are in Phase 1.
