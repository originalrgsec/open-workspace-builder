---
type: policy
scope: all-projects
created: 2026-03-16
updated: 2026-03-25
tags: [policy, testing, quality]
---

# Integration Verification Policy

## Problem Statement

AI-assisted development implements stories as isolated modules with strong unit test coverage. Each module works correctly in isolation. But the modules are frequently not wired into the end-to-end workflow that an operator actually uses. This produces a codebase where every unit test passes but the application does not function.

This pattern has been observed repeatedly across projects. Common failure modes include: CLI commands never registered, commands calling constructors without required arguments, pipeline stages skipped, adapter fields not mapped, and placeholder values left in production code. Every individual module had passing tests.

## Policy

### 1. Acceptance Criteria Must Be Workflow-Level

Every story's acceptance criteria must describe an end-to-end operator workflow, not an isolated module behavior.

Correct: "Operator runs `myapp process --source api` and items appear in the database with populated enrichment fields and corresponding output files."

Incorrect: "ApiAdapter.collect() returns a list of Item objects." (This tests the adapter module. It does not verify that the CLI command exists, that the adapter is instantiated with correct arguments, that enrichment runs, or that items reach storage.)

### 2. Sprint Acceptance Gate Must Include Pipeline Smoke Test

Before marking any sprint complete, the implementer must run the application's primary command(s) and verify that data flows through the complete chain. For CLI applications, this means running the command and checking output at every stage (storage, sync, generated files). An automated integration test that exercises the full chain with a mock data source is acceptable as a substitute for manual verification, but the test must exist and pass.

### 3. Configuration Errors Must Fail Loudly

Graceful degradation is correct for transient errors (network timeouts, service temporarily unavailable). It is incorrect for configuration errors (missing constructor arguments, invalid credentials, wrong API endpoints, missing directories). If a command silently returns "0 items" or "no results" when the real problem is a misconfiguration, that is a bug. The application must distinguish between "nothing to process" and "unable to process" and surface actionable error messages for the latter.

### 4. CLI Contract Verification Test Is Mandatory

Any project with a CLI interface must have a test file that asserts every documented command exists and responds to `--help`. This test must be created in the first sprint and updated whenever new commands are added. The test catches the most common failure mode: modules implemented but CLI entry points never registered.

### 5. Factory/Builder Patterns Must Be Tested With Real Constructor Signatures

When a factory or builder constructs objects on behalf of CLI commands, the factory's tests must verify that the constructed objects are usable for their intended purpose, not just that construction succeeds. A factory that builds an adapter for health checks but passes placeholder values that break collection is a bug. If an object is constructed for multiple use cases (health check and collection), it must be tested for all of them.

## Applying This Policy

This policy applies to all projects where AI-assisted development handles implementation. It should be referenced in each project's workspace config sprint acceptance gate section. The story template (`_templates/story.md`) enforces workflow-level acceptance criteria by default.

For existing projects, retroactively apply items 2 and 4 (pipeline smoke test and CLI contract test) before the next sprint begins.
