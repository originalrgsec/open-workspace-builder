# Supply Chain Security

**Software supply chain assurance (SSCA)** protects the integrity of the tools, dependencies, and content that enter a development environment. OWB applies SSCA to the AI workspace itself — scanning dependencies, quarantining new packages, auditing licenses, and verifying content provenance before anything reaches your sessions.

## What OWB protects

OWB's supply chain protections cover two attack surfaces:

1. **Python dependencies** — packages installed via pip/uv that OWB or downstream tools depend on
2. **Workspace content** — skills, agents, rules, and templates sourced from upstream repositories

Both surfaces are scanned before content enters the workspace. The principle is simple: nothing gets installed or deployed without passing a security gate.

## Supply chain capabilities

### Package quarantine

OWB enforces a 7-day quarantine on newly published packages via `uv.toml` configuration (`exclude-newer`). The `owb audit pins` command checks pinned dependencies against PyPI publication dates and identifies packages that have aged past the quarantine window and are safe to advance.

This protects against supply chain attacks that rely on compromised packages being installed quickly before the community detects the compromise. The March 2026 litellm incident (versions 1.82.7 and 1.82.8 compromised within hours of publication) is the concrete example that drove this feature.

### Pre-install SCA gate

Before any package is installed, `owb audit package <name>` runs:

- **pip-audit** — checks for known vulnerabilities against the OSV database
- **GuardDog** — heuristic malware detection (typosquatting, obfuscated code, suspicious install hooks)
- **License check** — verifies the package license against the allowed-licenses policy
- **OSS health check** — evaluates maintenance cadence, bus factor, security posture, and community health

An inline policy rule in the workspace instructs the AI coding assistant to run this gate before any `pip install` or `uv add` command.

### Secrets scanning

Pre-commit hooks run **gitleaks** (or optionally **ggshield**) on every commit to prevent API keys, tokens, passwords, and other secrets from entering the repository.

### Multi-ecosystem SCA

**Trivy** (pinned to a verified-safe version) provides vulnerability scanning across Python, Node.js, Go, and Rust ecosystems. This catches vulnerabilities in transitive dependencies that pip-audit alone would miss.

### Suppression monitoring

Known false positives are tracked in a suppression registry. The `owb audit check-suppressions` command queries the OSV API to check whether upstream fixes have landed for suppressed CVEs. A weekly CI job opens GitHub issues when fixes become available, ensuring suppressions do not become permanent.

### Content provenance

When OWB pulls content from upstream sources (`owb update`), every file runs through the three-layer security scanner. The reputation ledger tracks source history: how many updates have been clean, how many have been flagged, and what the overall trust posture of each source is. Sources that exceed a flag threshold are recommended for removal.

## What OWB does not protect

OWB's SSCA protects the AI workspace and its development dependencies. It does not protect the artifacts you ship to production. If you are building a web application, OWB scans the tools and libraries you use during development, not the application's runtime dependencies (unless they overlap). Production supply chain assurance requires additional tooling in your CI/CD pipeline.

## Related concepts

- [IDP for AI Coding](idp-for-ai-coding.md) — the platform model that SSCA fits within
- [Policy as Code](policy-as-code.md) — the enforcement mechanism for supply chain policies
- [Security Model](security.md) — the three-layer scanner that content passes through
