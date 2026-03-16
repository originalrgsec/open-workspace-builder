# claude-workspace-builder

A Python script that bootstraps a fully structured Claude Code / Cowork workspace from scratch. It creates an Obsidian knowledge vault with 18 project templates, installs a curated subset of the [Everything Claude Code](https://github.com/anthropics/courses) (ECC) catalog, deploys custom Cowork skills with associated scripts, and generates template context files and a `.claude/CLAUDE.md` entry point.

The goal is repeatable, version-controlled workspace setup. Run the script in a fresh Claude session or on any machine with Python 3.10+ to get a consistent working environment.

## What Gets Built

```
output/
├── .claude/
│   ├── CLAUDE.md                    # Workspace entry point (template)
│   ├── agents/                      # ECC curated agents (16)
│   ├── commands/                    # ECC curated slash commands (15)
│   └── rules/
│       ├── common/                  # Cross-language rules (8)
│       ├── golang/                  # Go-specific rules (4)
│       └── python/                  # Python-specific rules (4)
├── .skills/
│   └── skills/
│       ├── mobile-inbox-triage/     # Mobile note capture → vault routing
│       ├── vault-audit/             # Vault integrity checks (bash + semantic)
│       └── oss-health-check/        # OSS dependency health scoring (Python)
├── Claude Context/
│   ├── about-me.md                  # Template — fill in your background
│   ├── brand-voice.md               # Template — fill in your writing style
│   ├── working-style.md             # Template — fill in your preferences
│   └── Obsidian/
│       ├── _bootstrap.md            # Session entry point (template)
│       ├── _index.md                # Vault area map
│       ├── _templates/              # 18 note templates
│       │   ├── adr.md               # Architecture Decision Record (C4, DFDs)
│       │   ├── budget-draw-schedule.md
│       │   ├── decision-record.md
│       │   ├── financing-tracker.md
│       │   ├── mobile-inbox.md
│       │   ├── post-mortem.md
│       │   ├── prd.md               # Product Requirements Document
│       │   ├── project-index.md
│       │   ├── readme.md
│       │   ├── research-note.md
│       │   ├── roadmap.md           # Phased delivery (POC → MVP → Prod)
│       │   ├── sdr.md               # Software Design Record
│       │   ├── selections-tracker.md
│       │   ├── session-log.md
│       │   ├── spec.md
│       │   ├── story.md             # TDD stories (Given/When/Then)
│       │   ├── threat-model.md      # STRIDE + NIST SP 800-30 scoring
│       │   └── vendor-contact-list.md
│       ├── self/
│       ├── research/
│       │   ├── inbox/
│       │   ├── processed/
│       │   ├── archive/
│       │   └── mobile-inbox/
│       ├── projects/
│       │   ├── Personal/
│       │   ├── Volcanix/
│       │   ├── Incubator/
│       │   └── Claude/
│       ├── decisions/
│       ├── code/
│       └── business/
```

## Quick Start

```bash
# Clone the repo
git clone https://github.com/volcanix-llc/claude-workspace-builder.git
cd claude-workspace-builder

# Build with defaults (writes to ./output/)
python build.py

# Build to a specific location
python build.py --target ~/my-workspace

# Preview without writing anything
python build.py --dry-run

# Use a custom config
python build.py --config config.yaml
```

No dependencies required for default operation. PyYAML is optional and only needed if you use a custom `config.yaml`.

## Configuration

The script uses a built-in default configuration. To customize, create a `config.yaml`:

```yaml
target: output

vault:
  name: Obsidian
  parent_dir: "Claude Context"
  create_bootstrap: true
  create_templates: true

ecc:
  source_dir: ecc-curated
  agents:
    - architect
    - code-reviewer
    - security-reviewer
    # ... add or remove as needed
  commands:
    - plan
    - code-review
    - verify
    # ... add or remove as needed
  rules:
    common:
      - coding-style
      - security
      - testing
    python:
      - coding-style
      - patterns

skills:
  source_dir: skills
  install:
    - mobile-inbox-triage
    - vault-audit
    - oss-health-check

context_templates:
  deploy: true

claude_md:
  deploy: true
```

Any key you omit falls back to the built-in default. You only need to specify what you want to change.

## Design Document Chain

The vault templates implement a structured design pipeline for projects that moves from business requirements through architecture to code:

**PRD → ADR → Threat Model → SDR → Stories**

1. **PRD** (Product Requirements Document) defines what to build: personas, use cases, goals, and success criteria.
2. **ADR** (Architecture Decision Record) defines how to build it: C4 model (context, containers, components), data flow diagrams with trust boundaries, tech stack, and key architectural decisions. Each decision includes an OSS health check and license verification gate.
3. **Threat Model** applies STRIDE analysis per element from the ADR's DFDs. Risk is scored using NIST SP 800-30 likelihood/impact matrices. Mitigations map to NIST SP 800-53 Rev. 5 control families for compliance traceability (SOC 2, FedRAMP).
4. **SDR** (Software Design Record) is C4 Level 4: module design, data schemas, API contracts, configuration, and testing strategy. It breaks work into stories grouped by sprint.
5. **Stories** have Given/When/Then acceptance criteria that Claude Code uses for TDD: write the test first, then the implementation.

The chain is opinionated. Each document links forward and backward so Claude can traverse from requirements to code and back. If a project does not warrant the full chain, the lightweight `spec.md` template is available.

## Custom Skills

Three custom Cowork skills are included:

**mobile-inbox-triage** processes notes captured on mobile (via iOS Shortcut from Claude mobile conversations) and routes them into the correct vault location based on content analysis and frontmatter tags.

**vault-audit** runs a two-layer integrity check: a bash script handles mechanical checks (broken wiki links, index-to-disk consistency, frontmatter validation, stale references, required structural files), and a semantic pass catches higher-order problems (bootstrap phase alignment, decision index completeness, research tag accuracy, status currency).

**oss-health-check** evaluates open source project health against configurable thresholds by querying GitHub API and package registries (npm, PyPI, crates.io). It produces a Green/Yellow/Red rating across six categories: maintenance activity, bus factor, community adoption, funding, documentation, and security posture.

## ECC Catalog (Curated)

The `ecc-curated/` directory contains a vetted subset of the Everything Claude Code catalog. These are agents, slash commands, and rules files that get installed into `.claude/` during the build. The full ECC catalog contains many more items; this repo includes only the ones selected for this workspace.

## Privacy

This repo contains no private data. The context files (`about-me.md`, `brand-voice.md`, `working-style.md`) are templates with placeholder content. The Obsidian vault is an empty skeleton with structural files and templates only. The `_bootstrap.md` is a template with example format but no real project data.

To use the workspace, fill in the template files with your own information. These files should be added to `.gitignore` after population if the repo remains version-controlled.

## Requirements

- Python 3.10+
- No third-party packages (PyYAML is optional for custom config)
- Works on macOS, Linux, and Windows

## License

MIT
