# Public API Changes

This file is the canonical record of public-API changes between
consecutive open-workspace-builder releases. Downstream consumers
(claude-workspace-builder and any future packages depending on OWB)
read this file to absorb breaking changes in their next sprint.

## v1.16.0 → v1.17.0

### Signature Changed — `sbom.builder.build_bom`

- **Before:** `build_bom(components, *, options=None) -> cyclonedx.model.bom.Bom`
- **After:** `build_bom(components, *, options=None) -> BomWithMetadata`

**Why:** OWB-S144. The previous implementation stashed OWB metadata
(`_owb_options`, `_owb_non_allowed_count`) on the vendored
`cyclonedx.model.bom.Bom` instance via `# type: ignore[attr-defined]`.
That leaked abstraction (upgrading CycloneDX could break OWB) and
dominated the pyright basic-mode error count. The new
`BomWithMetadata` dataclass (in `sbom._bom_metadata`) holds
`(bom, options, non_allowed_count)` adjacent to the underlying Bom
without touching it.

**Consumer impact:** direct callers of `build_bom` must read the
underlying Bom via `wrapped.bom` explicitly. `serialize_bom` and
`count_non_allowed_licenses` already accept the wrapper; other code
paths that previously treated the return as a bare `Bom` (for access
to `.components`, `.metadata`, etc.) need `wrapped.bom.components`.
No public OWB CLI command changes — the wrapper is internal plumbing.

**How to migrate:**

```python
# Old
bom = build_bom(components)
for c in bom.components:        # AttributeError after upgrade
    ...

# New
wrapped = build_bom(components)
for c in wrapped.bom.components:
    ...
```

### Changed Default — `SecurityConfig.fail_closed`

- **New field, default `True`** (`SecurityConfig.fail_closed: bool = True`).
- **Behaviour change:** when a wrapped dependency-gate tool (pip-audit,
  guarddog, license audit, quarantine, skill-quarantine) raises an
  unexpected exception, the gate now returns `passed=False` with a
  `"errored: ..."` detail instead of the previous `passed=True,
  "skipped — ... error: ..."`. Tool-not-installed is unchanged (still
  `passed=True, "skipped"`).

**Why:** OWB-S142. The previous shape was indistinguishable from
tool-missing, so an attacker who could induce a tool crash got a free
pass through the gate. Fail-closed is the correct default for a
security control.

**Consumer impact:** CI pipelines that legitimately want skip-on-error
semantics (e.g. flaky networks) can set `security.fail_closed: false`
in their OWB config. The errored path then labels the detail
`"errored (fail_closed=false): ..."` and the gate logs a WARNING so
the event stays visible.

### Added — `SecurityConfig.http_max_bytes`

- **New field, default `1_048_576`** (1 MiB).
- Documents the size-cap knob read by `security.quarantine._fetch_pypi_json`
  and `security.suppression_monitor._query_osv`.

**Why:** OWB-S143. Defensive-in-depth against a compromised or spoofed
PyPI/OSV endpoint returning a multi-megabyte payload. See CHANGELOG.

### Added — `sbom._bom_metadata.BomWithMetadata`

New internal dataclass. Exported through `sbom.builder` for type
annotations on direct callers, but the module is named with a leading
underscore to signal internal intent.

### Removed

- `bom._owb_options` attribute on `cyclonedx.model.bom.Bom` instances
  (was monkey-patched via `# type: ignore[attr-defined]`; replaced by
  `BomWithMetadata.options`).
- `bom._owb_non_allowed_count` attribute (same — replaced by
  `BomWithMetadata.non_allowed_count`).

Both removals are effectively internal; no consumer was expected to
read these attributes, and new regression tests assert the wrapped
`Bom` carries neither attribute going forward.

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
