# Dependency Security Gate

## Pre-Install Audit (MANDATORY)

Before executing ANY command that introduces a new dependency, run the appropriate
supply-chain security scan first. This applies across all ecosystems.

### Python (uv / pip)

```bash
owb audit package <package-name>
```

This applies to:
- `uv add <package>`
- `pip install <package>`
- `uv pip install <package>`
- Adding a line to `pyproject.toml` dependencies and running `uv sync`

**Quarantine enforcement:** uv supports native release-age filtering via `uv.toml`:

```toml
exclude-newer = "7 days"
```

This tells uv to ignore package versions published in the last 7 days during dependency
resolution. For pip without uv, there is no equivalent built-in setting — use `pip-audit`
and pin dependencies with hashes in requirements.txt.

**Scanning tools:**
- `pip-audit` (Apache 2.0) — audits against the PyPI advisory database for known CVEs
- GuardDog — detects malware indicators in Python packages
- `owb audit gate` — pre-install check combining CVE and malware scans

### npm (Node.js)

npm has no free, native release-age enforcement. Mitigate with:

- **Always use `npm ci`** in CI (never `npm install`). `npm ci` installs exactly what the
  lockfile specifies, preventing silent dependency drift.
- **Run `npm audit --audit-level=high`** as a required CI check on every PR.
- **Diff `package-lock.json`** before committing. Fail CI if the lockfile changed without
  a corresponding dependency update PR.
- **Renovate** (self-hosted, AGPL-3.0, free) for automated dependency update PRs with
  `minimumReleaseAge: "7 days"` to enforce quarantine on automated PRs. Never auto-merge.
- **Manual check:** Run `npm show <package> time` to inspect the publish date before
  adding a new dependency. If the latest version is less than 7 days old, wait or pin an
  older version.

### Rust (Cargo)

There is no built-in release-age filter in Cargo. Mitigate with:

- **`cargo-audit`** (MIT/Apache 2.0) — audits against the RustSec advisory database for
  known vulnerabilities. Run in CI on every PR.
- **`cargo-vet`** (MIT/Apache 2.0, Mozilla) — supply chain review of new dependencies.
- Pin dependencies with `=` version constraints and review `Cargo.lock` diffs.

### Go (modules)

Go has no release-age filter. Mitigate with:

- **`govulncheck`** (BSD-3, Go team) — vulnerability scanner that checks Go modules
  against the Go vulnerability database. Run in CI on every PR.
- Go's checksum database (sumdb) provides tamper detection but not age filtering.
- Review `go.sum` diffs on dependency updates.

## 7-Day Quarantine Window

The single most effective supply-chain defense is refusing to install any package version
published less than 7 days ago. Most supply chain attacks (compromised maintainer accounts,
typosquatting, dependency confusion, malicious version bumps) are detected within 24-72
hours. A 7-day window means you are virtually never the first person to install a
compromised package.

**Enforcement by ecosystem:**

| Ecosystem | Quarantine Mechanism |
|-----------|---------------------|
| Python (uv) | `exclude-newer = "7 days"` in `uv.toml` (native enforcement) |
| npm | Renovate `minimumReleaseAge: "7 days"` + manual publish-date check |
| Rust | Manual review of publish dates; no native enforcement |
| Go | Manual review of publish dates; no native enforcement |

**Emergency bypass:** If you genuinely need a package released in the last 7 days (e.g.,
a critical security patch for an active zero-day), document the bypass in the commit
message with justification. This should be rare — once or twice a year at most.

For the full quarantine policy, ecosystem-specific controls, CI pipeline integration, and
FOSS tool reference, see `supply-chain-protection.md`.

## Pre-Install Decision Flow

**If the audit reports findings:**
- STOP. Do not proceed with the install.
- Present all findings (CVEs, advisory flags, malware indicators) to the user.
- Wait for the user to decide: proceed anyway, pin a different version, or skip.

**If the audit is clean:** Proceed with the install.

**For bulk installs** (`uv sync`, `npm ci`, `pip install -r requirements.txt`):
- Run the appropriate audit tool AFTER the install completes to catch transitive dependencies.
- For Python: `owb audit deps`
- For npm: `npm audit`
- If findings are reported, present them to the user immediately.

## Version Pinning

When adding a new dependency in any ecosystem:
- Pin to the specific version that passed the audit (e.g., `package==1.2.3` for Python,
  exact version in `package.json` for npm, `=1.2.3` for Cargo).
- If the user requests an open range, note the security tradeoff.

## Shared Environment (Python)

All Python projects under this workspace share a single virtual environment at the workspace
root. Do not create per-project `.venv` directories. Use `uv` for all package operations.
