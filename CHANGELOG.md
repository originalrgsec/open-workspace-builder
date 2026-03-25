# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-03-25

### Added
- Cross-project policy deployment during vault build (OWB-S064):
  - VaultBuilder deploys content/policies/*.md to Obsidian/code/ during init
  - Migrator automatically detects missing/outdated policies via reference diff
  - Graceful skip when content/policies/ is missing or empty
  - 8 new tests in test_policy_deployment.py
- Pluggable secrets backend with `SecretsBackend` protocol and three implementations (OWB-S050):
  - OS keyring (macOS Keychain, GNOME Keyring, Windows Credential Manager) via `keyring` package
  - Age encryption with pyrage/CLI fallback and automatic key generation
  - Environment variable fallback (backward compatible, zero config)
- `owb auth` CLI command group: `store-key`, `get-key`, `status`, `backends`
- Runtime API key resolution with four-step fallback: CLI flag → secrets backend → env var → error
- `SecretsConfig` section in config overlay (`secrets.backend`, `secrets.age_identity`, etc.)
- Wizard secrets backend selection step with availability checking and graceful fallbacks
- Wizard API key storage now routes through the configured secrets backend
- `keyring`, `age`, and `secrets` optional dependency groups in pyproject.toml
- 88 new tests (625 → 713)
- Dependency supply chain scanning with two-layer architecture (OWB-S053):
  - Layer A: pip-audit Python API wrapper for known vulnerability scanning against OSV database
  - Layer B: GuardDog subprocess wrapper (`uvx guarddog`) for heuristic malware detection
- `owb audit deps` CLI command with `--deep`, `--fix`, `--format json|text`, `--output FILE` options
- `owb audit package <name>` CLI command for pre-addition single-package vetting with `--version` option
- Bundled suppressions YAML for acknowledged GuardDog false positives
- Makefile with `check-deps`, `audit-deps`, `audit-deps-deep` targets
- GitHub Actions CI workflow: pip-audit on every push, GuardDog on pyproject.toml changes
- `audit` optional dependency group in pyproject.toml
- 42 new tests (713 → 755)

- Context file lifecycle management:
  - `ContextDeployer` detects existing files and skips instead of overwriting
  - `owb context migrate` command for interactive reformatting against current templates
  - `owb context status` command reports filled/stub/missing state per file
  - Workspace config template includes "First Session Tasks" for assistant-guided fill
  - Wizard informational notice about context file stubs
- 16 new tests for context lifecycle (755 → 771)
- Pre-install SCA gate ECC rule (`dependency-security.md`) — instructs Claude Code to run `owb audit package` before any pip/uv install (OWB-S055)
- Semgrep SAST integration (OWB-S056):
  - `security/sast.py` module wrapping Semgrep CLI with JSON output parsing
  - `owb security sast` CLI command with `--config`, `--sarif`, `--format` options
  - `sast` optional dependency group in pyproject.toml
  - GitHub Actions SAST CI job, Makefile `sast` and `sast-json` targets
  - `sast-scanning.md` ECC rule for evaluated component scanning
- SCA and SAST wired into evaluator and security scan (OWB-S057):
  - `--sca` and `--sast` flags on `owb security scan` for combined reporting
  - Dependency discovery from requirements.txt, pyproject.toml, and import statements
  - `SecurityConfig.sca_enabled` and `sast_enabled` fields for config-driven activation
  - Trust tier scoring: critical SCA findings or SAST errors block T0, force manual review
- Automated CVE suppression monitoring (OWB-S059):
  - Suppression registry (`security/data/suppressions.yaml`) with CVE-2026-4539 entry
  - `owb audit check-suppressions` CLI command querying OSV API for fix availability
  - Weekly CI job (`suppression-monitor.yml`) opens GitHub issues when fixes land
  - `suppressions_schema.py` dataclass and YAML loader with validation
- 57 new tests for S055-S059 (771 → 828)

### Changed
- `VaultConfig.parent_dir` default changed from `"Context"` to `""` — vault deploys directly under workspace root instead of an intermediate folder
- pyyaml promoted from optional to core dependency — evaluator and security modules import it unconditionally

### Fixed
- CI: pip-audit `--skip-editable` for local package, `--ignore-vuln CVE-2026-4539` for pygments ReDoS (no upstream fix)
- CI: removed 3 unused imports caught by ruff lint on Python 3.13 matrix
- Stale `Claude Context/` path references in workspace config template and SKILL.md

## [0.3.0] - 2026-03-24

### Added
- Full skill evaluation pipeline: classify, generate tests, execute, score, judge, decide (S022-S024)
- Three evaluation modes: new skill (UC-1), update existing (UC-2), overlapping capability (UC-3) (S024)
- Evaluator scorer with per-dimension and weighted composite scoring via ModelBackend judge operation (S022)
- Quality judge with pairwise comparison and prompt injection hardening via system/user separation and XML delimiters (S023)
- Evaluation manager orchestrator chaining classify → generate → execute → score → judge → decide (S024)
- Test suite generator and persistence layer extracted from CWB, adapted to OWB's LiteLLM ModelBackend (S024)
- Skill type classifier with 10 skill types and configurable weight vectors (S028)
- Organizational layer classifier (L0-L3) with few-shot examples from YAML and confidence-gated manual review (S028)
- Trust tier assignment from registry-loaded policies with data-driven tier transitions (T0/T1/T2) (S029)
- Multi-source content discovery with per-source glob patterns, exclude rules, and SourcesConfig (S035)
- Repo-level security audit with pass/warn/block verdicts for hooks dirs, setup scripts, event triggers (S036)
- `owb update <source>` command replacing hardcoded ECC update path with config-driven multi-source pipeline (S037)
- SourcesConfig in config.py for named upstream sources with repo URL, pin, and discovery rules (S035)
- 251 new tests (374 → 625)

### Changed
- `owb ecc update` preserved as backward-compatible alias for `owb update ecc` (S037)

## [0.2.0] - 2026-03-23

### Added
- Config-driven architecture with three-layer overlay system (defaults, user file, CLI flags) (S040)
- LiteLLM-backed ModelBackend for model-agnostic provider routing — works with Anthropic, OpenAI, Ollama, and any LiteLLM-supported provider (S041)
- Extensible registry system for security patterns, trust policies, and marketplace formats with metadata envelopes and overlay support (S042)
- Interactive setup wizard (`owb init`) with 7-step configuration: model provider, API keys, vault tiers, marketplace format, security patterns, trust policies (S043)
- Vault config generation from existing vaults (`owb init --from-vault <path>`) (S043)
- `--no-wizard` flag to skip interactive setup and use defaults (S043)
- VaultConfig.assistant_name for configurable generated content (S044)
- AgentConfigConfig with configurable directory and filename (defaults: `.ai/WORKSPACE.md`) (S044)
- EccConfig.enabled flag (default: false) and configurable target_dir (S044)
- PathsConfig with runtime resolution from CLI name
- CLI name-aware config resolution (`owb` uses `~/.owb/`, `cwb` uses `~/.cwb/`)
- ModelsConfig with per-operation model strings for classify, generate, judge, security_scan
- SecurityConfig, TrustConfig, MarketplaceConfig as first-class config sections
- 42 security patterns split into 9 registry files with metadata envelopes
- Trust tier policy file (T0/T1/T2) in registry format
- Marketplace format configs (generic, anthropic, openai) in registry format
- `config.example.yaml` documenting full schema
- 121 new tests (253 to 374)

### Changed
- VaultConfig.parent_dir default changed from "Claude Context" to "Context" (S044)
- ECC installation disabled by default (enable via config) (S044)
- Agent config deploys to `.ai/WORKSPACE.md` by default (configurable) (S044)
- Security scanner accepts SecurityConfig and Registry for pattern loading
- Semantic analysis uses ModelBackend instead of direct anthropic SDK (S041)
- Scanner accepts ModelBackend instead of api_key/model parameters (S041)
- All Claude-specific references in generated content replaced with configurable assistant_name (S044)

### Removed
- Direct `anthropic` SDK dependency (replaced by LiteLLM)
- Hardcoded Claude-specific paths and content in engine modules

## [0.1.0] - 2026-03-23

### Added
- CLI entry point (`owb`) with Click-based commands: init, diff, migrate, ecc update/status, security scan
- Config module with defaults-first strategy and optional YAML overlay
- Build engine: vault generator, ECC installer, skills installer, context deployer
- Three-layer security scanner: structural validation, pattern matching, semantic analysis
- Reputation ledger with threshold-based drop recommendations
- Workspace diff engine and interactive migration
- ECC upstream update workflow with fetch, diff, scan, accept/reject
- 253 tests

[Unreleased]: https://github.com/VolcanixLLC/open-workspace-builder/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/VolcanixLLC/open-workspace-builder/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/VolcanixLLC/open-workspace-builder/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/VolcanixLLC/open-workspace-builder/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/VolcanixLLC/open-workspace-builder/releases/tag/v0.1.0
