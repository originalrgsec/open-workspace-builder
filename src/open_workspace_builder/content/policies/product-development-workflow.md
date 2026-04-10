---
type: policy
scope: all-projects
created: 2026-03-23
updated: 2026-03-25
tags: [policy, process, workflow, lifecycle]
---

# Product Development Workflow

## Purpose

This document describes the end-to-end workflow for building, maintaining, and operating software products using AI-assisted development. It covers every phase from market intelligence through production operation, explains how each vault template and process document fits into the lifecycle, and documents how the human-agent team executes work.

This is the "how we work" document. It sits alongside two companion documents:

- [[code/development-process]] — the sprint mechanics (completion checklist, release notes, versioning)
- [[code/integration-verification-policy]] — the quality gate (acceptance criteria, smoke tests, CLI contract)

## The Product Lifecycle

### Phase 1: Market Intelligence and Ideation

New product ideas originate from market research processed through the Obsidian vault's research pipeline. Content is collected from sources relevant to the product domain (social media bookmarks, RSS feeds, email newsletters, academic papers, industry reports) and lands in `research/inbox/` for triage. The triage process classifies each item by topic, assigns project tags, and routes it to `research/processed/` or `research/inbox/low-priority/`.

Mobile captures (ideas, observations, links captured on the go) enter through `research/mobile-inbox/` and are triaged separately.

When research reveals an opportunity worth pursuing, a new project entry is added to `_bootstrap.md` under the appropriate tier. At this stage the project has a one-line description and a phase of "Concept."

**Templates used:** `research-note.md` for processed research, `mobile-inbox.md` for mobile captures.

### Phase 2: Design

Design produces the foundational documents that define what the product is, how it is built, and what threats it faces. These documents live in the project's repo (not just the vault) and are maintained throughout the project's life.

The design phase produces four core documents in order:

1. **PRD (Product Requirements Document)** — Use cases, personas, goals, success criteria, and scope boundaries. Written from the owner's perspective. Template: `_templates/prd.md`.

2. **ADR (Architecture Decision Record)** — C4 model (context, container, component, code), architectural decisions with alternatives considered, technology stack with justification, data flow diagrams, and integration points. Template: `_templates/adr.md`.

3. **SDR (Software Design Record)** — Module-level design: interfaces, data schemas, API contracts, configuration, error handling strategy, routing matrix (if applicable), testing strategy, story breakdown, and sprint plan. The SDR is the implementation blueprint that the AI agent reads. Template: `_templates/sdr.md`.

4. **Threat Model** — STRIDE analysis per data flow diagram element, risk assessment, mitigations mapped to NIST 800-53 controls. Template: `_templates/threat-model.md`.

Design happens collaboratively between the owner and the AI agent. The owner and agent iterate on each document through conversation, with the agent asking clarifying questions per the question-first workflow. Architectural decisions that affect cost, security, external dependencies, or operational complexity are escalated to the owner per the decision authority framework.

Cross-project architectural decisions are indexed in `decisions/_index.md` using the `decision-record.md` template. Before recommending technology or architecture choices, the agent reads this index to check for prior decisions.

**Key outputs:** PRD, ADR, SDR, threat model, project `_index.md`, initial `status.md`.

### Phase 3: Story Writing and Sprint Planning

Stories are derived from the SDR's story breakdown section. Each story uses the `_templates/story.md` template, which enforces:

- Workflow-level acceptance criteria (not module-level — per [[code/integration-verification-policy]])
- Given/When/Then format with CLI commands as the "When"
- Edge cases and error cases as explicit sections
- Integration contracts when a story's output feeds another story's input
- Integration verification plan (what system boundaries are touched and how they are verified beyond unit tests)
- Test file mapping (filled in during implementation)

The story template supports two modes via the `deliverable` frontmatter field:
- `deliverable: code` (default) — standard implementation story with AC/edge/error sections
- `deliverable: decision` or `deliverable: research` — research spike mode with tracks, evaluation criteria, time box, and outcome sections (embedded as HTML comments in the template; expand when needed)

Stories are grouped into sprints in the SDR. The sprint plan specifies which stories ship together and what is demonstrable at sprint end.

Stories and sprint tracking live in the Obsidian vault under `projects/<tier>/<project>/stories/`. Status is tracked in `status.md` with a story status table.

### Phase 4: Implementation

Implementation follows TDD (test-driven development). The AI agent reads the `.claude/CLAUDE.md` in the project repo, the relevant story files, and writes failing tests before writing implementation code.

The execution model uses CLI prompts. Each prompt specifies a target branch, the stories to implement, the files to read for context, and the test/lint commands to run.

Sprint completion follows the checklist in [[code/development-process]]: stories pass acceptance criteria, project docs are updated, release notes written, and metrics recorded.

**Security drift baseline:** When a new project repo is created, run `owb security drift <project-path> --update-baseline` and commit the resulting `.owb/drift-baseline.json`. This baseline enables detection of unauthorized or accidental changes to project directives. See [[code/development-process#Security Drift Baseline]] for update and maintenance requirements.

**Metrics rhythm:** At sprint start, run `owb metrics record` to flush unrecorded sessions into the ledger. During the sprint, tag sessions with story IDs (`owb metrics record --story {PREFIX}-S{NNN}`) at natural breakpoints. At sprint end, run a final `owb metrics record` and generate a cost summary with `owb metrics by-story --since {sprint-start-date}`. This applies to every project, every sprint. When a new project repo is created, run `owb metrics baseline` once to establish the zero-point snapshot.

### Phase 5: Quality Assurance

QA is layered:

1. **TDD tests** — Written before implementation code. Each acceptance criterion, edge case, and error case maps to at least one test.
2. **CLI contract test** — Asserts every documented command exists and responds to `--help`. Mandatory per [[code/integration-verification-policy]].
3. **Integration tests** — Exercise the full data flow with mock data sources and real modules. Catches the "modules tested in isolation but never wired" failure class.
4. **Pipeline smoke test** — Run the primary commands and verify end-to-end output. Part of the sprint acceptance gate.
5. **OSS health check** — Before adopting any new dependency, evaluate it against the [[code/oss-health-policy]].
6. **Secrets scanning** — Run the secrets scanner (gitleaks or ggshield) against staged changes before every commit. Pre-commit hooks enforce this automatically. See [[code/supply-chain-protection]].
7. **Supply chain verification** — Enforce 7-day package quarantine via `uv exclude-newer`, run `owb audit deps` and `owb audit package` before adopting dependencies, verify lockfile integrity. See [[code/supply-chain-protection]].
8. **Supply chain gate** — Run `owb audit pins` to verify all dependencies pass the quarantine window. Run `owb audit gate --all` to verify all direct dependencies pass the full scan battery (CVEs, malware indicators, advisory flags).
9. **Pre-commit hooks** — Every project must have pre-commit hooks installed (`owb security hooks install`). The default set runs gitleaks (secrets), ruff (lint + format), trivy (dependency vulnerabilities), and semgrep (SAST) on every commit. These are commit-time gates that catch issues before code enters the repository.

### Phase 6: Retrospective

Every sprint, phase transition, or significant incident triggers a retrospective. The retro template (`_templates/retrospective.md`) requires root cause analysis, action items, and linked deliverables. Every retro must produce at least one concrete deliverable (bug story, policy change, process update) — a retro with findings but no linked deliverables is incomplete.

Retros use global sequential RETRO-NNN numbering and live in `self/retros/`. The retro-log at `self/retro-log.md` indexes all retros with summaries and tracks the `next_id`. Each retro's "Open Items for Next Retro" section creates a verification chain — the next retro must address those items explicitly.

Full requirements: [[code/development-process#Retrospective Requirements]].

### Phase 7: Production Operation

Production systems run on the target platform's native scheduling mechanism (launchd on macOS, systemd on Linux, Task Scheduler on Windows, or a cloud scheduler for hosted services). Schedule installation and management are handled through the project's CLI. Health monitoring uses the project's alerting module and health check commands.

Workspace moves, config changes, and infrastructure updates follow the standing procedures in `self/setup-journal.md`, which includes the workspace move checklist.

## Template Reference

| Template | Phase | Purpose |
|----------|-------|---------|
| `research-note.md` | Intelligence | Processed research with project tags and relevance summary |
| `mobile-inbox.md` | Intelligence | Mobile capture with triage instructions |
| `prd.md` | Design | Product requirements: use cases, goals, personas |
| `adr.md` | Design | Architecture: C4 model, decisions, technology stack |
| `sdr.md` | Design | Implementation blueprint: modules, schemas, stories, sprints |
| `threat-model.md` | Design | STRIDE analysis per DFD element with NIST 800-53 mapping |
| `decision-record.md` | Design | Cross-project architectural decision with alternatives |
| `story.md` | Sprint planning | Acceptance criteria, edge/error cases, integration contracts. Set `deliverable: decision` and uncomment the Research Spike sections for time-boxed research spikes. |
| `session-log.md` | Implementation | Session-level record of decisions and changes |
| `retrospective.md` | Retro | Root cause analysis, action items, linked deliverables |
| `tech-debt.md` | Any | Deferred work tracked with priority and trigger conditions |
| `roadmap.md` | Planning | Multi-sprint feature roadmap |
| `spec.md` | Design | Standalone spec for complex subsystems (supplements SDR) |
| `readme.md` | Release | GitHub README generated from project docs |

## Process Documents

| Document | Location | Purpose |
|----------|----------|---------|
| This document | `code/product-development-workflow.md` | End-to-end lifecycle overview |
| Development Process | `code/development-process.md` | Sprint mechanics, release notes, versioning |
| Integration Verification | `code/integration-verification-policy.md` | Quality gates, acceptance criteria standards |
| OSS Health Policy | `code/oss-health-policy.md` | Dependency adoption risk evaluation |
| Allowed Licenses | `code/allowed-licenses.md` | Permitted open source licenses |
| Supply Chain Protection | `code/supply-chain-protection.md` | 7-day quarantine, lockfile integrity, SCA/secrets scanning |
| Setup Journal | `self/setup-journal.md` | Configuration history and standing procedures |
| Retro Log | `self/retro-log.md` | Global retrospective index |

## Links

- Development Process: [[code/development-process]]
- Integration Verification: [[code/integration-verification-policy]]
- OSS Health Policy: [[code/oss-health-policy]]
- Retro Log: [[self/retro-log]]
