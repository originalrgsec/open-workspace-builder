---
name: mobile-inbox-triage
description: >
  Process and triage notes captured on mobile into the Obsidian knowledge vault.
  Use this skill whenever the user says anything like "check the mobile inbox",
  "process mobile notes", "triage inbox", "what came in from mobile", "sync my
  mobile notes", or any reference to the research/mobile-inbox folder. Also trigger at
  the start of any session where the user has been away from their desk, or when
  the user says "I captured some ideas on mobile" or "I sent some notes from my
  phone." If research/mobile-inbox/ contains unprocessed notes, this skill handles
  routing them to the correct vault locations.
---

# Mobile Inbox Triage

This skill processes notes that arrived in the Obsidian vault's `research/mobile-inbox/` folder via mobile capture (iOS Shortcut from Claude mobile conversations, voice memos, or manual Obsidian mobile entry). Each note gets read, analyzed, and routed to the appropriate vault location, then archived.

## When This Runs

The user triggers this explicitly ("process my mobile inbox", "triage inbox", etc.) or it can be invoked as part of a session startup routine. The skill is designed to handle anywhere from 1 to 20 notes in a batch.

## Vault Location

The Obsidian vault (named "Vault") lives at `Obsidian/` relative to the workspace root. The mobile inbox is at `Obsidian/research/mobile-inbox/`. Processed notes get moved to `Obsidian/research/mobile-inbox/archive/`.

## Processing Steps

### 1. Scan the inbox

List all `.md` files in `research/mobile-inbox/` excluding `_index.md` and anything already in `archive/`. If no files are found, tell the user the inbox is empty and stop.

### 2. Read and classify each note

For each note, read the full content and determine its type based on the content and any frontmatter hints:

| Classification | Route To | Description |
|---|---|---|
| **Project update** | `projects/<tier>/<project>/status.md` | Append to the relevant project's status file as a dated entry |
| **New idea or concept** | `projects/<tier>/<project>/` or `research/inbox/` | Create a new note in the appropriate project folder, or research inbox if no project match |
| **Decision** | `decisions/` | Create a decision record using the `_templates/decision-record.md` template |
| **Research finding** | `research/inbox/` | Create a research note using the `_templates/research-note.md` template |
| **Action item only** | Report to user | Surface as a task to be created (in Asana if connected, otherwise just reported) |
| **Session continuation** | `sessions/` | If the note is a continuation of desktop work, create a session log entry |
| **Ambiguous** | Ask the user | Present the note content and ask where it should go |

The `projects:` frontmatter field is the primary routing key. If it contains a project name, route there first. If empty or missing, infer from content. If you cannot confidently classify, ask the user rather than guessing wrong.

### 3. Route the content

When routing, follow these rules:

- Preserve the original voice and content. Do not rewrite or summarize unless the note is clearly raw dictation that needs light cleanup (remove filler words, fix obvious transcription errors, but keep the substance intact).
- Use existing vault templates when creating new notes. Read the relevant template from `_templates/` before creating.
- When appending to an existing file (like a project status.md), add a dated section header: `### YYYY-MM-DD — Mobile capture` followed by the content.
- When creating new notes, use frontmatter consistent with the vault's conventions. Check a sibling note in the target folder if unsure about the expected frontmatter fields.
- Wiki-link to related notes where connections are obvious.

### 4. Archive processed notes

After successfully routing a note:
1. Update its frontmatter to set `processed: true`
2. Add a `routed_to:` field recording where the content went
3. Move the file to `research/mobile-inbox/archive/`

### 5. Report results

After processing all notes, give the user a brief summary: how many notes were processed, where each one was routed, and whether any need manual attention. Keep the summary tight — one line per note is sufficient.

## Edge Cases

- **Duplicate content:** If a mobile note contains content that already exists in the vault (the user captured the same idea twice), flag it and skip rather than creating duplicates.
- **Multiple topics in one note:** If a single note clearly covers two unrelated topics, split it into separate notes before routing. This is common with stream-of-consciousness mobile capture.
- **Empty notes:** Notes with only frontmatter and no real content should be deleted, not archived.
- **Notes referencing projects that don't exist yet:** Ask the user whether to create a new project folder or file the note under research.

## Obsidian MCP

If the Obsidian MCP server is available and responsive, use it for note operations (create-note, edit-note, move-note, read-note, search-vault). If it times out or is unavailable, fall back to direct filesystem operations — the vault is accessible at the filesystem path noted above.
