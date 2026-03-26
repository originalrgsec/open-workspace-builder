# Lifecycle, Agents, and Policy Enforcement

OWB ships a set of governance policies, ECC agents, and orchestration skills that together form a complete product development process. The policies define what must happen at each phase. The agents and skills execute those policies automatically, triggered by the natural context of the work at hand. The developer does not need to remember the process — the agents enforce it.

This page explains how the product lifecycle, software development lifecycle, agent catalog, and policy enforcement rules connect to each other.

## Product Lifecycle

The product lifecycle defines the phases a project moves through from concept to production. Each phase produces specific artifacts and has specific quality gates.

```mermaid
graph LR
    P1["<b>Intelligence</b><br/><i>Research, ideation,<br/>opportunity identification</i>"]:::phase
    P2["<b>Design</b><br/><i>PRD, ADR, SDR,<br/>threat model</i>"]:::phase
    P3["<b>Plan</b><br/><i>Story writing,<br/>sprint planning</i>"]:::phase
    P4["<b>Build</b><br/><i>TDD implementation,<br/>code review</i>"]:::phase
    P5["<b>Verify</b><br/><i>QA layers, smoke test,<br/>security scan</i>"]:::phase
    P6["<b>Release</b><br/><i>Sprint close, retro,<br/>changelog, tag</i>"]:::phase
    P7["<b>Operate</b><br/><i>Production monitoring,<br/>drift detection</i>"]:::phase

    P1 --> P2 --> P3 --> P4 --> P5 --> P6 --> P7
    P6 -->|"next sprint"| P3
    P7 -->|"new opportunity"| P1

    classDef phase fill:#1B2A4A,color:#F0F0F0,stroke:#D4A017,stroke-width:2px
```

Each phase maps to specific governance documents, agent capabilities, and quality gates:

| Phase | Governance Document | Key Agents and Skills | Quality Gate |
|-------|-------------------|----------------------|-------------|
| Intelligence | product-development-workflow | mobile-inbox-triage | Research tagged and processed |
| Design | product-development-workflow | architect, planner | PRD, ADR, SDR, threat model complete |
| Plan | development-process | write-story, sprint-plan | Stories have workflow-level AC |
| Build | development-workflow, testing | tdd-guide, code-reviewer, build-error-resolver | Tests green, 80%+ coverage |
| Verify | integration-verification-policy | security-reviewer, e2e-runner | Smoke test passes, CLI contract verified |
| Release | development-process | sprint-complete, retro, doc-updater | Checklist complete, retro filed |
| Operate | oss-health-policy, allowed-licenses | vault-audit, oss-health-check | Drift detected and resolved |

## Software Development Lifecycle

Within the Build phase, each feature follows a strict development workflow. The ECC rules file `development-workflow.md` defines four sequential steps, each backed by a specific agent.

```mermaid
graph TD
    R["<b>0. Research and Reuse</b><br/><i>Search GitHub, registries,<br/>prior art before writing code</i>"]:::step
    P["<b>1. Plan</b><br/><i>planner agent creates<br/>implementation plan</i>"]:::step
    T["<b>2. TDD</b><br/><i>tdd-guide agent enforces<br/>RED → GREEN → REFACTOR</i>"]:::step
    CR["<b>3. Code Review</b><br/><i>code-reviewer agent runs<br/>immediately after writing</i>"]:::step
    G["<b>4. Commit</b><br/><i>Conventional commits,<br/>push to branch</i>"]:::step

    R --> P --> T --> CR --> G

    R -.- R_agent["oss-health-check<br/>license audit"]:::agent
    P -.- P_agent["planner<br/>architect"]:::agent
    T -.- T_agent["tdd-guide<br/>build-error-resolver"]:::agent
    CR -.- CR_agent["code-reviewer<br/>security-reviewer<br/>python-reviewer"]:::agent
    G -.- G_agent["doc-updater"]:::agent

    classDef step fill:#1B2A4A,color:#F0F0F0,stroke:#D4A017,stroke-width:2px
    classDef agent fill:#0A0A14,color:#E8B830,stroke:#B87308,stroke-width:1px,stroke-dasharray:5 5
```

The agents are not called by a central orchestrator. They are triggered naturally by the ECC rules loaded into the AI agent's context. When the rules file says "use **tdd-guide** agent" for new features, the AI agent invokes it because that instruction is part of its active system prompt. The developer does not need to remember which agent to call — the rules make it automatic.

## Sprint Lifecycle

A sprint is the unit of delivery. The sprint-plan skill orchestrates the documentation updates at both ends of a sprint — opening and closing — while the sprint-complete and retro skills handle the quality gates at close.

```mermaid
graph TD
    subgraph open ["Sprint Open"]
        O1["<b>Validate</b><br/><i>Prerequisites complete,<br/>tests green, tree clean</i>"]:::step
        O2["<b>Update Artifacts</b><br/><i>Story frontmatter,<br/>status, SDR, bootstrap</i>"]:::step
        O1 --> O2
    end

    subgraph build ["Sprint Execution"]
        B1["<b>Implement Stories</b><br/><i>TDD cycle per story,<br/>code review after each</i>"]:::step
        B2["<b>Integration Verify</b><br/><i>Smoke test, CLI contract,<br/>workflow-level AC</i>"]:::step
        B1 --> B2
    end

    subgraph close ["Sprint Close"]
        C1["<b>Completion Checklist</b><br/><i>Tests, docs, CHANGELOG,<br/>manifest, metrics</i>"]:::step
        C2["<b>Retrospective</b><br/><i>Root cause analysis,<br/>linked deliverables</i>"]:::step
        C3["<b>Update Artifacts</b><br/><i>Status, bootstrap,<br/>session log, vault audit</i>"]:::step
        C1 --> C2 --> C3
    end

    open --> build --> close
    close -->|"next sprint"| open

    O1 -.- sprint_plan["sprint-plan skill"]:::skill
    O2 -.- sprint_plan
    C1 -.- sprint_complete["sprint-complete skill"]:::skill
    C2 -.- retro_skill["retro skill"]:::skill
    C3 -.- vault_audit["vault-audit skill"]:::skill

    classDef step fill:#1B2A4A,color:#F0F0F0,stroke:#D4A017,stroke-width:2px
    classDef skill fill:#0A0A14,color:#E8B830,stroke:#B87308,stroke-width:1px,stroke-dasharray:5 5

    style open fill:#0A0A14,stroke:#D4A017,stroke-width:1px,color:#D4A017
    style build fill:#0A0A14,stroke:#B87308,stroke-width:1px,color:#B87308
    style close fill:#0A0A14,stroke:#E67E22,stroke-width:1px,color:#E67E22
```

## How Policy Enforcement Works

The connection between governance policies and agent behavior happens through three layers:

**Layer 1: Policy documents** live in `content/policies/` and are deployed to the vault's `code/` directory during `owb init`. These are the full, detailed governance documents — the product development workflow, sprint mechanics, integration verification standards, OSS health evaluation criteria, and allowed license lists.

**Layer 2: Inline enforcement rules** are extracted from the policy documents into a compact checklist (`vault-policies.md`) that is deployed to the workspace's rules directory. The AI agent loads this file automatically as part of its system context. Each checklist item is an enforceable gate — the agent checks these before proceeding with work.

**Layer 3: A policy compliance preamble** is injected into the generated workspace config file (the agent's entry point). This preamble instructs the agent to follow the enforcement rules and escalate conflicts to the owner rather than proceeding silently.

```mermaid
graph TD
    Policies["<b>Policy Documents</b><br/><i>5 governance documents<br/>in content/policies/</i>"]:::store
    Rules["<b>Inline Enforcement Rules</b><br/><i>vault-policies.md in<br/>workspace rules directory</i>"]:::rules
    Preamble["<b>Policy Compliance Preamble</b><br/><i>Injected into agent<br/>config file</i>"]:::rules
    Agent["<b>AI Agent</b><br/><i>Loads rules and preamble<br/>as system context</i>"]:::agent

    Policies -->|"owb init extracts<br/>enforceable items"| Rules
    Policies -->|"owb init detects<br/>policies exist"| Preamble
    Rules -->|"auto-loaded<br/>into context"| Agent
    Preamble -->|"read at<br/>session start"| Agent

    Agent -->|"consults full docs<br/>when needed"| Policies

    classDef store fill:#0A0A14,color:#B0B0C0,stroke:#B87308,stroke-width:1px,stroke-dasharray:5 5
    classDef rules fill:#1B2A4A,color:#F0F0F0,stroke:#D4A017,stroke-width:2px
    classDef agent fill:#12121E,color:#E8B830,stroke:#D4A017,stroke-width:3px
```

The enforcement rules contain checklist items like:

- "PRD, ADR, SDR, and threat model exist before implementation begins"
- "Acceptance criteria describe end-to-end operator workflows, not isolated module behavior"
- "License check passes before health evaluation (disallowed license = stop)"

When an AI agent begins work on a feature, these rules are already in its context. If the agent is asked to implement a story without a PRD, the enforcement rules instruct it to flag that gap. If a dependency is being added, the rules require a license check and health evaluation before proceeding. The agent does not need a separate compliance workflow — the rules are part of every session.

## Agent Catalog

The ECC ships 16 agents, 15 commands, and 7 skills. Each is designed for a specific phase of the lifecycle.

### Agents (Specialized Sub-Processes)

| Agent | Lifecycle Phase | What It Does |
|-------|----------------|-------------|
| **planner** | Plan | Creates implementation plans, identifies dependencies and risks |
| **architect** | Design | System design, C4 modeling, architectural decisions |
| **tdd-guide** | Build | Enforces RED → GREEN → REFACTOR cycle, 80%+ coverage |
| **code-reviewer** | Build | Reviews code for quality, security, maintainability |
| **python-reviewer** | Build | Python-specific PEP 8, type hints, security review |
| **go-reviewer** | Build | Go-specific idiomatic patterns, concurrency safety |
| **security-reviewer** | Verify | OWASP Top 10, secrets detection, injection prevention |
| **build-error-resolver** | Build | Fixes build errors, type errors, linter warnings |
| **e2e-runner** | Verify | End-to-end testing with browser automation |
| **doc-updater** | Release | Updates documentation, READMEs, codemaps |
| **refactor-cleaner** | Build | Dead code removal, consolidation, cleanup |
| **database-reviewer** | Build | PostgreSQL query optimization, schema review |
| **harness-optimizer** | Build | Agent harness configuration optimization |
| **loop-operator** | Build | Autonomous agent loop monitoring and intervention |
| **chief-of-staff** | Operate | Communication triage across channels |

### Skills (Orchestration Workflows)

| Skill | Lifecycle Phase | What It Does |
|-------|----------------|-------------|
| **sprint-plan** | Plan / Release | Automates sprint open and close artifact updates |
| **sprint-complete** | Release | Walks through the sprint completion checklist |
| **retro** | Release | Scaffolds retrospectives with sequential IDs |
| **write-story** | Plan | Generates story files with workflow-level AC |
| **vault-audit** | Operate | Checks vault integrity (links, indexes, frontmatter) |
| **oss-health-check** | Build | Evaluates dependency health against scoring criteria |
| **mobile-inbox-triage** | Intelligence | Processes mobile research captures |

### Commands (One-Line Triggers)

Commands are shorthand for common operations: `/plan`, `/tdd`, `/code-review`, `/verify`, `/build-fix`, `/test-coverage`, `/e2e`, `/eval`, `/checkpoint`, `/update-docs`, `/refactor-clean`, `/python-review`, `/go-review`, `/go-build`, `/go-test`.

## End-to-End Example

A developer working with OWB and an AI agent experiences the full lifecycle without needing to remember the process:

1. **Research phase:** The developer captures an idea on mobile. The mobile-inbox-triage skill processes it into a tagged research note.

2. **Design phase:** The developer says "let's design this." The agent invokes the architect and planner agents, checks the decisions index for prior art, and produces PRD, ADR, SDR, and threat model using vault templates.

3. **Sprint planning:** The developer says "open Sprint 5 with stories S030 through S035." The sprint-plan skill validates prerequisites, updates story frontmatter, status.md, SDR, and bootstrap in one pass.

4. **Implementation:** The developer says "implement S030." The agent reads the story's acceptance criteria, invokes the tdd-guide to write tests first, implements the code, then automatically triggers the code-reviewer. If a new dependency is needed, the enforcement rules require `owb audit package` before installation and `owb audit licenses` before adoption.

5. **Sprint close:** The developer says "close the sprint." The sprint-complete skill runs the checklist (tests, docs, CHANGELOG, manifest). The retro skill scaffolds a retrospective with the correct sequential ID and carried-forward items. The vault-audit skill checks for broken links from the bulk edits. A session log is written to the project's sessions folder.

6. **Operation:** Between sprints, `owb diff` detects template drift. `owb migrate` applies updates. The vault-audit skill catches stale references. The oss-health-check skill re-evaluates dependencies when their maintenance signals change.

At no point does the developer consult a process document or remember which agent to call. The policies are in the agent's context. The agents trigger based on the work at hand. The skills orchestrate multi-file updates that would otherwise require manual coordination across a dozen vault files.
