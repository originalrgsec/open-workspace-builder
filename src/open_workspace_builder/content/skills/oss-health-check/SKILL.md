---
name: oss-health-check
description: >-
  Evaluate the health and sustainability of open source projects before adopting
  them as dependencies. Use this skill when the user asks to assess dependency
  health, compare open source options, or check project maintenance status.
---

# OSS Health Check

Evaluate open source project health using quantitative signals from GitHub and package registries, scored against a configurable OSS health policy.

## When to Use

- User asks whether an open source project is healthy, maintained, or safe to adopt
- User wants to compare two or more open source options
- User wants to audit existing dependencies for health risks
- User mentions evaluating a GitHub repo, npm package, PyPI package, or Rust crate
- User references the OSS health policy or dependency evaluation

## Environment Detection

This skill runs in two environments. Detect which one and adjust behavior.

**CLI agent (Claude Code in terminal):**
- You have direct access to `bash`, `gh`, `python`, and `owb` commands.
- Use structured terminal output (tables, headers).
- Prefer `gh api` over raw HTTP for GitHub data (authenticated by default, higher rate limits).
- Use `owb audit licenses` and `owb audit deps` for supply-chain dimensions.

**Desktop agent (Cowork):**
- You run tools through the Cowork tool interface.
- Present results in UI-friendly markdown with collapsible sections.
- The health_check.py script handles all data collection; you format the output.

## Workflow

### 1. Identify the Target

Extract from the user's request:
- **GitHub repo** (e.g., `pallets/flask`, `https://github.com/pallets/flask`)
- **Package name and ecosystem** (e.g., `flask` on PyPI, `express` on npm, `serde` on crates.io)

If the user gives a package name without a repo, resolve the GitHub repo from the package registry metadata. If the user gives only a repo, detect the ecosystem from repository contents.

### 2. Collect Health Signals

#### Option A: CLI Agent (preferred when `gh` and `owb` are available)

Run these data collection steps. Steps 2a, 2b, and 2c are independent and can run in parallel.

**Step 2a: GitHub health metrics via `gh api`**

```bash
# Repository info (stars, archived status, license, description)
gh api repos/{owner}/{repo}

# Recent commits (last commit date, frequency)
gh api repos/{owner}/{repo}/commits?per_page=50

# Releases (cadence, last release date)
gh api repos/{owner}/{repo}/releases?per_page=10

# Contributors (bus factor, concentration)
gh api repos/{owner}/{repo}/contributors?per_page=30

# Open issues sample (response time estimate)
gh api "repos/{owner}/{repo}/issues?state=all&per_page=30&sort=created&direction=desc"

# Open PRs (staleness)
gh api "repos/{owner}/{repo}/pulls?state=open&per_page=30&sort=created&direction=desc"

# Community profile (SECURITY.md, CONTRIBUTING.md, etc.)
gh api repos/{owner}/{repo}/community/profile

# Check for Dependabot
gh api repos/{owner}/{repo}/contents/.github/dependabot.yml
```

**Step 2b: Package registry stats**

For PyPI:
```bash
curl -s "https://pypi.org/pypi/{package}/json"
curl -s "https://pypistats.org/api/packages/{package}/recent"
```

For npm:
```bash
curl -s "https://api.npmjs.org/downloads/point/last-week/{package}"
```

For crates.io:
```bash
curl -s "https://crates.io/api/v1/crates/{package}" -H "User-Agent: oss-health-check"
```

**Step 2c: OWB supply-chain audits (Python ecosystem only)**

```bash
# License compliance against allowed-licenses policy
owb audit licenses --format json

# Vulnerability scan (pip-audit)
owb audit deps --format json

# Single-package pre-adoption scan (both CVE and malware checks)
owb audit package {package} --format json
```

#### Option B: Script Mode (desktop agent, or when `gh` is unavailable)

```bash
python <skill-path>/scripts/health_check.py \
  --repo <owner/repo> \
  [--ecosystem npm|pypi|crates] \
  [--package <name>] \
  [--github-token <token>]
```

The script outputs a JSON report to stdout. Capture it for analysis.

**Arguments:**
- `--repo` (required): GitHub owner/repo (e.g., `pallets/flask`)
- `--ecosystem` (optional): Package ecosystem for download stats. One of `npm`, `pypi`, `crates`. Auto-detected if omitted.
- `--package` (optional): Package name if different from repo name
- `--github-token` (optional): GitHub personal access token. Falls back to `GITHUB_TOKEN` env var. Without authentication, the API allows 60 requests/hour.

### 3. Score Against Policy

Apply the OSS health policy scoring rules across all dimensions. The policy is at `content/policies/oss-health-policy.md`. The thresholds are summarized here for quick reference:

#### Maintenance Activity

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Time since last commit | < 3 months | 3-6 months | > 12 months |
| Release cadence | Regular/predictable | Irregular but active | No release in 12+ months |
| Median issue response time | < 7 days | 7-30 days | > 90 days |
| PR merge rate | PRs reviewed regularly | Slow but active | PRs ignored 30+ days |

#### Bus Factor / Contributor Health

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Significant contributors (>5% of commits) | 3+ | 2 | 1 |
| Top contributor concentration | < 70% | 70-90% | > 90% |

#### Community and Adoption

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| GitHub stars | > 1,000 | 100-1,000 | < 100 |
| Weekly downloads | > 10,000 | 1,000-10,000 | < 1,000 |

#### Funding and Sponsorship

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Org-backed + funding file | Yes | Partial | Neither |

#### Documentation and API Stability

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Presence of README + CONTRIBUTING + CHANGELOG + homepage | 3+ of 4 | 2 of 4 | < 2 |

#### Security Posture

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| SECURITY.md + Dependabot | Both | One | Neither (auto caps at Yellow; Red requires CVE evidence) |

#### License Compliance (from `owb audit licenses`, Python only)

| Status | Rating |
|--------|--------|
| All dependencies pass allowed-licenses policy | Green |
| Any conditional findings (e.g., MPL 2.0) | Yellow |
| Any fail or unknown licenses | Red |

#### Dependency Health (from `owb audit deps`, Python only)

| Status | Rating |
|--------|--------|
| No vulnerabilities found | Green |
| Skipped packages only | Yellow |
| Known vulnerabilities found | Red |

### 4. Present Results

**Report format:**

```
# OSS Health Report: <project-name>

**Overall Rating: [GREEN/YELLOW/RED]**
**Evaluated:** <date>
**Repository:** <github-url>
**Package:** <ecosystem>/<package-name>

## Category Ratings

| Category | Rating | Key Signal |
|----------|--------|------------|
| Maintenance Activity | GREEN | Last commit 3 days ago, monthly releases |
| Bus Factor | YELLOW | 2 significant contributors |
| Community & Adoption | GREEN | 15K stars, 2.1M weekly downloads |
| Funding | YELLOW | GitHub Sponsors active, no corporate backing |
| Documentation & API Stability | GREEN | README, CONTRIBUTING, CHANGELOG present |
| Security Posture | GREEN | SECURITY.md present, Dependabot active |
| License Compliance | GREEN | All dependencies pass policy |
| Dependency Health | GREEN | No known vulnerabilities |

## Detailed Findings

[For each category, list the specific signals checked and their values]

## Recommendation

[Based on the scoring rules:
- Any Red in Maintenance or Security → REJECT. Find an alternative.
- Any Red elsewhere → Strong caution. Document justification via ADR.
- 2+ Yellows → Closer evaluation needed. Document risk assessment.
- All Green → Adopt with confidence.]

## Signals Requiring Human Review

[List qualitative signals the script cannot fully assess:
- Documentation quality (comprehensive vs adequate vs minimal)
- Migration guide presence and quality
- Semver discipline (requires changelog review)
- Deprecation warning practices
- CVE response time and third-party audit history]
```

### 5. Comparison Mode

When the user asks to compare two or more projects, run the check on each and present a side-by-side table:

```
| Signal | Project A | Project B |
|--------|-----------|-----------|
| Overall | GREEN | YELLOW |
| Last commit | 2 days ago | 4 months ago |
| Contributors | 12 | 3 |
| Weekly downloads | 500K | 12K |
| License Compliance | GREEN | YELLOW (MPL 2.0 conditional) |
| ... | ... | ... |
```

End with a clear recommendation stating which project is the stronger choice and why.

### 6. Batch Audit Mode

When the user asks to audit a `package.json`, `requirements.txt`, `Cargo.toml`, or similar manifest:
1. Parse the manifest to extract dependencies
2. For Python projects, run `owb audit licenses` and `owb audit deps` first for quick coverage across all dependencies
3. Run the full health check on each dependency needing deeper evaluation (be mindful of GitHub rate limits)
4. Present a summary table sorted by risk (Red first, then Yellow, then Green)
5. Flag any dependencies that warrant replacement

## Policy Reference

The scoring thresholds are defined in `content/policies/oss-health-policy.md`. If the user asks to adjust thresholds or the policy changes, update the script's `THRESHOLDS` dict to match.

## Limitations

- GitHub API without authentication: 60 requests/hour. A single project check uses 4-6 requests. Batch audits of large manifests will need a token or `gh auth login`.
- Download statistics lag by 24-48 hours on most registries.
- The script cannot assess subjective quality (documentation comprehensiveness, API design quality). Always flag these for human review.
- Private repositories require a GitHub token with appropriate scopes.
- `owb audit licenses` and `owb audit deps` are Python-only. For npm/Rust, license and vulnerability checks require ecosystem-specific tools (e.g., `npx license-checker`, `cargo deny`).
