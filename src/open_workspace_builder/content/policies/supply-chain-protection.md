# Supply Chain Attack Protection - Fully FOSS Edition

Copy and paste this into a Claude Code conversation to configure your development environment against supply chain attacks. If you are not using Claude Code, skip Section 8 -- all other sections apply regardless of which tools or AI assistants you use.

All tools referenced in this document are free and open source. No paid services required.

---

## The Prompt

```
Configure my development environment to protect against software supply chain attacks. The single most effective defense is a package quarantine period: refuse to install any package version published less than 7 days ago. This eliminates the window between a malicious release and community detection for most attack vectors (compromised maintainer accounts, typosquatting, dependency confusion, malicious version bumps).

All tools below are free and open source. No paid services.

Set up the following:

### 1. npm (Node.js)

> **Note:** npm has no free, native release-age enforcement. The quarantine concept for npm relies on Trivy catching known vulns quickly and Renovate ensuring all updates are reviewed before merge. A brand-new malicious package with no CVE yet is not caught by Trivy -- this is a known gap.

Mitigate with:

- **Pin exact versions** via `package-lock.json`. Always use `npm ci` in CI (never `npm install`), which installs exactly what the lockfile specifies.
- **Run `trivy fs .`** as a required CI check on every PR. Trivy (Apache 2.0) scans lockfiles for known CVEs across npm, pip, Go, Rust, and more in a single binary.
- **Run `npm audit`** as an additional CI check. Built into npm, free, catches advisories from the npm registry.
- **Commit and diff lockfiles** on every PR. Fail CI if `package-lock.json` changes without a corresponding dependency update PR.
- **Renovate** (self-hosted, AGPL-3.0, free) for automated, reviewable dependency update PRs (never auto-merge). This is the highest-value free control after lockfiles. Renovate can be configured to delay updates by N days (`minimumReleaseAge: "7 days"` in `renovate.json`), which enforces the quarantine on automated PRs.
- **Manual check before adding new dependencies:** Run `npm show <package> time` to inspect the publish date. If the latest version is less than 7 days old, wait or pin an older version. This is a manual habit, not enforcement.
- **osv-scanner** (Apache 2.0, Google) as an alternative or complement to Trivy. Queries the OSV database for known vulns across all ecosystems.

### 2. uv / pip (Python)

**Global** (~/.config/uv/uv.toml):
```toml
exclude-newer = "7 days"
```

This tells uv to ignore package versions published in the last 7 days during dependency resolution. This is real, native release-age enforcement.

For pip without uv, there is no equivalent built-in setting. Use `pip-audit` (Apache 2.0, Google) and pin dependencies with hashes in requirements.txt.

### 3. Cargo (Rust)

There is no built-in release age filter in Cargo. Mitigate with:
- `cargo-audit` (MIT/Apache 2.0) in CI for known vulnerability detection
- `cargo-vet` (MIT/Apache 2.0, Mozilla) for supply chain review of new dependencies
- `trivy fs .` in CI as an additional layer (scans Cargo.lock)
- Pin dependencies with `=` version constraints and review lockfile diffs

### 4. Go modules

Go has no release age filter. Mitigate with:
- Go's checksum database (sumdb) provides tamper detection but not age filtering
- `govulncheck` (BSD-3, Go team) in CI
- `trivy fs .` in CI as an additional layer (scans go.sum)
- Review go.sum diffs on dependency updates

### 5. Homebrew

No release age filter. Mitigate by:
- Using `brew pin` for critical packages
- Reviewing `brew update` output before `brew upgrade`

### 6. CI/CD Pipeline

Add these checks to every CI pipeline:
- **`trivy fs . --severity CRITICAL,HIGH --exit-code 1`** as a required check on every PR. Trivy covers npm, pip, Cargo, Go, and more in a single scan. Apache 2.0 license. GitHub Action: `aquasecurity/trivy-action` with `scan-type: fs`.
- **`npm audit --audit-level=high`** as an additional npm-specific check (built-in, free).
- **`pip-audit`** for Python projects without uv (or as a complement to Trivy).
- **Lockfile integrity:** fail if lockfile changed without a corresponding dependency update PR.
- **Renovate** (self-hosted, free) for automated, reviewable dependency update PRs. Configure `minimumReleaseAge: "7 days"` to enforce quarantine on automated updates. Never auto-merge.
- **osv-scanner** (optional, Apache 2.0) as a second opinion alongside Trivy.

### 7. CLAUDE.md / Project Instructions

Add this to every project's CLAUDE.md or equivalent:
```
- Supply chain quarantine: enforce release age controls where tooling supports it (uv exclude-newer for Python, Renovate minimumReleaseAge for all ecosystems). Run trivy fs and npm audit in CI. Pin exact versions via lockfiles. Use npm ci in CI. Never auto-merge dependency updates.
```

### What this protects against

| Attack Vector | Why the 7-Day Window Matters |
|--------------|---------------------------|
| Compromised maintainer account | Malicious release detected and yanked within hours/days. You never install it. |
| Typosquatting (e.g., `loadsh` vs `lodash`) | Fake packages get reported quickly. 7 days is usually enough for npm to remove them. |
| Dependency confusion | Internal package names claimed on public registries. Detected and reported quickly by affected orgs. |
| Malicious version bump | Maintainer publishes a backdoored release. Community spots it in reviews/diffing within days. |
| Account takeover via expired domain | Attacker claims a maintainer's expired email domain, resets password, publishes malicious update. Same detection window applies. |

### What this does NOT protect against

- Long-lived backdoors that have been in a package for months/years (rare but devastating)
- Zero-day vulnerabilities in legitimate packages (not malicious, just buggy)
- Build-time attacks (compromised CI runners, build scripts)
- First-party code vulnerabilities

For those, you need: SCA scanning (Trivy), SAST, lockfile pinning, code review, and minimal dependency philosophy.

### Emergency bypass

If you genuinely need a package released in the last 7 days (e.g., a critical security patch for an active zero-day):
- For uv: use `--exclude-newer` with today's date to override the global setting
- For Trivy-flagged packages: add a `.trivyignore` entry with a comment explaining the justification. Review and remove ignore entries monthly.
- For Renovate: temporarily override `minimumReleaseAge` for a specific package in `renovate.json` with a comment and revert after the update merges.
- Document the bypass in the commit message with justification
- This should be rare (once or twice a year at most)

### FOSS Tool Reference

| Tool | License | What it does | Install |
|------|---------|-------------|---------|
| Trivy | Apache 2.0 | Multi-ecosystem SCA scanner (npm, pip, Go, Rust, etc.) | `brew install trivy` or GitHub Action `aquasecurity/trivy-action` |
| Renovate | AGPL-3.0 | Automated dependency update PRs with release-age enforcement | Self-hosted via Docker or GitHub App (free for public repos) |
| osv-scanner | Apache 2.0 | Multi-ecosystem vuln scanner using Google's OSV database | `go install github.com/google/osv-scanner/cmd/osv-scanner@latest` |
| pip-audit | Apache 2.0 | Python dependency audit against PyPI advisory DB | `pip install pip-audit` |
| cargo-audit | MIT/Apache 2.0 | Rust dependency audit against RustSec advisory DB | `cargo install cargo-audit` |
| cargo-vet | MIT/Apache 2.0 | Rust supply chain review (Mozilla) | `cargo install cargo-vet` |
| govulncheck | BSD-3 | Go vulnerability scanner (official Go team tool) | `go install golang.org/x/vuln/cmd/govulncheck@latest` |
| npm audit | MIT (npm) | npm built-in advisory check | Built into npm (no install needed) |
| uv | MIT/Apache 2.0 | Python package manager with native release-age filtering | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |

### 8. Persistence Layer (Claude Code / AI Assistants)

> **Claude Code users only.** This section applies exclusively to Claude Code's project rules system. Standard Claude.ai chat, the API, and Claude in Chrome have no persistent rules files or CLAUDE.md. If you are not using Claude Code, skip this section.

This makes the rule persistent within Claude Code projects. Outside of Claude Code, there is no cross-session memory -- enforce quarantine at the tooling level instead (lockfiles, Trivy, Renovate, CI checks) rather than relying on AI assistant configuration.

Add to your global Claude configuration (CLAUDE.md or equivalent):

```
## Supply Chain Security (GLOBAL - ALL PROJECTS)

Never install any package version published less than 7 days ago. This applies to every project, every package manager, every conversation. Enforce via uv exclude-newer for Python, Renovate minimumReleaseAge for automated PRs, trivy fs in CI for all ecosystems, and lockfile pinning. Never bypass without explicit user approval.
```

If you use Claude Code rules files, add a `dependency-security.md` rule to your common rules directory that enforces:
- 7-day quarantine where tooling supports it (uv exclude-newer, Renovate minimumReleaseAge)
- Pre-install audit for every new dependency (trivy fs, npm audit)
- Lockfile integrity checks
- No silent bypass of release age constraints

The goal is that no future Claude Code conversation can install a package younger than 7 days without you explicitly approving a bypass.

Please configure all of this now. Set up the global config files (uv.toml), add Trivy to CI pipelines, configure Renovate with minimumReleaseAge, and update any CLAUDE.md, rules files, or project instructions you find.
```

---

## Why This Matters

Most supply chain attacks are detected within 24-72 hours. A 7-day quarantine period means you are virtually never the first person to install a compromised package. The community, automated scanners, and npm's own security team will catch it before your `npm install` ever sees it.

This is the highest ROI security control you can add to a development environment. Zero cost (all FOSS tools). Zero workflow impact for 99.9% of installs. Eliminates the most common attack vector in modern software development.

## Persistence is Critical

**For Claude Code users:** Without persistent rules, every new conversation starts clean. Claude Code's CLAUDE.md and rules files ensure the quarantine is enforced even when you forget to mention it. This is the AI-layer defense.

**For everyone else:** The real defense is tooling-level enforcement. CI checks (Trivy), lockfile diffing, Renovate with `minimumReleaseAge`, and `uv exclude-newer` work regardless of which AI assistant (or none) you use. Do not rely on AI configuration alone -- the tooling must independently enforce the quarantine.
