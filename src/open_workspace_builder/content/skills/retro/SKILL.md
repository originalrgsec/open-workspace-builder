---
name: retro
description: >-
  Scaffold a new retrospective with correct ID, template, and pre-populated
  context. Use this skill when the user says 'retro', 'retrospective',
  'write a retro', or after completing a sprint.
---

# Retrospective Scaffolding

This skill creates a new retrospective file with the correct sequential ID, pre-populated context from the previous retro, and template compliance.

## When to Run

- After a sprint completion
- After a production incident or feature regression
- After a phase transition (design to implementation, implementation to production)
- When the operator says "retro", "retrospective", "write a retro", or "let's do a retro"

## Workflow

### Step 1: Determine the Next Retro ID

Read the retro-log file (`self/retro-log.md` in the vault) and extract the `next_id` field from its frontmatter. If the retro-log does not exist or has no `next_id`, scan the retro-log headings for the highest `RETRO-NNN` number and increment by one.

The retro ID format is `RETRO-NNN` with zero-padded three-digit numbers (e.g., `RETRO-001`, `RETRO-012`).

### Step 2: Identify the Trigger

Prompt the operator for the retro trigger:

1. Sprint completion — which sprint and project?
2. Incident — what happened?
3. Phase transition — which project and which phases?
4. Other — describe the context

Use the response to fill the frontmatter fields: `project`, `phase`, and `tags`.

### Step 3: Create the Retro File

Create the file using the retrospective template. The file goes in one of two locations based on expected scope:

- **Standalone retros** (multi-issue, root cause analysis, significant length): create at `self/retros/RETRO-NNN-short-description.md`
- **Lightweight retros** (single issue, quick process check): add inline in the retro-log under a new `RETRO-NNN` heading

Ask the operator which format is appropriate if unclear. Default to standalone for sprint completion and incident retros.

Fill the template frontmatter:

```yaml
---
type: retrospective
retro_id: RETRO-NNN
project: <from trigger>
phase: <from trigger>
date: <today>
participants: [owner]
tags: [retro, <trigger-type>]
---
```

Replace the title placeholder: `# RETRO-NNN: <short description from trigger>`

### Step 4: Pre-Populate Open Items from Previous Retro

Read the previous retro (RETRO-(NNN-1)). Extract the "Open Items for Next Retro" section. Insert those items into the new retro's "Scope" section as:

```
### Carried Forward from RETRO-(NNN-1)

- [ ] <open item 1>
- [ ] <open item 2>
```

If there are no open items from the previous retro, note "No open items carried forward from RETRO-(NNN-1)."

### Step 5: Pre-Fill Context Links

Populate the "Links" section at the bottom with the project's index and status file paths based on the project identified in Step 2.

If the trigger is sprint completion, also link to the sprint's session logs and the CHANGELOG entry for the release.

### Step 6: Hand Off for Findings

At this point, the template is ready for the operator to fill in findings. Prompt:

"The retro template is ready. Fill in: What Went Well, What Went Wrong, Root Cause Analysis, and Action Items. I will then help with Linked Deliverables and update the retro-log."

### Step 7: Update the Retro-Log

After the operator has written findings:

1. Add an entry to the retro-log index (`self/retro-log.md`) with:
   - The RETRO-NNN heading
   - A one-line summary
   - Link to the retro file (if standalone)
   - Linked deliverables reference

2. Update the `next_id` field in the retro-log frontmatter to NNN+1.

### Step 8: Validate Linked Deliverables

Check that the "Linked Deliverables" section has at least one entry. Per the development process policy, a retro that identifies problems but links to zero deliverables is incomplete.

If the section is empty, warn the operator: "This retro has no linked deliverables. Every retro must produce at least one concrete deliverable (bug, story, policy change, or process update). What deliverable should be created from these findings?"

## Output

Confirm the retro is complete by listing:
- Retro ID and file location
- Number of carried-forward items addressed
- Number of new action items
- Number of linked deliverables
- Whether the retro-log has been updated
