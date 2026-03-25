---
type: policy
scope: all-projects
created: 2026-03-16
updated: 2026-03-25
tags: [policy, process, sprint, release-notes, metrics]
---

# Development Process

## Purpose

This document defines the project lifecycle standards that apply across all managed projects where AI-assisted development handles implementation. It covers the process layer: how to run a sprint end-to-end, what happens at sprint completion, and how to maintain project documentation alongside code.

This sits above two other layers that are already documented:

- **Coding layer:** ECC rules (`development-workflow.md`, `git-workflow.md`, `coding-style.md`, `testing.md`, `security.md`) define how to write code within a session: TDD cycle, conventional commits, file size limits, coverage targets, security pre-commit checks.
- **Quality gate layer:** integration-verification-policy and oss-health-policy define how to verify code: workflow-level acceptance criteria, pipeline smoke tests, CLI contract verification, dependency health checks.

This document defines how to run a sprint end-to-end and what artifacts must be updated at each phase.

## Sprint Completion Checklist

Every sprint ends with the following before the final PR is merged:

### 1. Stories Complete

All stories in the sprint pass their acceptance criteria. Tests are green. The pipeline smoke test (per integration-verification-policy) has been run.

### 2. Project Docs Updated

Project documents (PRD, ADR, SDR, threat model, specs) are updated to reflect any design changes made during the sprint. This includes new use cases, architectural decisions, module designs, threat analysis for new components, and story additions or modifications. Project docs ship in the same repo as the code and must stay in sync.

Changes to project docs during a sprint are expected and normal. The goal is not to prevent doc changes but to ensure they are captured before the sprint closes, not left as undocumented drift.

### 3. Release Notes Updated

Update CHANGELOG.md in the repo root with a summary of code and project doc changes. Use Keep a Changelog format (https://keepachangelog.com/en/1.1.0/). Standard sections: Added, Changed, Deprecated, Removed, Fixed, Security.

Write or update the detailed manifest in `docs/releases/v<version>.md`. The manifest provides a full inventory of everything that changed, categorized by: Code (modules added/modified/removed), Project Docs (document changes), Content (skills, templates, ECC updates), Infrastructure (CI, config, packaging), Tests (count and category breakdown), Stories Completed (list with one-line descriptions).

The CHANGELOG entry links to the manifest for the full picture.

Tag the release after the PR merges.

### 4. Metrics Recorded (If Pipeline Metrics Are Active)

For projects with an active metrics system, record metrics entries for each pipeline run completed during the sprint. This is not a retroactive data entry exercise; metrics should be recorded as runs complete throughout the sprint.

## Project Documentation Standards

### Which Docs

Every project that reaches the Design phase or beyond maintains the following documents in its repo:

- **PRD** — use cases, goals, personas, success criteria
- **ADR** — C4 model, architectural decisions with alternatives and consequences, technology stack, data flow diagrams
- **SDR** — module designs with interfaces, data schemas, story breakdown, sprint plan
- **Threat Model** — STRIDE analysis per DFD element, risk assessment, mitigations with NIST 800-53 mapping

Additional docs (specs, retros, session logs) are added as needed per project.

### When to Update

Project docs are updated during a sprint when:

- A new feature or capability is added (PRD: use case, goal; ADR: decision if architectural; SDR: module design, story; Threat Model: if new data store or data flow)
- An existing design changes during implementation (all affected docs)
- A retrospective identifies a process or design gap (relevant doc + cross-project policy if applicable)

The sprint completion checklist (item 2) is the backstop, not the primary update trigger. Docs should be updated as decisions are made, not batched at sprint end.

### Cross-Project Policies

When a sprint produces a finding that applies beyond the originating project, it becomes a cross-project policy in `code/`. Examples:

- integration-verification-policy — originated from a Phase 1 retrospective identifying module isolation failures
- oss-health-policy — originated from dependency evaluation across multiple projects
- This document — originated from a sprint design discussion on metrics and release notes

## Retrospective Requirements

Retrospectives are conducted after each sprint, phase, or significant incident. The retro template lives at `_templates/retrospective.md`.

### When to Retro

A retrospective is required after any sprint completion, any production incident or feature regression, any phase transition (design → implementation → production), and any session where more than two bugs are discovered that trace to a common root cause.

### Linked Deliverables Are Mandatory

Every retro must produce at least one concrete deliverable linked in the "Linked Deliverables" section. Acceptable deliverable types: bug stories, new stories, cross-project policy documents, process changes to working-style.md or other process docs, config or template updates, and additions to the sprint acceptance gate.

A retro that identifies problems but links to zero deliverables is incomplete. The deliverable does not need to be implemented immediately, but it must be filed and tracked.

### Numbering Convention

Retros use a global sequential ID: `RETRO-NNN`. The numbering is global across all projects because retros frequently span multiple projects or cover process-level concerns that are not scoped to a single codebase. The next available ID is tracked in the `next_id` frontmatter field of `self/retro-log.md`.

Retro files are named `RETRO-NNN-short-description.md`.

### Retro Log and File Locations

All retros are indexed in `self/retro-log.md` with a summary, linked deliverables reference, and open items for the next retro. Standalone retros (those with root cause analysis, multiple issues, or significant length) live in `self/retros/RETRO-NNN-*.md`. Lightweight retros are inline in the retro-log with the same RETRO-NNN heading.

Retros do not live in project folders. Even when a retro is triggered by a single project, the findings and process changes often apply cross-project. The retro-log and `self/retros/` are the canonical locations.

### Follow-Through Verification

The "Open Items for Next Retro" section in each retro entry creates a verification chain. The next retro must address those open items explicitly, confirming whether the actions taken actually improved the process. If an open item has not been addressed by the next retro, it escalates to a standing item until resolved.

## Story ID Convention

Story IDs use a three-character project prefix followed by a sequential number: `{PREFIX}-S{NNN}`. This prevents ambiguity when referencing stories across projects in session logs, decision records, and the bootstrap file.

Assign a unique three-character prefix per project and maintain a lookup table in this document or in the vault. File names follow the pattern `{PREFIX}-S{NNN}-short-description.md`. The frontmatter `id` field uses the same prefixed format.

Story numbers are sequential per project. Stories in a later sprint must have higher numbers than stories in the preceding sprint for the same project.

## Release Versioning

Projects use Semantic Versioning (https://semver.org/). For projects not yet at 1.0, minor version bumps indicate feature additions (sprint completion) and patch bumps indicate bug fixes.

## Applying This Policy

This policy applies to all projects with a git repo and sprint-based development. Reference this document in each project's workspace config or SDR sprint plan section rather than duplicating the checklist inline.

For existing projects, adopt the sprint completion checklist starting with the next sprint. Retroactive release notes for prior sprints are optional but recommended for projects that have shipped code.
