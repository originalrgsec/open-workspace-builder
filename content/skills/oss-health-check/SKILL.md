---
name: oss-health-check
description: "Evaluate the health and sustainability of open source projects before adopting them as dependencies. Use this skill whenever the user wants to assess whether an open source library, framework, or tool is safe to depend on — including questions like 'is this project well maintained?', 'should I use X or Y?', 'is this dependency risky?', 'evaluate this GitHub repo', or any request to check project health, maintenance status, bus factor, community activity, or abandonment risk. Also trigger when the user asks to compare two or more open source options, audit current dependencies for health risks, or assess a project against the OSS health policy. This skill runs automated checks against GitHub API and package registries (npm, PyPI, crates.io) and produces a structured Green/Yellow/Red health report."
---

# OSS Health Check

Evaluate open source project health using quantitative signals from GitHub and package registries, scored against a configurable OSS health policy.

## When to Use

- User asks whether an open source project is healthy, maintained, or safe to adopt
- User wants to compare two or more open source options
- User wants to audit existing dependencies for health risks
- User mentions evaluating a GitHub repo, npm package, PyPI package, or Rust crate
- User references the OSS health policy or dependency evaluation

## Workflow

### 1. Identify the Target

Extract from the user's request:
- **GitHub repo** (e.g., `pallets/flask`, `https://github.com/pallets/flask`)
- **Package name and ecosystem** (e.g., `flask` on PyPI, `express` on npm, `serde` on crates.io)

If the user gives a package name without a repo, the script will attempt to resolve the GitHub repo from the package registry metadata. If the user gives only a repo, the script will attempt to detect the ecosystem from repository contents.

### 2. Run the Health Check Script

```bash
python <skill-path>/scripts/health_check.py --repo <owner/repo> [--ecosystem npm|pypi|crates] [--package <name>] [--github-token <token>]
```

The script outputs a JSON report to stdout. Capture it for analysis.

**Arguments:**
- `--repo` (required): GitHub owner/repo (e.g., `pallets/flask`)
- `--ecosystem` (optional): Package ecosystem for download stats. One of `npm`, `pypi`, `crates`. Auto-detected if omitted.
- `--package` (optional): Package name if different from repo name
- `--github-token` (optional): GitHub personal access token for higher rate limits. Without it, the API allows 60 requests/hour which is enough for a single check but may hit limits on batch runs.

### 3. Interpret Results

The script produces ratings per category matching the policy in `code/oss-health-policy.md`. Present the results as a structured report:

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
| Bus Factor | YELLOW | 2 contributors with merge access |
| Community & Adoption | GREEN | 15K stars, 2.1M weekly downloads |
| Funding | YELLOW | GitHub Sponsors active, no corporate backing |
| Documentation & API Stability | GREEN | Strict semver, comprehensive docs |
| Security Posture | GREEN | SECURITY.md present, Dependabot active |

## Detailed Findings

[For each category, list the specific signals checked and their values]

## Recommendation

[Based on the scoring rules from the policy:
- Any Red in Maintenance or Security → Reject
- Any Red elsewhere → Strong caution with justification
- 2+ Yellows → Closer evaluation needed
- All Green → Adopt with confidence]

## Signals Requiring Human Review

[List qualitative signals the script cannot fully assess:
- Documentation quality (comprehensive vs adequate vs minimal)
- Migration guide presence and quality
- Semver discipline (requires changelog review)
- Deprecation warning practices]
```

### 4. Comparison Mode

When the user asks to compare two or more projects, run the script on each and present a side-by-side table:

```
| Signal | Project A | Project B |
|--------|-----------|-----------|
| Overall | GREEN | YELLOW |
| Last commit | 2 days ago | 4 months ago |
| Contributors | 12 | 3 |
| Weekly downloads | 500K | 12K |
| ... | ... | ... |
```

End with a clear recommendation stating which project is the stronger choice and why.

### 5. Batch Audit Mode

When the user asks to audit a `package.json`, `requirements.txt`, `Cargo.toml`, or similar manifest:
1. Parse the manifest to extract dependencies
2. Run the health check on each (be mindful of GitHub rate limits without a token)
3. Present a summary table sorted by risk (Red first, then Yellow, then Green)
4. Flag any dependencies that warrant replacement

## Policy Reference

The scoring thresholds are defined in the Obsidian vault at `code/oss-health-policy.md`. If the user asks to adjust thresholds or the policy changes, update the script's `THRESHOLDS` dict to match.

## Limitations

- GitHub API without authentication: 60 requests/hour. A single project check uses 4-6 requests. Batch audits of large manifests will need a token.
- Download statistics lag by 24-48 hours on most registries.
- The script cannot assess subjective quality (documentation comprehensiveness, API design quality). Always flag these for human review.
- Private repositories require a GitHub token with appropriate scopes.
