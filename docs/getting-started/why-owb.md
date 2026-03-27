# Why Open Workspace Builder

## The Problem with Starting Cold

Every agentic coding session begins with zero context. You re-explain project structure, decision rationale, coding standards, and personal preferences. This happens session after session. There is no standard way to organize the knowledge, rules, and configurations that make AI-assisted coding productive. Users who build custom workflows discover one component (a Bash wrapper, an Obsidian vault, some custom agents) but miss the others. When you finally assemble something useful, drift creeps in — old decisions stay in the vault while processes change, context files go stale, agent definitions bitrot. Manual workspace assembly is not maintainable.

## What OWB Solves

Open Workspace Builder scaffolds a complete, production-grade AI workspace from a single command. It generates:

- **Knowledge vault**: Obsidian structure with project tracking, decision index, research organization, session logs, and bootstrap manifests that load in seconds.
- **Personal context**: System-level instructions, brand voice, working style, and professional background that calibrate how your coding agent responds to you.
- **Development rules**: Coding standards, security policies, testing requirements, git workflow, performance optimization, and integration verification—checked into the codebase and enforced.
- **Custom skills**: Domain-specific agents and prompts for your workflow (architecture planning, code review, TDD, build troubleshooting).
- **Drift detection**: Automatic scanning for stale decisions, orphaned projects, missing documentation, and policy violations.
- **Interactive migration**: Tools to upgrade your workspace when OWB improves without losing your customizations.
- **Three-layer security scanner**: Static analysis for hardcoded secrets, supply chain risk assessment, and access control verification before every commit.

Once generated, OWB provides upstream content sync so new agent templates and policy documents flow to your workspace without requiring manual edits.

## Who Should Use OWB

**People new to agentic coding.** You have heard that AI coding agents are powerful but every session feels like starting over. You do not have a system for persisting context, tracking decisions, or organizing project knowledge across sessions. OWB gives you a complete, opinionated structure on day one so you can focus on learning the workflow instead of building the scaffolding.

**Solo developers without a mature system yet.** You use an AI coding agent regularly and you have accumulated some ad hoc patterns — a CLAUDE.md here, a few custom prompts there — but nothing cohesive. Sessions still require re-explaining. OWB replaces the patchwork with an integrated workspace that handles context, security scanning, drift detection, and migration out of the box.

## Who Should Not Use OWB

**Teams with established workflows.** OWB is designed for individual developers, not collaborative teams. If your organization already has shared tooling, workspace standards, and onboarding processes, OWB will conflict with rather than complement that infrastructure.

**Experienced developers with a mature personal system.** If you have already built a workspace that persists context reliably, manages drift, and integrates security scanning the way you want it, adopting OWB wholesale will not add enough value to justify the migration. You may find individual ideas worth borrowing, but the tool is not aimed at you.

## Why Not Just Write a CLAUDE.md?

A CLAUDE.md is a single instructions file. OWB is the complete system that generates that file, plus the vault structure, policy documents, security scanning, skill definitions, migration tools, and drift detection that keep your workspace coherent over months and years of active development. CLAUDE.md is a component of OWB, not a substitute for it.
