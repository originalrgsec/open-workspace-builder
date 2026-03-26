# Why Open Workspace Builder

## The Problem with Starting Cold

Every Claude Code session begins with zero context. You re-explain project structure, decision rationale, coding standards, and personal preferences. This happens session after session. There is no standard way to organize the knowledge, rules, and configurations that make AI coding productive. Users who build custom workflows discover one component (a Bash wrapper, an Obsidian vault, some ECC agents) but miss the others. When you finally assemble something useful, drift creeps in—old decisions stay in the vault while processes change, context files go stale, agent definitions bitrot. Manual workspace assembly is not maintainable.

## What OWB Solves

Open Workspace Builder scaffolds a complete, production-grade AI workspace from a single command. It generates:

- **Knowledge vault**: Obsidian structure with project tracking, decision index, research organization, session logs, and bootstrap manifests that load in seconds.
- **Personal context**: System-level instructions (CLAUDE.md), brand voice, working style, and professional background that calibrate how Claude responds to you.
- **Development rules**: Coding standards, security policies, testing requirements, git workflow, performance optimization, and integration verification—checked into the codebase and enforced.
- **Custom skills**: Domain-specific agents and prompts for your workflow (architecture planning, code review, TDD, build troubleshooting).
- **Drift detection**: Automatic scanning for stale decisions, orphaned projects, missing documentation, and policy violations.
- **Interactive migration**: Tools to upgrade your workspace when OWB improves without losing your customizations.
- **Three-layer security scanner**: Static analysis for hardcoded secrets, supply chain risk assessment, and access control verification before every commit.

Once generated, OWB provides upstream content sync so new agent templates and policy documents flow to your workspace without requiring manual edits.

## Who Should Use OWB

**Solo developers and technical professionals** using Claude Code or Cowork daily. You need session continuity, not a blank slate every time.

**People managing multiple active projects**. You need a single place to track decisions, dependencies, and assumptions across codebases so the next session picks up where you left off.

**Team leads standardizing workspace config**. You can generate a baseline workspace for your team, commit it to version control, and keep agents and policies in sync across developers.

**Anyone who has built a workspace by hand**. You have patterns that work. OWB gives you the structure to keep them maintainable and the tooling to stop fighting drift.

## Why Not Just Write a CLAUDE.md?

A CLAUDE.md is a single instructions file. OWB is the complete system that generates that file, plus the vault structure, policy documents, security scanning, skill definitions, migration tools, and drift detection that keep your workspace coherent over months and years of active development. CLAUDE.md is a component of OWB, not a substitute for it.
