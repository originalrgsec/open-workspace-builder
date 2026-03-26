# Security Model

OWB treats workspace content as untrusted input. Agents, commands, rules, and skills are markdown files that act as system prompts for Claude. A compromised prompt file could instruct Claude to exfiltrate data, modify files, or bypass user oversight. The security scanner exists to catch this before it reaches a session.

## Three-Layer Defense-in-Depth

### Layer 1: Structural Analysis

The first layer validates file properties without reading content. It catches binary files, executables, oversized files, zero-width Unicode characters, right-to-left overrides, and homoglyph attacks. These are indicators of obfuscation or smuggled payloads that have no legitimate reason to appear in workspace configuration files.

### Layer 2: Pattern Matching

The second layer applies regex patterns against file content. The default pattern set (`owb-default`) includes 42 patterns organized across 9 categories: shell injection, credential harvesting, data exfiltration, prompt injection, privilege escalation, persistence mechanisms, evasion techniques, known-malicious signatures, and steganography indicators.

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
