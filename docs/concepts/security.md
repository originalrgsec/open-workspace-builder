# Security Model

OWB treats workspace content as untrusted input. Agents, commands, rules, and skills are markdown files that act as system prompts for Claude. A compromised prompt file could instruct Claude to exfiltrate data, modify files, or bypass user oversight. The security scanner exists to catch this before it reaches a session.

## Three-Layer Defense-in-Depth

### Layer 1: Structural Analysis

The first layer validates file properties without reading content. It catches binary files, executables, oversized files, zero-width Unicode characters, right-to-left overrides, and homoglyph attacks. These are indicators of obfuscation or smuggled payloads that have no legitimate reason to appear in workspace configuration files.

### Layer 2: Pattern Matching

The second layer applies regex patterns against file content. The default pattern set (`owb-default`) includes 58 patterns organized across 9 categories: shell injection, credential harvesting, data exfiltration, prompt injection, privilege escalation, persistence mechanisms, evasion techniques, known-malicious signatures, and steganography indicators.

Patterns are loaded from an extensible registry. You can add project-specific pattern files to the registry overlay directory for custom detection rules.

### Layer 3: Semantic Analysis

The third layer sends file content to an LLM for behavioral analysis. This catches threats that cannot be expressed as regex patterns: behavioral manipulation, social engineering, stealth language designed to influence Claude's behavior, obfuscated payloads, and self-modification instructions.

Layer 3 requires a configured model in `models.security_scan` and the `llm` package extra:

```bash
pip install "open-workspace-builder[llm]"
```

Without the extra, Layers 1 and 2 still provide coverage for the most common attack patterns.

## Scanner Integration Points

The security scanner runs automatically at several points in the OWB workflow:

- **During `owb migrate`**: Every file proposed for update is scanned before it is written. Files that fail are blocked.
- **During `owb update`**: Upstream content is scanned before acceptance.
- **On demand via `owb security scan`**: Scan any file or directory at any time.
- **During skill evaluation**: The `owb eval` pipeline includes a security pass before scoring.

## Trust Tiers

OWB supports configurable trust policies that define minimum scanner requirements for different content sources. The `trust` section in config.yaml controls which policy is active. Policies specify which layers must pass for content to be accepted from each tier.

## Pattern Registry

The pattern registry is designed for extension. Each pattern file is a YAML document containing one or more patterns with metadata: name, category, severity, regex, and a human-readable description of what the pattern catches.

To add custom patterns, place YAML files in the registry overlay directory specified in your config. OWB merges them with the default set at scan time. Custom patterns can reference the same severity levels and categories as the built-in set.

## Secrets Scanning

OWB integrates pre-commit secrets detection to prevent credentials from entering version control. The default backend is **gitleaks**, which provides zero-config operation with 800+ built-in patterns and runs fully locally. An opt-in alternative is **ggshield** (GitGuardian), which requires a GitGuardian API key for cloud-based detection.

The secrets scanner hooks into pre-commit to block commits containing detected secrets. On-demand scanning is available via `owb security secrets`.

The active backend is controlled by the `security.secrets_scanner` config key (default: `gitleaks`).

## Trivy Integration

**Trivy** provides multi-ecosystem software composition analysis (SCA), covering npm, Go, Rust, and container images. It supplements pip-audit, which remains the primary scanner for Python dependencies. Together they give OWB coverage across all supported ecosystems.

Trivy is pinned to **v0.69.3**. Versions 0.69.4 through 0.69.6 are blocked due to CVE-2026-33634, a supply-chain compromise affecting those releases. OWB enforces this version constraint automatically and will refuse to run a blocked version.

On-demand scanning is available via `owb security trivy`.

## Package Quarantine

OWB enforces a 7-day quarantine window on new package versions via `uv.toml exclude-newer`. No package published within the last 7 days can enter the lock file. This provides a buffer against supply-chain attacks that rely on rapid adoption of compromised releases.

Safe advancement of pinned dates is handled by `owb audit pins`, which checks whether advancing the window would introduce packages with known issues. Emergency bypass is supported with a mandatory audit trail.

## Pre-Install Gate

Before any new dependency enters the project, a 5-check battery runs automatically:

1. **pip-audit** — known vulnerability check
2. **GuardDog** — malicious package heuristics
3. **OSS health** — maintenance and community health scoring
4. **License** — allowed-license policy enforcement
5. **Quarantine** — 7-day publication window check

The gate is available programmatically via `owb audit gate`. This replaces the earlier prompt-only pre-install rule with an enforceable automated check.

## Reputation Ledger

The security scanner feeds a reputation ledger that tracks source trustworthiness over time. When the scanner returns a malicious verdict, it records a FlagEvent against the source. The SourceUpdater consults the ledger and blocks sources that exceed the configured flag threshold. Pre-install gate failures also feed the ledger, creating a cumulative risk signal that influences future trust decisions.

## Directive Drift Detection

Workspace directive files (CLAUDE.md, agents, rules, commands) are security-sensitive because they act as system prompts for Claude. An unauthorized modification to any of these files could alter agent behavior in ways that bypass user oversight.

`owb security drift` computes SHA-256 hashes of all tracked directive files and compares them against a stored baseline. It reports files that have been modified, added, or deleted since the last known-good state. The baseline is stored per-workspace at `<workspace>/.owb/drift-baseline.json`, so each project maintains an independent record.

Tracked file patterns:

- `CLAUDE.md` and `.claude/CLAUDE.md`
- `.claude/agents/*.md`
- `.claude/rules/**/*.md`
- `.claude/commands/**/*.md`

Run `owb security drift --update-baseline` after any intentional directive change to re-establish the known-good state. Between baselines, any modification triggers a drift alert on the next check.

## SCA and SAST Defaults

As of v1.2.0, SCA (software composition analysis) and SAST (static application security testing) are enabled by default for all workspaces. Previous versions required opt-in via `security.sca_enabled` and `security.sast_enabled`. Existing configs that explicitly set these to `false` will continue to be respected.

## Related concepts

- [Policy as Code](policy-as-code.md) — how security rules are expressed and enforced
- [Supply Chain Security](supply-chain-security.md) — dependency and content provenance protection
- [IDP for AI Coding](idp-for-ai-coding.md) — the platform model these security capabilities support
