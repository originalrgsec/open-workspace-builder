# Public API Changes

This file is the canonical record of public-API changes between
consecutive open-workspace-builder releases. Downstream consumers
(claude-workspace-builder and any future packages depending on OWB)
read this file to absorb breaking changes in their next sprint.

## v1.14.1 → v1.15.0

### Added

- **`open_workspace_builder.config.ModelsConfig.security_scan_cross_file`**
  (field) — new optional model string, defaults to `""`.
  - **Why:** OWB-S136 HIGH-1 fix. The semantic scanner's cross-file
    correlation layer dispatches through
    `ModelBackend.completion(operation="security_scan_cross_file")`,
    but that operation was missing from `_VALID_OPERATIONS`, so every
    cross-file invocation raised `ModelBackendError` at runtime.
  - **Consumer impact:** none required. If you leave the field unset,
    `_resolve_model` falls back to the `security_scan` model.
  - **When to set:** only if you want a dedicated model for cross-file
    correlation (typically a larger-context model, since the user
    message concatenates all files in the bundle).

### Removed

(none this release)

### Renamed

(none this release)

### Signature Changed

(none this release)

### Internal-only changes (no migration needed)

These do not affect consumers but are listed for transparency:

- `auth/google.py`: `_load_age_public_key` removed (private; zero
  callers in OWB or tests — superseded by callers passing keys
  directly).
- `metrics/baseline.py`: `_is_test_path` removed (private; zero
  callers, left over from an earlier baseline collector shape).
- `security/trivy.py`: `SAFE_COMMIT_SHA` module constant removed
  (unused; version-based checks use `SAFE_VERSION` +
  `COMPROMISED_VERSIONS`).
- `security/drift.py`: `DriftStatus` dataclass removed (drift logic
  uses the string constants `"ok"`, `"modified"`, etc. directly; the
  `DriftStatus` wrapper had zero callers).
- `security/quarantine.py`: `CveAuditFinding` dataclass,
  `parse_pip_audit_json`, and `collect_cve_exemptions` removed (zero
  callers in OWB or CI; CVE exemption flow lives in the dependency
  gate hook now).

### Behaviour changes worth noting (no API change)

- **New ReDoS hardening in LLM JSON parsers.**
  `_llm_json.parse_json_object` and `parse_json_array` now cap input
  at 128 KiB before fence-regex matching
  (`_MAX_FENCE_INPUT = 131_072`). Legitimate LLM responses are well
  under this bound. Pathological inputs that previously risked
  catastrophic backtracking now fail fast with `ValueError("Could not
  parse ...")`. Same cap applied to the bracket fallback in
  `evaluator/generator._parse_test_cases`
  (`_MAX_BRACKET_INPUT = 131_072`). OWB-S136 HIGH-3 (CWE-1333).

- **LLM JSON error messages consolidated.** Five modules previously
  had slightly different phrasings for "could not parse LLM response
  as JSON". All now route through `_llm_json.parse_json_object`
  with a `context=` parameter; error messages are consistent across
  classifier, judge, org_layer, scorer, and semantic-scan paths.

- **`ModelsConfig` weight-vector defaults now deterministic.**
  `ManagerImpl._resolve_weight_vector` fell back to a uniform
  distribution over `REQUIRED_DIMENSIONS` (a `frozenset`). Key order
  was undefined. Now sorted. No change in weight values.

### Removal candidates (NOT removed this release — deferred to v2.0.0)

These public symbols have no known callers in OWB or tests, but
removing them is a breaking change and CWB (the primary consumer) is
currently dormant — we preserve them for the v1.x series pending a
future audit with CWB in active development.

- **`open_workspace_builder.llm.backend.ModelBackend.completion`**
  `response_format` parameter — accepted but never forwarded to the
  underlying litellm call (100% vulture confidence). Kept for now;
  any reliance on it by CWB would be silent. **Migration when
  removed:** drop the argument; set `response_format` inside your
  system prompt if needed.

- **`open_workspace_builder.cli`** `--non-interactive` flag on
  `metrics baseline` — accepted as a Click option but never read in
  the command body. **Migration when removed:** omit the flag.

### Scope and exclusions

- `src/open_workspace_builder/vendor/` is out of refactor-clean
  scope. Any dead code there is filed upstream at the ECC source and
  re-vendored per OWB-S131.
- `OrgLayerClassifier` is kept — tests exist in
  `tests/evaluator/test_org_layer.py`.

### Downstream coordination

- **CWB:** dormant per operator. This changelog is produced for
  future CWB resume or any external consumer. The
  `ModelsConfig.security_scan_cross_file` addition is backward
  compatible (default empty, fallback to `security_scan`) so no CWB
  action is required.
