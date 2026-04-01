---
name: vault-audit
description: >
  Run a full integrity audit of the Obsidian knowledge vault. Use this skill whenever the user
  asks to check, audit, validate, or verify vault health, after any major vault restructuring,
  when adding or removing projects, after bulk research processing, or when the user mentions
  broken links, stale references, or vault consistency. Also trigger when the user says things
  like "is the vault clean", "check the vault", "run the audit", "anything broken", or
  "validate the structure". This skill combines a mechanical bash script for link/structure
  checks with semantic analysis that catches issues a script cannot.
---

# Vault Audit

This skill runs a two-layer audit of the Obsidian knowledge vault: a mechanical check via bash script, followed by a semantic analysis pass that catches higher-order consistency problems.

## When to Run

- After any structural change to the vault (new projects, moved files, renamed folders)
- After bulk research processing (inbox to processed pipeline)
- After updating _bootstrap.md, decisions/_index.md, or tier-level _index files
- On request ("audit the vault", "check for broken links", "is everything consistent")

## Step 1: Locate the Vault

The vault lives at `Claude Context/Obsidian/` inside the user's workspace folder. Confirm the path exists before proceeding. The typical full path in Cowork is `/sessions/*/mnt/Claude Cowork/Claude Context/Obsidian/`.

## Step 2: Run the Mechanical Audit Script

Run the bundled bash script:

```bash
bash <skill-path>/scripts/audit.sh "<vault-path>"
```

The script checks six categories:

1. **Wiki link resolution** — Every `[[...]]` link in every `.md` file (excluding templates) resolves to a real file. Story forward-references in SDR files are flagged as warnings, not issues, because those files are created at implementation time.
2. **Index-to-disk consistency** — Every project folder on disk appears in its tier's `_index.md`, and every project linked in an index has a corresponding folder.
3. **Bootstrap manifest consistency** — Every project in `_bootstrap.md` appears in `projects/_index.md` (with normalized name matching to handle display-name vs folder-name differences).
4. **Stale inbox references** — Wiki links (`[[research/inbox/...]]`) in project files that should have been updated to `research/processed/` or `research/archive/`. Prose mentions of the inbox in workflow docs and session logs are excluded.
5. **Frontmatter validation** — All `status.md` files have a `last-updated` or `updated` field. All processed research notes have a `projects:` field.
6. **Required structural files** — Critical vault files exist (`_bootstrap.md`, `_index.md`, all area indexes). Every project folder has both `_index.md` and `status.md`.

The script exits with code 0 (pass) or 1 (issues found). Warnings do not cause failure.

Capture and present the full output to the user.

## Step 3: Run the Semantic Audit

The bash script catches mechanical problems. This step catches things a script cannot. Read the relevant files and check:

### 3a: Bootstrap Phase Alignment

Read `_bootstrap.md` and compare each project's listed phase against the actual `status.md` for that project. Flag any mismatches. The bootstrap is the session entry point, so stale phase data there means every future session starts with wrong information.

### 3b: Decisions Index Completeness

Read `decisions/_index.md`. Then read every file matching `*/adr.md` or `*/decisions/DRN-*.md` under `projects/`. Verify that every accepted decision in a project's ADR/DRN appears in the cross-project decisions index. Flag any missing entries.

Also check the reverse: every entry in `decisions/_index.md` should still have a valid source document on disk.

### 3c: Research Tag Accuracy

For each project that has research notes linked in its `_index.md`, verify that the referenced processed research notes actually have that project listed in their `projects:` frontmatter field. This catches cases where a research note is linked from a project but not tagged back to it.

### 3d: Status File Currency

Check the `last-updated` date on every `status.md`. Any status file older than 30 days where the project phase is not "archived", "reference", or "passive" should be flagged as potentially stale. Use today's date from the system for comparison.

### 3e: Cross-Project Boundary Conflicts

Read `decisions/_index.md` for any pending decisions that mention boundary definitions or overlap between projects (these are common when infrastructure projects share scope). Flag these as open items that may need resolution.

## Step 4: Present Results

Combine the mechanical and semantic findings into a single structured report:

```
## Vault Audit Report — YYYY-MM-DD

### Mechanical Checks
<paste script output>

### Semantic Checks
- Bootstrap phase alignment: X issues
- Decisions index completeness: X issues
- Research tag accuracy: X issues
- Status file currency: X warnings
- Cross-project boundaries: X open items

### Issues Requiring Action
<numbered list of real problems with file paths and recommended fixes>

### Warnings (informational)
<numbered list of expected conditions that were flagged>
```

## Step 5: Offer to Fix

For any issues found, offer to fix them directly. Group fixes by category (broken links, missing frontmatter, stale phases, etc.) and confirm with the user before making changes.

After fixes are applied, rerun the mechanical script to confirm the vault is clean.
