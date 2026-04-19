---
type: policy
created: 2026-03-13
updated: 2026-04-19
tags: [policy, open-source, dependencies, risk]
applies-to: all-projects
related: "allowed-licenses"
---

# Open Source Project Health Evaluation Policy

## Pre-Install Gate (MANDATORY)

**Before running any package install command** — `uv pip install`, `uv add`, `pip install`, `npm install`, `cargo add`, `go get`, `brew install`, or equivalents — verify the target package's license against `allowed-licenses.md`. Bits on disk is the point of no return; once a package is installed, tests are running against it, and code is being written to import it, removing it becomes a sunk-cost argument rather than a clean decision.

**The rule, stated positively:** No new dependency enters the venv, `node_modules`, `Cargo.lock`, `go.sum`, or any other dependency manifest until all four checks below have passed.

**The sequencing:**

1. **License check first.** Fetch the package's `LICENSE` file (or read the PyPI / npm / crates.io license field — but prefer the real `LICENSE` file because registry metadata is sometimes wrong or coarse). Compare against `allowed-licenses.md`.
   - If the license is in the Allowed (Permissive) table → proceed to health check.
   - If the license is Allowed with Conditions → verify the condition does not apply to the use case, then proceed.
   - If the license is Disallowed, or the file reports "Other/Proprietary License," or the license is custom and not in the policy tables → **STOP**. Do not install. Escalate for a policy exception ADR or find an alternative. A PyPI / npm classifier of "Other/Proprietary License" is always a stop-the-line signal, not a follow-up.
2. **Health check second.** Only if the license check passes. Run the `oss-health-check` skill (or the project's equivalent script). Record the overall rating, date, and any flags in the project's `oss-health-policy-scores.md`. Apply the scoring rules from this document.
3. **Supply-chain post-release window check.** Verify the package version's publication date is older than the quarantine threshold in `supply-chain-protection.md` (currently 7 days).
4. **Only then** run the install command and write code.

**"License check owed" is an anti-pattern.** If you have written "license check still required" or "license check owed as follow-up" anywhere in a score entry, ADR, CHANGELOG, or session log, that is a stop-the-line signal. The dependency must not remain in the codebase — committed or not — until the check completes. There is no legitimate "implemented, license TBD" state.

**Retroactive scoring is a process smell.** If you find yourself writing an oss-health score entry for a dependency that has already been installed, committed, and pushed, something went wrong earlier in the workflow. Record the score anyway, but also file a retrospective note identifying the sequencing failure and propose a process fix. Retroactive scores should be rare and individually explained, not routine.

## Purpose

After a dependency passes the license check, it must also pass a health evaluation before adoption. The goal is to avoid depending on projects that are likely to be abandoned, inadequately maintained, or too fragile to sustain over a 2-3 year horizon — the window within which a forced replacement becomes a painful refactor.

This policy defines the criteria, thresholds, and scoring system for evaluating open source project health. A companion skill (`oss-health-check`) automates the quantitative signals; qualitative factors require human judgment.

## Rating System

Projects receive a **Green / Yellow / Red** rating. Any single Red flag is grounds to reject the dependency and find an alternative. Two or more Yellow flags warrant a closer look and a documented justification if adopted.

## Evaluation Criteria

### 1. Maintenance Activity

The strongest predictor of project survival. A project with regular commits, responsive triage, and predictable releases is unlikely to die without warning.

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Time since last commit | < 3 months | 3-6 months | > 12 months |
| Release cadence | Regular/predictable | Irregular but active | No release in 12+ months |
| Median issue response time | < 7 days | 7-30 days | > 90 days or no responses |
| Open issue trend | Stable or declining | Growing slowly | Growing rapidly with no triage |
| PR merge rate | PRs reviewed and merged regularly | Slow but active | PRs ignored or stale (30+ days) |

### 2. Bus Factor / Contributor Health

Measures resilience to individual contributor departure.

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Contributors with merge access | 3+ | 2 | 1 (solo maintainer) |
| Commit distribution | No single contributor > 70% | One contributor 70-90% | One contributor > 90% |
| Organizational backing | Foundation or company-sponsored | Informal team | Solo individual, no org |
| Maintainer succession plan | Documented or org-backed | Implied by team size | None visible |

### 3. Community and Adoption

Indicates whether the project has enough gravity to sustain itself.

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| GitHub stars | > 1,000 | 100-1,000 | < 100 |
| Star velocity | Trending up or stable | Flat | Declining |
| Weekly downloads (npm/PyPI/crates) | > 10,000 | 1,000-10,000 | < 1,000 |
| Dependent packages | > 100 | 10-100 | < 10 |
| Stack Overflow presence | Active Q&A | Some questions | None |

### 4. Funding and Sponsorship

Financial sustainability reduces abandonment risk.

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Funding model | Corporate sponsor or foundation grant | GitHub Sponsors / Open Collective with active donors | No funding model |
| Paid contributors | At least one contributor paid to work on the project | Occasional bounties | All volunteer |

Note: Lack of funding alone is not disqualifying if other signals are strong. Many healthy projects are volunteer-run. But unfunded + solo maintainer + growing adoption is a fragility pattern.

### 5. Documentation and API Stability

Signals maturity and respect for downstream consumers.

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| Semver discipline | Strict semver, no surprise breaks | Mostly follows semver | Frequent breaking changes without major version bumps |
| Changelog | Maintained with each release | Exists but sporadic | None |
| Migration guides | Provided for breaking changes | Partial | None, breaking changes undocumented |
| Documentation quality | Comprehensive, up to date | Adequate | Minimal or outdated |
| Deprecation warnings | Used before removal | Sometimes | Features removed without warning |

### 6. Security Posture

Critical for any project handling sensitive data or operating in regulated environments.

| Signal | Green | Yellow | Red |
|--------|-------|--------|-----|
| SECURITY.md / disclosure process | Documented responsible disclosure | Email contact for security | None |
| CVE response time | Patches within days-weeks | Patches within months | Known unpatched CVEs |
| Dependency scanning in CI | Active (Dependabot, Snyk, etc.) | Partial | None |
| Security audit history | Audited by third party | Self-audited | Never audited |

## Scoring Rules

1. **Any single Red in Maintenance Activity or Security Posture** → Reject. Find an alternative.
2. **Any single Red in other categories** → Strong caution. Document justification if adopting.
3. **Two or more Yellows across any categories** → Closer evaluation required. Document the risk assessment.
4. **All Green** → Adopt with confidence.

## Exception Process

If a dependency with Red or multiple Yellow flags has no viable alternative, document the following in the project's `decisions/` folder as an ADR:

- Which signals failed and why the risk is acceptable
- Mitigation strategy (vendoring, fork plan, abstraction layer to ease future replacement)
- Review trigger (what would cause re-evaluation — maintainer departure, CVE, competing project maturity)
- Review date (no longer than 12 months)

## Automation

The `oss-health-check` skill automates quantitative signal collection from GitHub API, npm registry, PyPI, and crates.io. It produces a structured health report with the rating. Qualitative signals (documentation quality, API stability discipline, migration guide quality) require human review of the output.

## ADR Integration

Every architectural decision that selects an open source dependency must include a license check and health check before the decision is accepted. The ADR template (`_templates/adr.md`) includes fields for both. The required workflow is:

1. **License check first.** Verify the project's license against `allowed-licenses.md`. If the license is Disallowed, stop — do not proceed to the health check. Find an alternative or document a policy exception per the exception process above.
2. **Health check second.** Run the `oss-health-check` skill (or the health check script directly). Record the overall rating, date, and any flags in the AD entry. Apply the scoring rules from this document.
3. **Record results in the ADR.** Each AD entry must show the license name, allowed/disallowed status, health rating, and any action items.
4. **Flag blockers in decisions index.** If a license or health finding requires a follow-up decision, add it to `decisions/_index.md` under Pending Decisions so it is visible across sessions.

## Review Schedule

Review this policy annually or when adopting a new technology ecosystem.
