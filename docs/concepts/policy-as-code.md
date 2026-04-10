# Policy as Code

**Policy as code** means expressing security, development, and operational rules as machine-readable definitions that are enforced automatically rather than relying on human memory or documentation. OWB embeds policy-as-code at multiple layers of the workspace lifecycle.

## Where OWB enforces policy

### Inline policy rules

OWB ships a set of inline policy enforcement rules that are deployed to the workspace during `owb init`. These rules are read by the AI coding assistant at session start and enforced during interactive sessions. They cover:

- Dependency pre-install gates (license check, health check, supply chain quarantine)
- Immutability and coding style conventions
- Test-driven development workflow requirements
- Security review checklists before commits

The rules live in the workspace's `.claude/rules/` directory and are version-controlled alongside the project. See the [Configuration](configuration.md) guide for how these are structured.

### Security scanner patterns

The three-layer security scanner uses a pattern registry with 58 known attack signatures across 12 categories. These patterns are policy definitions: each one specifies what to detect, what severity to assign, and what action to take (block, warn, or inform). The registry is extensible — users can add custom patterns for their own policy requirements.

Categories include prompt injection, data exfiltration, shell command execution, stealth techniques, MCP manipulation, and jailbreak attempts.

### Pre-commit hooks

`owb init` deploys a `.pre-commit-config.yaml` with hooks for:

- **gitleaks** — secrets scanning (blocks commits containing API keys, tokens, passwords)
- **ruff** — Python linting and formatting
- **Semgrep** — static analysis against OWASP Top 10 and Python security rulesets
- **Trivy** — multi-ecosystem vulnerability scanning

These hooks enforce policy at the commit boundary. Code that violates the policy does not enter the repository.

### Drift detection as policy enforcement

`owb diff` and `owb security drift` detect when a workspace has diverged from its reference state or when directive files have been modified. Drift detection is a form of configuration compliance: it ensures the workspace continues to match the policy baseline established during setup.

## Concrete example

A developer runs `owb init` on a new project. The wizard deploys:

1. Inline rules requiring license checks before any `pip install`
2. Pre-commit hooks blocking secrets and known vulnerabilities
3. Scanner patterns detecting prompt injection in any `.md` file
4. A package quarantine policy requiring 7-day aging before pin advancement

From that point forward, the developer cannot accidentally install an unapproved dependency, commit a secret, or introduce a prompt injection — the policies are enforced automatically at every relevant boundary.

## Related concepts

- [IDP for AI Coding](idp-for-ai-coding.md) — the platform model that policy-as-code supports
- [Supply Chain Security](supply-chain-security.md) — policies specific to the dependency chain
- [Security Model](security.md) — the three-layer scanner architecture
