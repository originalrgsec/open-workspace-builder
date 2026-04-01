---
type: research-spike
id:
title:
status: backlog
project:
sprint:
priority:
stage:
time-box:
created:
updated:
related: []
cross-project: []
tags: [research-spike]
---

# SP-000: Spike Title

## Purpose

(What question does this spike answer? What decision does it unblock? One to two sentences that establish why this research is necessary before implementation can proceed.)

- PRD reference: [[projects/project-name/prd#section]]
- Decision to unblock: [[decisions/_index#DRN-NNN]] or "new decision required"

## Scope

(Define research tracks. Each track is a parallel line of investigation with its own candidates and evaluation criteria. Spikes with a single track are fine; use multiple tracks when the research spans distinct domains that can be investigated concurrently.)

### Track 1: [domain name]

**Question:** (The specific question this track answers.)

**Known candidates:**

- [Candidate A](URL) — one-line description of what it is and why it is relevant
- [Candidate B](URL) — one-line description

**Evaluation criteria:**

- (Criterion 1 — what does "good" look like for this criterion?)
- (Criterion 2)
- (Criterion 3)

**OWB tooling to apply:**

- [ ] `owb security scan` on content files (three-layer)
- [ ] `owb eval` on agent/skill definitions
- [ ] `owb audit deps` on Python dependencies
- [ ] `owb audit licenses` against allowed-licenses policy
- [ ] OSS health check skill for repo-level assessment
- [ ] (other — specify)

### Track N: [domain name]

(Repeat structure for each track.)

## Integration Analysis

(How do the tracks compose? After individual candidates are evaluated, what are the integration questions? This section may be empty at spike creation and filled during execution.)

- Track X ↔ Track Y: (integration question)
- OWB integration surface: (where does OWB inject policy, scanning, or evaluation?)

## Time Box

(Maximum effort before the spike must produce a recommendation, even if incomplete. Spikes that exceed their time box without a clear recommendation are escalated for scope reduction.)

- **Budget:** [N hours / N days / 1 sprint]
- **Escalation if exceeded:** (what happens — reduce scope, extend with approval, or force a decision with available data)

## Deliverables

1. **Research notes** in `research/processed/` with `projects: [project-name]` frontmatter, one per candidate evaluated
2. **OSS health reports** for each candidate repo (Green/Yellow/Red per `code/oss-health-policy.md`)
3. **Security scan reports** for any agent definitions, prompt files, or config templates in candidate repos
4. **Evaluation matrix** — comparison table across tracks (vault note or spreadsheet)
5. **Architecture recommendation** — proposed approach with rationale, risks, and integration points
6. **Decision record** — if the spike produces an architectural decision, file it using `_templates/decision-record.md` and index it in `decisions/_index.md`

## Cross-Project Dependencies

(List any projects affected by the spike's outcome. For each, note what kind of dependency it is: API change, config schema change, documentation update, etc.)

| Project | Dependency Type | Notes |
|---------|----------------|-------|
| | | |

## Acceptance Criteria

(Spikes do not have Given/When/Then criteria like implementation stories. Instead, acceptance is about coverage and decision quality.)

1. All known candidates evaluated against stated criteria
2. All evaluations produced using OWB toolchain (no manual-only assessments) where applicable
3. Evaluation matrix populated and reviewed
4. Architecture recommendation drafted with rationale and risk assessment
5. Decision record filed if recommendation is accepted
6. Time box respected or escalation documented

## Outcome

(Filled after spike completion.)

- **Recommendation:**
- **Decision record:** [[decisions/_index#DRN-NNN]]
- **Stories spawned:** (list any implementation stories created as a result)
- **Open questions remaining:**
