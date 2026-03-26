# Credits

OWB builds on the work of several open source projects. This page acknowledges what we use, how we use it, and where our own work begins.

## Core Dependencies

| Project | How OWB Uses It | License |
|---------|----------------|---------|
| [Click](https://click.palletsprojects.com/) | CLI framework — all `owb` subcommands are Click commands | BSD-3-Clause |
| [PyYAML](https://pyyaml.org/) | Config file parsing — the three-layer overlay reads YAML | MIT |
| [LiteLLM](https://github.com/BerriAI/litellm) | Model routing — Layer 3 semantic scanning and evaluator call any LLM provider through a unified interface | MIT |

## Security Tooling

| Project | How OWB Uses It | License |
|---------|----------------|---------|
| [pip-audit](https://github.com/pypa/pip-audit) | Known vulnerability scanning — `owb audit deps` wraps the pip-audit Python API to check installed packages against the OSV database | Apache-2.0 |
| [GuardDog](https://github.com/DataDog/guarddog) | Malicious package detection — `owb audit deps --deep` shells out to `uvx guarddog` for heuristic analysis of package contents. Not imported as a library; invoked as an isolated subprocess | Apache-2.0 |
| [pip-licenses](https://github.com/raimon49/pip-licenses) | License discovery — `owb audit licenses` shells out to `pip-licenses --format=json` to enumerate installed package licenses. OWB does its own classification against the allowed-licenses policy; pip-licenses provides the raw data | MIT |
| [Semgrep](https://semgrep.dev/) | Static analysis — `owb security scan --sast` invokes Semgrep as a subprocess for code pattern scanning. Used for evaluated component vetting, not imported as a library | LGPL-2.1 (subprocess) |

## Secrets Backends

| Project | How OWB Uses It | License |
|---------|----------------|---------|
| [keyring](https://github.com/jaraco/keyring) | OS credential storage — the keyring secrets backend wraps macOS Keychain, GNOME Keyring, and Windows Credential Manager through keyring's unified API | MIT |
| [pyrage](https://github.com/woodruffw/pyrage) | Age encryption — the age secrets backend uses pyrage for file encryption with automatic key generation. Falls back to the `age` CLI if pyrage is unavailable | MIT |

## Content Sources

OWB's `owb update` infrastructure supports multiple upstream content sources, each pinned, security-scanned, and tracked independently. The current catalog:

| Source | How OWB Uses It | License |
|--------|----------------|---------|
| [Everything Claude Code](https://github.com/anthropics/claude-code) | ECC upstream — OWB vendors a curated subset of agents, commands, and rules. Content is pinned at a specific commit, security-scanned before acceptance, and tracked in a reputation ledger. OWB does not import or execute any ECC code; the files are markdown instructions interpreted by AI agents | MIT |

OWB curates a subset of the ECC catalog rather than shipping it wholesale. The curated set includes 16 agents, 15 commands, and rules across 3 language categories (common, Python, Go). Content that does not pass OWB's three-layer security scanner is not vendored.

Additional content sources can be registered in `config.yaml` under the `sources` section. Each source specifies a repo URL, pin (commit or tag), discovery patterns, and exclude rules. The same security scanning and reputation tracking that applies to ECC applies to every registered source.

## Documentation Site

| Project | How OWB Uses It | License |
|---------|----------------|---------|
| [MkDocs](https://www.mkdocs.org/) | Static site generator — builds this documentation site from markdown | BSD-2-Clause |
| [Material for MkDocs](https://squidfunk.github.io/mkdocs-material/) | Theme — provides the navigation, search, dark mode, and code highlighting used throughout this site | MIT |
| [mkdocs-glightbox](https://github.com/blueswen/mkdocs-glightbox) | Image lightbox — click-to-zoom for images in the documentation | MIT |
| [Mermaid](https://mermaid.js.org/) | Diagram rendering — all architecture, lifecycle, and data flow diagrams are written in Mermaid and rendered client-side | MIT |

## What OWB Built From Scratch

The following components are original to OWB and do not wrap or adapt an existing project:

- **Three-layer security scanner** (structural, pattern, semantic) — no existing tool scans AI workspace content for prompt injection
- **Workspace builder engine** (vault scaffolding, ECC installation, context deployment, drift detection, migration) — purpose-built for the OWB workspace model
- **Evaluator pipeline** (classifier, scorer, judge, manager) — skill quality evaluation with prompt injection hardening
- **Policy enforcement system** (policy parsing, inline rule extraction, conditional preamble injection) — connects governance documents to agent behavior
- **Source update infrastructure** (multi-source fetching, repo auditing, content hashing, reputation ledger) — supply chain management for AI workspace content
- **License audit engine** (policy file parser, license matcher, classification) — runtime policy parsing rather than hardcoded license lists
- **All orchestration skills** (sprint-plan, sprint-complete, retro, write-story, vault-audit, mobile-inbox-triage, oss-health-check) — workflow automation for the vault-based development process
