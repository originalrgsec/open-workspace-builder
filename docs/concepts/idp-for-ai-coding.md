# IDP for AI Coding

An **Internal Developer Platform (IDP)** is a self-service layer that standardizes how developers set up, operate, and maintain their development environments. OWB applies this concept to AI coding assistants: it provides a single CLI that scaffolds a structured workspace, enforces security policies, and keeps the workspace current as projects evolve.

## What OWB provides as an IDP

| IDP Concept | OWB Implementation |
|---|---|
| **Golden path** | `owb init` generates a fully configured workspace from a single command. The interactive wizard guides users through model selection, vault structure, and security settings. |
| **Environment consistency** | Every workspace follows the same structural conventions: knowledge vault, context files, development rules, skills, and a workspace config entry point. |
| **Self-service provisioning** | No manual setup or file copying. Install from PyPI, run `owb init`, answer the wizard prompts. Fifteen minutes from install to a working workspace. |
| **Drift detection** | `owb diff` compares your workspace against the reference and reports divergence. `owb migrate` brings it up to date with interactive file-by-file review. |
| **Upstream sync** | `owb update` pulls content from configured upstream sources, runs security scanning on every change, and presents accept/reject decisions. |

## What OWB is not

OWB is not a hosted platform, a SaaS product, or a team collaboration tool. It is a CLI that runs on your machine, manages files in your filesystem, and exits when it is done. There is no server, no account, no telemetry.

OWB is designed for individual developers, not collaborative teams. If your organization needs shared workspace management, build farm orchestration, or multi-agent coordination, those capabilities are served by a separate product.

## The buyer

OWB's IDP value proposition is relevant to developers who:

- Use AI coding assistants daily across multiple projects
- Want repeatable workspace setup without manual configuration
- Need security scanning of third-party content (skills, agents, rules) before it enters their workspace
- Want to keep their workspace current with upstream improvements without losing customizations

## Related concepts

- [Policy as Code](policy-as-code.md) — how OWB enforces security and development policies
- [Supply Chain Security](supply-chain-security.md) — how OWB protects the workspace dependency chain
- [Phase Model](phases.md) — the workspace maturity progression
- [Architecture](architecture.md) — OWB's internal design
