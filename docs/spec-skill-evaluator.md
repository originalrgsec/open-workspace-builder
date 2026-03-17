# Spec: Skill Evaluator

## Purpose

Automated evaluation framework for Claude skills that scores candidates across four weighted dimensions, compares against baselines and existing skills, and makes incorporate/reject/deprecate decisions. The evaluator integrates with the workspace builder's existing security scanner and multi-source vendor system to create a complete skill lifecycle: discover, scan, evaluate, incorporate, track, re-evaluate on update.

## Evaluation Dimensions

| Dimension | Description | Measurement |
|-----------|-------------|-------------|
| Novelty | Usefulness in producing new ideas, creative or analytical approaches | Judge prompt compares diversity, originality, and unexpectedness of outputs vs baseline |
| Efficiency | Token economy for equivalent task completion | Instrument token usage across identical prompts, compute ratio |
| Precision & Accuracy | How well the skill understands and executes user intent | Structured tasks with known-correct outputs, score against ground truth |
| Defect Rate | Quality of error-free responses or code | Run code generation tasks, count syntax errors, test failures, lint violations, factual errors |

## Dimension Weighting

Weights are determined dynamically per skill by a classifier that maps skill type to a weight vector. The classifier runs on Ollama using Llama 3.2 (same model and pattern as the ingest-pipeline classifier).

Example weight vectors by skill type:

| Skill Type | Novelty | Efficiency | Precision | Defect Rate |
|------------|---------|------------|-----------|-------------|
| Marketing / copywriting | 0.40 | 0.15 | 0.25 | 0.20 |
| Security analysis | 0.10 | 0.20 | 0.35 | 0.35 |
| Code review | 0.10 | 0.20 | 0.30 | 0.40 |
| Research / analysis | 0.30 | 0.15 | 0.35 | 0.20 |
| Project management | 0.15 | 0.25 | 0.35 | 0.25 |

The weight mapping is configurable and stored as data (YAML), not hardcoded.

## Evaluation Use Cases

### UC-1: Brand New Skill

A skill from a new source with no existing equivalent in the workspace.

1. Classifier determines skill type — weight vector (Ollama, Llama 3.2)
2. Test generator creates a tailored test suite for the skill's stated capabilities (Ollama, Mistral Small 22B Q4)
3. Test suite runs against: (a) baseline (raw Claude, no skills), (b) the candidate skill
4. Results scored across all four dimensions using the weight vector (Ollama, Mistral Small 22B Q4)
5. Composite score computed. If delta vs baseline exceeds the incorporation threshold, recommend incorporation.
6. Test suite and results persisted as skill metadata for future comparisons.

### UC-2: Replacing or Updating an Existing Skill

A new version of an existing skill, or a different skill from a different source that does the same thing.

1. Load the existing skill's persisted test suite and scores.
2. Run the same test suite against the new candidate.
3. Score the candidate. Compare composite scores directly.
4. If the new skill scores higher by at least the incorporation threshold, recommend replacement. Deprecate the old skill.
5. Update metadata: old skill gets `superseded_by`, new skill gets `supersedes`.

### UC-3: Partial Overlap with New Functionality

A new skill that overlaps with an existing one but adds capabilities.

1. Run the existing skill's test suite against the candidate (covers overlapping functionality).
2. Generate new tests for the candidate's additional capabilities (same as UC-1 step 2, but scoped to new functionality only).
3. Score across both test sets.
4. If the candidate matches or exceeds the existing skill on overlapping tests AND scores above baseline on new functionality, recommend incorporation and deprecation of the old skill.

## Models and Infrastructure

### Classification (Tier 1): Llama 3.2 (8B) on Ollama

Determines skill type from SKILL.md content. Maps type to dimension weight vector. This is the same model and pattern used in the ingest-pipeline classifier. Shared via the `volcanix-classifier` Python package (Option A: shared package).

### Test Generation and Quality Judgment (Tier 2): Mistral Small 22B Q4 on Ollama

Generates test prompts tailored to skill capabilities. Judges output quality across the four dimensions. Mistral Small 22B at Q4 quantization uses ~16GB memory and runs on M1 Pro 32GB with headroom for OS.

### Resource Management

Ollama loads models on demand. To minimize resource consumption:

- The evaluator explicitly loads the model at the start of an evaluation batch.
- The evaluator explicitly unloads the model when the batch completes (no waiting for the 5-minute idle timeout).
- Implementation: `ollama stop mistral-small` after the last evaluation call returns.
- During evaluation, the system will use ~16GB for Mistral Small + ~6GB for Llama 3.2 if both are loaded. Run them sequentially (classify first with Llama, unload, then evaluate with Mistral) to keep peak usage at ~16GB.

### Fallback: Async Vault-Based Workflow

If Mistral Small 22B proves insufficient for Tier 2 quality judgment on specific skill types, a fallback workflow exists. The fallback routes evaluation requests through the Obsidian vault's research inbox for human-in-the-loop scoring in a Cowork session, at zero additional API cost.

## Scoring and Thresholds

### Composite Score

Weighted average of the four dimension scores:

```
composite = (novelty * w_n) + (efficiency * w_e) + (precision * w_p) + (defect_rate * w_d)
```

Each dimension is scored on a 1-10 scale. Composite range is 1.0-10.0.

### Incorporation Threshold

A candidate skill must score at least `threshold` points above both:
- The baseline composite (raw Claude, no skills)
- Any existing duplicative skill's composite

Default threshold: 1.0 (configurable in config.yaml). This prevents churn from marginal improvements.

### Score Persistence

All scores are stored in skill metadata at `vendor/<source>/.skill-meta/<skill-name>.json`:

```json
{
  "skill_name": "security-reviewer",
  "source": "ecc",
  "skill_type": "security-analyst",
  "version": "abc123",
  "evaluated": "2026-03-16T22:00:00Z",
  "classifier_model": "llama3.2:8b",
  "evaluator_model": "mistral-small:22b-q4",
  "weights": {"novelty": 0.1, "efficiency": 0.2, "precision": 0.4, "defect_rate": 0.3},
  "scores": {
    "novelty": {"raw": 7.2, "weighted": 0.72},
    "efficiency": {"raw": 8.1, "weighted": 1.62},
    "precision": {"raw": 8.8, "weighted": 3.52},
    "defect_rate": {"raw": 9.0, "weighted": 2.70}
  },
  "composite": 8.56,
  "baseline_composite": 5.2,
  "delta_vs_baseline": 3.36,
  "supersedes": null,
  "superseded_by": null,
  "test_suite_hash": "sha256:...",
  "test_results_path": ".skill-meta/tests/security-reviewer/"
}
```

Test suites persist alongside metadata so they can be reused for UC-2 comparisons.

## Multi-Source Skill Tracking

Skills removed during a competitive evaluation are tracked in the skill metadata (`superseded_by` field). When the superseded skill's source publishes an update, the evaluator automatically re-runs the stored test suite against the updated version. If the updated skill now exceeds the current incumbent, it can be re-incorporated and the incumbent deprecated. This creates a dynamic best-of-breed selection across multiple third-party sources.

## Ingest Pipeline Integration

The ingest-pipeline processes bookmarks from X, RSS, and other sources. When a processed bookmark points to a GitHub repo containing Claude skills (detected by presence of SKILL.md files or relevant topic tags), the pipeline outputs a structured reference to `research/skill-candidates/` in the vault. The workspace builder's evaluator consumes these candidates as input to the evaluation workflow.

The pipeline produces; the builder evaluates and installs. The boundary is clean: the pipeline has no opinion on skill quality, and the builder has no awareness of content sources.

## CLI

```
cwb eval <skill-path>                  # evaluate a new skill (UC-1)
cwb eval <skill-path> --compare        # compare against existing duplicative skills (UC-2/UC-3)
cwb eval --list                        # show all evaluated skills with scores
cwb eval --rerun <skill-name>          # re-evaluate with current test suite
cwb eval --rerun-superseded            # re-evaluate all superseded skills against current incumbents
```

## Pre-Build Reminders (Discuss Before Sprint 4)

### 1. Repo-Level Security Concerns Beyond Per-Skill Evaluation

When ECC was first brought in, the security audit identified issues at the repo level that went beyond any individual skill file. Specifically, the continuous learning capability had hooks and triggers that were recommended for exclusion. The evaluator as currently designed operates per-skill (score one SKILL.md at a time), but a new upstream repo may contain architectural-level risks that span multiple files or involve non-skill content (hooks, event triggers, config modifications, init scripts). The evaluator needs a repo-level triage step before per-skill evaluation begins. This might mean extending the security scanner to produce a repo-level assessment (not just per-file verdicts) that flags structural concerns like event hooks, auto-execution patterns, and cross-file dependencies.

### 2. Skill Discovery Across Varied Repo Structures

ECC organizes skills in a known structure, but every new upstream repo the builder encounters will be organized differently. Some repos will have a `skills/` directory, others will scatter skill definitions across nested paths, and some may use different naming conventions or file structures entirely. The evaluator needs a skill discovery module that can locate SKILL.md files (or equivalent) in an unfamiliar repo. This could be a combination of glob patterns, content-based detection (look for files that structurally resemble skill definitions), and a configurable mapping in the builder's config that maps repo URL to discovery rules. Without this, adding a second or third upstream source will require manual file-by-file identification every time.

## Open Questions

1. What is the right scoring rubric for the novelty dimension? It is the most subjective. Should we use a panel of N runs and take the median score, or a single-pass judgment?
2. Should the evaluator run automatically during `cwb ecc update` (evaluate every new/changed skill), or only on explicit `cwb eval` invocation?
3. Should the incorporation threshold be a single number or per-dimension minimums (e.g., defect rate must be above 7.0 regardless of composite)?
4. How many test cases per dimension constitutes a sufficient test suite? Too few gives noisy results; too many burns tokens on local inference.
5. What does the repo-level triage step look like? Is it a separate `cwb repo audit` command, or a mandatory first phase within `cwb ecc update` before per-file scanning begins?
6. Should skill discovery rules be community-contributed (a registry of repo-to-structure mappings), or strictly owner-maintained?

## Links

- [PRD](./prd.md)
- [ADR](./adr.md)
- [SDR](./sdr.md)
