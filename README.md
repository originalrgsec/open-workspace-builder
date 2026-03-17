# cwb — Claude Workspace Builder

Scaffold, maintain, and secure [Claude Code](https://docs.anthropic.com/en/docs/claude-code) and [Cowork](https://docs.anthropic.com/en/docs/cowork) workspaces from a single command.

[![PyPI version](https://img.shields.io/pypi/v/claude-workspace-builder)](https://pypi.org/project/claude-workspace-builder/)
[![Python 3.10+](https://img.shields.io/pypi/pyversions/claude-workspace-builder)](https://pypi.org/project/claude-workspace-builder/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![CI](https://github.com/VolcanixLLC/claude-workspace-builder/actions/workflows/release.yml/badge.svg)](https://github.com/VolcanixLLC/claude-workspace-builder/actions/workflows/release.yml)

## What It Does

`cwb` generates a ready-to-use workspace that includes an Obsidian knowledge vault, a curated set of agents/commands/rules from the [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) (ECC) catalog, custom Cowork skills, and context file templates. It also provides drift detection, migration, upstream sync, and a three-layer security scanner — so you can keep your workspace up to date and safe over time.

## Quick Start

```bash
pip install claude-workspace-builder

# Scaffold a workspace with sensible defaults
cwb init

# Scaffold to a specific directory
cwb init --target ~/my-workspace

# Preview what would be created without writing anything
cwb init --dry-run
```

This creates an `output/` directory (or your chosen target) containing:

```
output/
├── .claude/
│   ├── CLAUDE.md               # Workspace entry point
│   ├── agents/                 # 16 curated ECC agents
│   ├── commands/               # 15 curated ECC slash commands
│   └── rules/                  # Language-specific rules (common, Go, Python)
├── .skills/
│   └── skills/                 # 3 custom Cowork skills
├── Claude Context/
│   ├── about-me.md             # Template — your background
│   ├── brand-voice.md          # Template — your writing style
│   ├── working-style.md        # Template — your preferences
│   └── Obsidian/               # Knowledge vault with 18 note templates
│       ├── _bootstrap.md
│       ├── _index.md
│       ├── _templates/
│       ├── self/, research/, projects/, decisions/, code/, business/
│       └── ...
```

## Features

### `cwb init` — Scaffold a Workspace

Creates the full directory structure in one step. Supply `--config` to customize which agents, commands, rules, and skills are installed. Defaults work out of the box with no config file needed.

### `cwb diff` — Detect Drift

Compares an existing workspace against the reference state and reports what is missing, outdated, or modified. Useful in CI to catch manual edits that drifted from the managed baseline.

```bash
cwb diff ./output              # prints human-readable report
cwb diff ./output -o report.json  # also writes JSON for automation
```

### `cwb migrate` — Update a Workspace

Brings an existing workspace up to date. Reviews each changed file interactively (or use `--accept-all` for batch mode). Files that fail security scanning are blocked from migration.

```bash
cwb migrate ./output           # interactive review of each change
cwb migrate ./output --accept-all  # batch mode, skip prompts
cwb migrate ./output --dry-run     # preview without writing
```

### `cwb ecc update` — Sync Upstream ECC Content

Fetches the latest Everything Claude Code catalog, diffs against your vendored copy, runs the security scanner on changed files, and lets you accept or reject each update individually.

```bash
cwb ecc update                 # interactive review
cwb ecc update --accept-all    # auto-accept clean files
cwb ecc status                 # show pinned commit, flag history
```

### `cwb security scan` — Three-Layer Content Scanner

Scans files for security issues using a defense-in-depth approach:

```bash
cwb security scan ./path       # scan file or directory
cwb security scan ./path --layers 1,2   # structural + pattern only
cwb security scan ./path -o report.json  # write JSON report
```

### `cwb package-skills` — Package for Cowork

Package custom skills for distribution. *(Coming soon.)*

## Security Model

`cwb` includes a three-layer security scanner designed to catch malicious content in workspace configuration files — particularly important when pulling content from external sources like ECC.

| Layer | Method | What It Catches |
|-------|--------|-----------------|
| **1 — Structural** | File type, size, and encoding analysis | Binary files, executables, oversized files, encoding anomalies (zero-width characters, RTL overrides, homoglyphs) |
| **2 — Pattern** | Regex pattern matching (42 patterns across 9 categories) | Shell injection, credential harvesting, data exfiltration, prompt injection, known-malicious signatures |
| **3 — Semantic** | Claude API analysis (sandboxed) | Behavioral manipulation, social engineering, stealth language, obfuscated payloads, self-modification instructions |

The scanner runs automatically during `cwb migrate` and `cwb ecc update`. Files flagged as malicious are blocked from being applied. A reputation ledger tracks flag events per source; if a source exceeds the malicious flag threshold, cwb recommends dropping that upstream entirely.

Layer 3 (semantic analysis) requires the `security` extra and an `ANTHROPIC_API_KEY`:

```bash
pip install claude-workspace-builder[security]
export ANTHROPIC_API_KEY=sk-...
```

Without the extra, layers 1 and 2 still run and provide coverage for the most common attack patterns.

## Configuration

`cwb` works without any configuration file — sensible defaults are built in. To customize, create a `config.yaml` and pass it with `--config`:

```bash
cwb init --config config.yaml
```

See [`config.example.yaml`](config.example.yaml) for the full configuration surface with comments explaining each option.

Key things you can configure:

- **Target directory** — where the workspace is created
- **Vault settings** — name, parent directory, whether to create bootstrap/templates
- **ECC selection** — which agents, commands, and rules to install
- **Skills** — which custom skills to include
- **Context templates** — whether to deploy the personal context files
- **CLAUDE.md** — whether to deploy the workspace entry point

Any key you omit falls back to the built-in default. You only need to specify what you want to change.

## ECC Content

The workspace includes a curated subset of the [Everything Claude Code](https://github.com/affaan-m/everything-claude-code) catalog (MIT licensed). This content is **vendored and pinned** — it ships with the package at a known-good commit rather than fetching at install time.

To update to the latest upstream:

```bash
cwb ecc update          # interactive review with security scanning
cwb ecc status          # check current pinned commit
```

Every file from upstream is scanned before it can be applied. The vendored copy only changes when you explicitly accept an update.

## Custom Skills

Three Cowork skills are included:

- **mobile-inbox-triage** — Processes notes captured on mobile and routes them into the correct vault location based on content analysis and frontmatter tags.
- **vault-audit** — Runs structural and semantic integrity checks on the Obsidian vault (broken links, index consistency, frontmatter validation, stale references).
- **oss-health-check** — Evaluates open-source project health against configurable thresholds using GitHub API and package registry data.

### Adding Your Own Skills

Place skill directories under `skills/` in the source tree. Each skill needs:

```
skills/
└── my-skill/
    ├── cowork.skill.yaml    # Skill metadata
    └── ...                  # Implementation files
```

Add the skill name to `config.yaml` under `skills.install` and run `cwb init`.

## Requirements

- Python 3.10+
- Core: `click` (installed automatically)
- Optional: `pyyaml` for custom config files (`pip install claude-workspace-builder[yaml]`)
- Optional: `anthropic` for Layer 3 semantic scanning (`pip install claude-workspace-builder[security]`)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, branch naming conventions, testing requirements, and the PR process.

## License

[MIT](LICENSE) — Copyright (c) 2026 Volcanix LLC
