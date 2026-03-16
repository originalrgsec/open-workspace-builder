# CLAUDE.md

<!-- This file tells Claude Code and Cowork how to behave in this workspace. -->
<!-- Fill in the sections below and customize to your needs. -->

(One-sentence description of who you are and what this workspace is for.)

## Required Context Files

At the start of any non-trivial session, read the following files to load working context:

1. **working-style.md** — Behavioral instructions, output calibration, tool preferences
2. **brand-voice.md** — Writing voice, register tiers, vocabulary, anti-patterns
3. **about-me.md** — Professional background, domain expertise, project details

## Obsidian Knowledge Vault

An Obsidian vault at `Claude Context/Obsidian/` serves as persistent project memory.

**Session startup:** Read `Claude Context/Obsidian/_bootstrap.md` first. It contains a
compact manifest of all projects with current phases and next actions.

**Project work:** After bootstrap, read the specific project's `_index.md` and `status.md`.
At session end, update `status.md` and write a session log to `sessions/`.

**Research lookup:** Processed research notes have a `projects:` frontmatter field for
targeted retrieval.

**Decision checks:** Read `Claude Context/Obsidian/decisions/_index.md` before recommending
technology or architecture choices.

The vault structure:

- `_bootstrap.md` — session entry point
- `self/` — identity context
- `research/` — inbox → processed pipeline
- `projects/` — one subfolder per project with status, decisions, specs, session logs
- `decisions/` — cross-project decision index
- `code/` — cross-project code patterns
- `business/` — strategy, finance, compliance
- `_templates/` — note templates

If the Obsidian MCP server is available, use it. Otherwise, read/write vault files
directly from the filesystem.
