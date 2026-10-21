---
type: index
area: code
scope: all-projects
tags: [policy, index, cross-project]
---

# Code — Cross-Project Policies

Policies that apply across all managed projects. These are deployed to `Obsidian/code/`
by the vault engine during workspace initialization.

## Policies

- [[product-development-workflow]] — End-to-end product lifecycle from market intelligence through production operation
- [[development-process]] — Sprint mechanics: completion checklist, project doc standards, release versioning, retrospective requirements
- [[integration-verification-policy]] — Quality gates: workflow-level acceptance criteria, pipeline smoke tests, CLI contract verification
- [[oss-health-policy]] — Dependency health evaluation: Green/Yellow/Red scoring with six evaluation criteria
- [[allowed-licenses]] — Permitted open source licenses with enforcement workflow and audit tools
- [[supply-chain-protection]] — Supply chain attack defense: 7-day quarantine, lockfile integrity, SCA scanning, secrets scanning, per-ecosystem controls
- [[cli-standards]] — Shared Click-based CLI conventions: config loading, auth group, exit codes, output conventions, async bridge, contract testing
- [[scrub-skills-quick-reference]] — One-page summary of the mid-sprint `/simplify` → `/code-review` → `/refactor-clean` scrub-skills order
- [[pii-handling-policy]] — PII and secrets encryption: himitsubako-preferred store, `[SEC-NNN]` / `[PII-NNN]` reference format, refuse-fallback, operator-configured exclusions
