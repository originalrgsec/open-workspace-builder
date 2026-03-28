# owb — Open Workspace Builder

Scaffold, maintain, and secure AI coding workspaces from a single command.

[![PyPI](https://img.shields.io/pypi/v/open-workspace-builder)](https://pypi.org/project/open-workspace-builder/)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests: 1253](https://img.shields.io/badge/tests-1253%20passed-brightgreen)](tests/)

## What It Does

`owb` generates a ready-to-use AI workspace that includes an Obsidian knowledge vault, custom skills, context file templates, and a workspace config entry point. It provides drift detection, interactive migration, upstream content sync, and a three-layer security scanner.

OWB also serves as a shared core library. Downstream packages (like vendor-specific wrappers) can depend on OWB for all engine, security, and configuration infrastructure, then overlay their own defaults.

Key capabilities:

- **Interactive setup wizard** on first run, with `--from-vault` for existing Obsidian vaults
- **Model-agnostic LLM backend** via LiteLLM — works with any provider (Anthropic, OpenAI, Ollama, etc.)
- **Extensible registry** for security patterns, trust policies, and marketplace formats
- **Three-layer security scanner** with structural, pattern, and semantic analysis
- **Config overlay system** with three layers: built-in defaults, user config file, CLI flags
- **Name-aware CLI** that resolves config paths from the binary name (`owb` vs `cwb`)
- **Skill evaluation pipeline** with scoring, judging, and three evaluation modes (new, update, overlap)
- **Multi-source content infrastructure** with config-driven discovery, repo audit, and update pipeline
- **Token consumption tracking** with cost analysis, budget alerts, monthly forecasting, and per-story attribution
- **Supply chain scanning** with pip-audit, GuardDog, and Semgrep SAST integration

## Quick Start

```bash
pip install open-workspace-builder

# First run launches an interactive setup wizard
owb init

# Generate config from an existing Obsidian vault
owb init --from-vault ~/path/to/vault

# Skip the wizard and use defaults
owb init --no-wizard

# Scaffold to a specific directory
owb init --target ~/my-workspace

# Preview without writing anything
owb init --dry-run
```

This creates an `output/` directory (or your chosen target) containing:

```
output/
├── .ai/
│   └── WORKSPACE.md              # Workspace config entry point
├── .skills/
│   └── skills/                   # Custom skills
├── Context/
│   ├── about-me.md               # Template — your background
│   ├── brand-voice.md            # Template — your writing style
│   ├── working-style.md          # Template — your preferences
│   └── Obsidian/                 # Knowledge vault with 18 note templates
│       ├── _bootstrap.md
│       ├── _index.md
│       ├── _templates/
│       ├── self/, research/, projects/, decisions/, code/, business/
│       └── ...
```

ECC (Everything Claude Code) agent/command/rule installation is disabled by default. Enable it by setting `ecc.enabled: true` in your config file.

**Already have a vault?** See the [First Run Guide](docs/howto-first-run.md) for a step-by-step walkthrough of running OWB against an existing Obsidian vault, including how to safely test on a copy before touching the live vault.

## Configuration

OWB uses a three-layer configuration system:

1. **Built-in defaults** — sensible values that work out of the box
2. **User config file** — `~/.owb/config.yaml` (auto-detected) or any file via `--config`
3. **CLI flags** — override any config value from the command line

Any key you omit falls back to the layer below. See [`config.example.yaml`](config.example.yaml) for the full schema with comments.

Key sections:

| Section | Controls |
|---------|----------|
| `vault` | Obsidian vault name, parent directory, assistant name, templates |
| `ecc` | ECC catalog enabled/disabled, target directory, agent/command/rule lists |
| `skills` | Which custom skills to install |
| `agent_config` | Workspace config file directory and filename |
| `models` | Per-operation LLM model strings (LiteLLM provider/model format) |
| `security` | Active pattern sets, scanner layer selection |
| `trust` | Trust tier policy selection |
| `marketplace` | Output format (generic, anthropic, openai) |
| `paths` | Config, data, and credentials directory paths |
| `context_templates` | Whether to deploy personal context files |

The setup wizard (`owb init` on first run) generates `~/.owb/config.yaml` interactively. Subsequent runs load it automatically.

## Commands

### `owb init` — Scaffold a Workspace

Creates the full directory structure. On first run, launches an interactive wizard to configure your model provider, vault structure, and security settings. Use `--config` to provide a pre-written config, `--from-vault` to generate config from an existing Obsidian vault, or `--no-wizard` to skip the wizard and use defaults.

### `owb diff` — Detect Drift

Compares an existing workspace against the reference state and reports what is missing, outdated, or modified.

```bash
owb diff ./output                 # prints human-readable report
owb diff ./output -o report.json  # also writes JSON for automation
```

### `owb migrate` — Update a Workspace

Brings an existing workspace up to date. Reviews each changed file interactively (or use `--accept-all` for batch mode). Files that fail security scanning are blocked.

```bash
owb migrate ./output              # interactive review
owb migrate ./output --accept-all # batch mode
owb migrate ./output --dry-run    # preview without writing
```

### `owb ecc update` — Sync Upstream ECC Content

Fetches the latest Everything Claude Code catalog, diffs against your vendored copy, runs the security scanner, and lets you accept or reject each update.

```bash
owb ecc update                    # interactive review
owb ecc update --accept-all       # auto-accept clean files
owb ecc status                    # show pinned commit, flag history
```

### `owb security scan` — Three-Layer Content Scanner

```bash
owb security scan ./path          # scan file or directory
owb security scan ./path --layers 1,2   # structural + pattern only
owb security scan ./path -o report.json # write JSON report
```

### `owb update` — Multi-Source Content Update

Updates content from named upstream sources. Replaces the single-source `owb ecc update` path with a config-driven pipeline supporting arbitrary sources.

```bash
owb update ecc                    # update ECC source
owb update <source>               # update any configured source
owb ecc update                    # backward-compatible alias
```

### `owb eval` — Skill Evaluation

Evaluates skills using a multi-stage pipeline: classify, generate tests, execute against baseline and candidate, score, and decide.

```bash
owb eval ./path/to/skill          # evaluate a new skill
owb eval ./path/to/skill --compare  # compare against existing version
```

### `owb metrics` — Token Tracking and Cost Analysis

```bash
owb metrics tokens                              # consumption report
owb metrics tokens --format json --since 20260301  # filtered JSON
owb metrics export --format gsheets --sheet-id ID  # export to Sheets
owb metrics record --story OWB-S076             # record to local ledger
owb metrics sync --sheet-id ID                  # record + export
owb metrics forecast                            # monthly cost projection
owb metrics budget-check --threshold 200        # budget alert (exit 2 if over)
owb metrics by-story                            # cost per story ID
```

Requires `[sheets]` extra for Google Sheets or `[xlsx]` for Excel export.

## Phase Model

OWB uses a [four-phase maturity model](docs/concepts/phases.md). Phase 1 (interactive sessions) is fully operational. Phase 2 (hybrid model routing with cheaper open-weight models for builds and Claude for oversight) is in design. The existing LiteLLM integration means the codebase is already model-agnostic.

## Security Scanner

The scanner uses a defense-in-depth approach to catch malicious content in workspace files.

| Layer | Method | What It Catches |
|-------|--------|-----------------|
| **1 — Structural** | File type, size, encoding analysis | Binary files, executables, oversized files, zero-width characters, RTL overrides, homoglyphs |
| **2 — Pattern** | Regex matching against registry patterns | Shell injection, credential harvesting, data exfiltration, prompt injection, known-malicious signatures |
| **3 — Semantic** | LLM analysis via configured model | Behavioral manipulation, social engineering, stealth language, obfuscated payloads, self-modification |

Patterns are loaded from the extensible registry. The default set (`owb-default`) includes 58 patterns across 12 categories. Add custom pattern files to the registry overlay directory for project-specific rules.

Layer 3 requires a configured model in `models.security_scan` and the `llm` extra:

```bash
pip install "open-workspace-builder[llm]"
```

Without the extra, layers 1 and 2 still provide coverage for the most common attack patterns.

## Using as a Library

OWB is designed to be used as a dependency by downstream packages. A vendor-specific wrapper can:

1. Depend on `open-workspace-builder>=0.1.0`
2. Provide a pre-baked config YAML with vendor-specific defaults
3. Register its own CLI entry point that sets `cli_name` in the Click context
4. Use OWB's evaluator, sources, and security infrastructure directly, or add vendor-specific modules on top

OWB's config system resolves paths based on the CLI name, so `cwb` loads from `~/.cwb/config.yaml` while `owb` loads from `~/.owb/config.yaml`. The `claude_md` YAML key is accepted as a backward-compatible alias for `agent_config`.

## Development

```bash
git clone https://github.com/originalrgsec/open-workspace-builder.git
cd open-workspace-builder
uv sync --all-extras

# Run tests (1253 tests)
uv run pytest tests/

# Lint
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
```

## License

[MIT](LICENSE)
