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
  - **The `--exit-code 1` flag is mandatory.** Workflows that ship Trivy as `--exit-code 0` (informational only) silently downgrade the gate. New repos must adopt `--exit-code 1` from day one. Repos with a dirty baseline must file CVE-cleanup follow-ups before adopting the gate, not relax it. (Pre-commit hooks that run Trivy already exit non-zero on findings; the rule only applies to direct `trivy fs` workflow calls.)
- **`npm audit --audit-level=high`** as an additional npm-specific check (built-in, free).
- **`pip-audit`** for Python projects without uv (or as a complement to Trivy).
- **Lockfile integrity:** fail if lockfile changed without a corresponding dependency update PR.
- **Renovate** (self-hosted, free) for automated, reviewable dependency update PRs. Configure `minimumReleaseAge: "7 days"` to enforce quarantine on automated updates. Never auto-merge.
- **osv-scanner** (optional, Apache 2.0) as a second opinion alongside Trivy.

#### 6.1 Binary integrity in CI

CI workflows that download release-tarball binaries (`curl | tar`,
GitHub release assets, etc.) **must** verify SHA256 before extraction.
Two acceptable patterns:

1. **Upstream `_checksums.txt` manifest** (preferred). Most projects
   that publish release tarballs also publish a checksums manifest
   alongside them (e.g., `trivy_<VERSION>_checksums.txt`,
   `gitleaks_<VERSION>_checksums.txt`,
   `sops-v<VERSION>.checksums.txt`). Pattern:

   ```bash
   curl -fsSL "${binary_url}" -o /tmp/binary.tar.gz
   curl -fsSL "${checksums_url}" -o /tmp/checksums.txt
   ( cd /tmp && grep " ${expected_artifact}\$" checksums.txt | sha256sum --check - )
   tar -xz -C "$HOME/.local/bin" -f /tmp/binary.tar.gz "${binary_name}"
   ```

2. **Hardcoded SHA256 in workflow env** (fallback). Some projects
   publish only Sigstore `.proof` attestations rather than a
   `_checksums.txt` manifest (notably `FiloSottile/age`). For those,
   compute the SHA256 once against the pinned release version and
   pin the value in workflow `env:`. Pattern:

   ```yaml
   env:
     AGE_VERSION: "1.3.1"
     AGE_LINUX_AMD64_SHA256: "bdc69c09cbdd6cf8b1f333d372a1f58247b3a33146406333e30c0f26e8f51377"
   ```

   ```bash
   curl -fsSL "${age_url}" -o /tmp/age.tar.gz
   echo "${AGE_LINUX_AMD64_SHA256}  /tmp/age.tar.gz" | sha256sum --check -
   ```

   Bumping the pinned version requires recomputing the hash against
   the new release. Record the computation date in a comment.

The unsigned `curl ... | tar -xz` pattern is **prohibited** in CI.
A network man-in-the-middle (or a compromised release asset that
hasn't been yanked yet) bypasses every other supply-chain control if
the binary itself isn't verified.

#### 6.2 Reusable-workflow SHA pinning

GitHub Actions reusable workflows referenced via `uses:` must pin to
a commit SHA, not a branch:

- **Wrong:** `uses: org/repo/.github/workflows/foo.yml@main`
- **Right:** `uses: org/repo/.github/workflows/foo.yml@<40-char-sha>  # source PR / date`

Combined with `secrets: inherit`, an unpinned reusable workflow
makes every consuming repo vulnerable to a single-point compromise
of the source repo. SHA-pinning constrains the blast radius to the
specific commit you reviewed at pin time.

The same rule applies to third-party Action `uses:` references
(`actions/checkout`, `astral-sh/setup-uv`, etc.) — pin to a 40-char
commit SHA with the tag name in a trailing comment for readability.

**Bumping a pin** is a multi-repo PR set whenever the source
workflow changes. Walk the consumer set, pick a known-good SHA on
the source repo's main branch, and update each consumer's pin in
its own PR. Add a comment naming the source PR or branch the SHA
was on at pin time so the audit trail stays intact across rotations.

**Pin shape: owner-controlled tag preferred over raw `@SHA` for
private→private reusable workflows.** GitHub's resolution of
`@<40-char-sha>` for cross-repo private→private reusable-workflow
calls is, in some configurations, stricter than `@<branch>` or
`@<tag>`. The observed failure mode is silent: every release fires
the workflow, but the run starts with 0 jobs, 0s duration, and a
"workflow file issue" message visible only via the GitHub web UI.
`gh run view --log` and `gh api .../jobs` return empty because
there is no job to log against. The rejection happens at
workflow-validation time before any step runs.

The supported pattern is an **owner-controlled annotated tag** on
the source repo (e.g., `@notify-updates-v1`,
`@dependency-gate-v1.0.2`) pinned to a specific reviewed commit.
The tag is immutable in practice (only the source-repo owner can
move it; do not), so the policy intent — pin to a specific audited
commit — is preserved. The tag → SHA mapping is recorded in the
source repo's release notes for that tag, which keeps the audit
trail intact end-to-end.

Caller-side comment convention:

```
uses: org/repo/.github/workflows/foo.yml@workflow-tag-vX  # tag → <40-char-sha> as of YYYY-MM-DD
```

This documents the resolution at pin time without re-introducing
the raw-SHA failure mode. Public-repo reusable workflows and
third-party Actions are not affected by the validation issue and
continue to follow the raw-SHA rule above.

**When a raw-SHA pin starts failing.** If a previously-working
`@<sha>` reference begins emitting silent 0-job runs after a
tooling or repo-config change, the recovery is to retag the source
commit and convert callers to the tag form. The SHA itself remains
in the audit trail via the tag's release notes.

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

### CVE exemption (automatic)

Updates that exist solely to close known CVEs are **exempt from the quarantine**. When `pip-audit` (or equivalent SCA tooling) detects a vulnerability with an available fix version, that fix may be adopted immediately regardless of its publish date.

This exemption is automatic in CI: the dep-scan job runs a two-phase audit that detects CVEs with available fixes and exempts them from the quarantine check. Locally, advance `exclude-newer` in `uv.toml` to include the fix version, run `uv lock --upgrade-package <pkg>`, and record the bypass in `.owb/quarantine-bypasses.jsonl`.

The exemption applies **only** to the specific packages with CVE fixes. All other packages remain subject to the full quarantine window. If advancing `exclude-newer` temporarily narrows the quarantine for other packages, that is an accepted tradeoff when security patches are involved.

**Audit trail:** every CVE exemption must be logged with the CVE IDs, the previous and new `exclude-newer` dates, and the package/version. The `record_cve_bypass()` function in `quarantine.py` handles this.

### Emergency bypass (manual)

For non-CVE situations where you genuinely need a package released in the last 7 days:
- For uv: use `--exclude-newer` with today's date to override the global setting
- For Trivy-flagged packages: add a `.trivyignore` entry with a comment explaining the justification. Review and remove ignore entries monthly.
- For Renovate: temporarily override `minimumReleaseAge` for a specific package in `renovate.json` with a comment and revert after the update merges.
- Document the bypass in the commit message with justification
- This should be rare (once or twice a year at most)

### ADR override procedure for `dependency-gate` PreToolUse hook blocks

The bundled `dependency-gate.py` PreToolUse hook (shipped at `vendor/ecc/hooks/dependency-gate.py` and registered at `~/.claude/hooks/dependency-gate.py` after `owb init`) blocks dependency-install commands when a finding violates project policy: license not on the allow-list, package inside the 7-day quarantine window, or unknown-package state. When the operator has independently judged a finding acceptable for a specific install, the sanctioned override path is:

1. **File an ADR exception** in the project's decisions index under `decisions/ADR-NNN-<package>-gate-exception.md` with:
   - The package name + version being exempted.
   - The finding category (license, quarantine, unknown).
   - The reason the operator judges the finding acceptable.
   - The expiry condition (e.g., "until upstream allow-list adds license X" or "until quarantine clock elapses on YYYY-MM-DD").
   - The blast radius (which workspace, which repo, which downstream consumers depend on the exempted package).
2. **One-time override commit** referencing the ADR. Two valid mechanisms:
   - For a one-shot package: pin its version exact in the manifest with an inline comment naming the ADR and the expiry condition (preferred — leaves an audit trail in the manifest itself).
   - For a class of first-party findings: add the package prefix to the hook's `--first-party-prefix` argument list. Only add prefixes for packages the operator owns or builds in-tree.
3. **Do NOT disable the hook globally.** Removing the hook from `settings.json` or flipping it to a permanent allow-everything configuration is not an ADR exception; it is a reversal of the policy that installed the gate. Reversal needs its own story.
4. **Review the ADR exception at sprint close.** If the expiry condition is met, remove the manifest pin (or the prefix entry) in the same sprint. If not, record the carryover in the next sprint's plan.

This procedure is the only sanctioned path for working around `dependency-gate` hook blocks. Filing the ADR before the override commit is a hard requirement; the commit message must reference the ADR ID.

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
