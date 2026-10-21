---
type: policy-reference
created: 2026-04-18
updated: 2026-04-19
tags: [policy, scrub-skills, development-process, quick-reference]
---

# Scrub Skills — Quick Reference

One-page answer to "when do I run `/simplify`?". Full policy: [[code/development-process|development-process]] §Scrub Skills.

## Order (strict)

1. `/simplify` — clarity + reuse pass. Non-destructive.
2. `/code-review` — correctness + security + design at HIGH / MED / LOW.
3. `/refactor-clean` — destructive dead-code removal + public-API changelog.

Optional: a static-type scrub (e.g., pyright strict-mode triage) runs alongside the trio only when the project-local static-typing policy has been updated since the last scrub.

## When

- After the sprint's implementation stories are merged to the integration branch, before sprint close.
- Every sprint that touches > 0 lines of source code. Vault-only or docs-only sprints skip the scrub.

## Blocking rules

- `/simplify`: blocking if any suggestion is behaviour-changing; advisory if cosmetic.
- `/code-review`: blocking for CRITICAL and HIGH; MED / LOW roll into a tech-debt bundle story unless the bundle exceeds a 2-pt budget.
- `/refactor-clean`: blocking for the sprint that runs it. The downstream absorption story (for projects that consume your package) is blocking for that consumer's next sprint.

## Logging

Sprint-close session log must name which scrub skills ran this sprint and link to the PRs. Sprints that skip note "scrub skipped" and the reason (small-scope, vault-only, docs-only, etc.).
