# Vault Policy Documents

## Authoritative Process Layer

The Obsidian vault at `Obsidian/code/` contains policy documents that govern how all
Volcanix projects are built and operated. These policies sit above the ECC rules in this
directory and are the authoritative source for process decisions.

When any policy document conflicts with an ECC rule, the vault policy takes precedence.

## Policy Documents

Read these from the vault before making process decisions:

1. **`Obsidian/code/product-development-workflow.md`** — End-to-end product lifecycle:
   market intelligence, ideation, planning, sprint execution, release, operation. Defines
   how the human-agent team works together across all phases. Covers how vault templates
   (PRD, SDR, ADR, threat model) map to lifecycle phases.

2. **`Obsidian/code/development-process.md`** — Sprint mechanics: completion checklist,
   release notes conventions, versioning policy, project documentation update requirements.
   Every sprint must pass this checklist before the final PR merges.

3. **`Obsidian/code/integration-verification-policy.md`** — Quality gates: workflow-level
   acceptance criteria (not just unit-level), pipeline smoke tests, CLI contract verification.
   Origin: 13 post-production bugs in ingest-pipeline Phase 1 all traced to modules tested
   in isolation but never wired end-to-end.

4. **`Obsidian/code/oss-health-policy.md`** — Dependency health evaluation: quantitative
   scoring (maintenance cadence, bus factor, security posture, community health), Green/Yellow/Red
   thresholds, adoption and monitoring requirements.

5. **`Obsidian/code/allowed-licenses.md`** — Approved open source license list for dependencies.

## When to Consult Policies

| Activity | Policy to Read |
|----------|---------------|
| Planning a feature or sprint | product-development-workflow, development-process |
| Writing acceptance criteria | integration-verification-policy |
| Completing a sprint | development-process (completion checklist) |
| Reviewing code | integration-verification-policy (wiring checks) |
| Adding a dependency | oss-health-policy, allowed-licenses |
| Writing tests | integration-verification-policy (workflow-level AC) |
| Release preparation | development-process (release notes, versioning) |
