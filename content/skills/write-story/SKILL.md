---
name: write-story
description: >-
  Generate a properly structured story file from a description with workflow-level
  acceptance criteria. Use this skill when the user says 'write a story', 'new story',
  'create a story', or when planning sprint work items.
---

# Story Writer

This skill generates a story file from a description, using the correct project prefix, sequential ID, and template structure. Acceptance criteria are written at the workflow level per the integration verification policy.

## When to Run

- Operator says "write a story", "new story", "create a story", or "add a story"
- During sprint planning when defining work items
- When converting a retro action item into a tracked story

## Workflow

### Step 1: Gather Inputs

Collect from the operator:

1. **Story description** — what capability is being added, changed, or fixed
2. **Project name** — which project this story belongs to
3. **Priority** (optional) — high, medium, low (default: medium)
4. **Sprint** (optional) — which sprint this is planned for

If the operator provides a one-liner, extract the description and project from context. If the project is ambiguous, ask.

### Step 2: Determine Project Prefix and Next ID

Each project uses a three-character prefix for story IDs (e.g., `OWB`, `CSK`, `INP`). Determine the prefix by:

1. Reading existing story files in the project's stories directory
2. Checking the development process policy or project SDR for the prefix convention
3. If no convention exists, ask the operator for the prefix

Find the highest existing story number for that prefix by scanning filenames matching `{PREFIX}-S{NNN}*`. The new story gets the next sequential number.

Format: `{PREFIX}-S{NNN}` with zero-padded three-digit numbers (e.g., `OWB-S042`).

### Step 3: Generate the Story File

Create the file using the story template. File name: `{PREFIX}-S{NNN}-short-description.md` (lowercase, hyphenated).

Fill the frontmatter:

```yaml
---
type: story
id: {PREFIX}-S{NNN}
status: backlog
project: <project name>
sprint: <sprint if provided>
priority: <priority>
estimate:
created: <today>
updated: <today>
tags: []
---
```

### Step 4: Write the User Story

Convert the operator's description into the standard format:

```
As a [persona], I want [capability] so that [business value].
```

If the operator provided a technical description without a persona, use "project operator" as the default persona and derive the business value from the capability.

### Step 5: Fill Context Links

Populate the Context section with links to relevant SDR modules and PRD use cases based on the project name. If the SDR and PRD exist in the repo, reference the specific sections that relate to this story.

### Step 6: Write Workflow-Level Acceptance Criteria

This is the most critical step. Per the integration verification policy, acceptance criteria must describe end-to-end operator workflows, not isolated module behaviors.

**Correct pattern:** The "When" clause uses CLI commands or operator actions. The "Then" clause verifies observable outcomes at system boundaries.

```
### AC-1: [descriptive name]
- **Given:** the project is configured with valid credentials and a data source
- **When:** the operator runs `myapp process --source api`
- **Then:** items appear in the database with populated enrichment fields and output files are generated in the configured directory
```

**Incorrect pattern (do not use):** Module-level assertions like "ApiAdapter.collect() returns a list" or "EnrichmentService.enrich() populates all fields." These test implementation details, not operator workflows.

For each acceptance criterion:
- The "When" must be an operator-visible action (CLI command, API call, UI interaction)
- The "Then" must be a verifiable outcome (data in storage, files on disk, API response)
- Include the full command with representative arguments

Generate at least two AC items from the story description.

### Step 7: Write Edge Cases and Error Cases

Generate edge cases and error cases that exercise boundary conditions:

**Edge cases** — unusual but valid inputs: empty data sets, maximum batch sizes, special characters in identifiers, concurrent operations.

**Error cases** — invalid states that must produce clear errors: missing configuration, invalid credentials, unreachable services, malformed input. Per the integration verification policy, configuration errors must fail loudly, not degrade silently.

Generate at least one edge case and one error case.

### Step 8: Fill Test File Mapping

Leave the Test File Mapping table with placeholder rows matching each AC, edge case, and error case. The implementing agent fills in actual test file paths during implementation.

### Step 9: Present and Confirm

Show the complete story to the operator for review. Highlight:
- The assigned ID
- The acceptance criteria (since these drive the entire implementation)
- Any assumptions made about the project or workflow

Ask the operator to confirm or request changes before writing the file to disk.

## Validation Rules

Before finalizing, verify:

1. All AC "When" clauses reference operator-visible actions, not internal function calls
2. All AC "Then" clauses reference observable outcomes, not internal state
3. At least one edge case and one error case exist
4. Context links reference real project doc paths if the docs exist
5. The story ID is sequential and does not duplicate an existing ID
