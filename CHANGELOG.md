# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed

- Dependency pre-install gate moved from ~400-token CLAUDE.md instruction block
  to a mechanical PreToolUse hook (`dependency-gate.py`). The hook checks PyPI
  license, 7-day quarantine, and first-party exemption before any install command
  (OWB-S124).
- `vault-policies.md` compressed from verbose descriptions (~540 tokens) to
  pointer-only format (~302 tokens) (OWB-S125).
- Security checklist trimmed to LLM-judgment items only; tooling-enforced items
  (gitleaks, semgrep, ruff) removed with attribution note (OWB-S128).
- Model reference updated from Opus 4.5 to Opus 4.6 in `performance.md`
  (OWB-S129).
- Dependency gate origin narratives in CLAUDE.md trimmed to one-line vault
  pointers (OWB-S130).

## [1.12.0] - 2026-04-12

### Added

- Research section with disposition tracking table added to `project-index.md`
  vault template (OWB-S080). New projects scaffolded by OWB will include a
  Research section for tracking tagged research note dispositions during sprint
  planning.

## [1.11.0] - 2026-04-11

### Changed

- **Secrets module replaced by himitsubako (OWB-S113).** The bespoke
  `open_workspace_builder.secrets` module (5 backends, 8 files) is replaced by
  a dependency on [himitsubako](https://github.com/originalrgsec/himitsubako)
  `>=0.4.0`. The old import path emits a `DeprecationWarning` and will be
  removed in v1.12.0. Backends are now: env, sops, keychain, bitwarden
  (via himitsubako). The 1Password and standalone age backends are removed;
  himitsubako uses SOPS+age as its primary encrypted backend.
- **Python version floor bumped to >=3.12.** himitsubako requires Python 3.12+.
  Python 3.10 reaches EOL October 2026.
- `SecretsConfig` fields updated: `age_identity`, `age_secrets_dir`, and
  `onepassword_vault` removed; `sops_secrets_file` added.
- Wizard secrets step presents himitsubako's four backends instead of the
  previous five (env, sops, keychain, bitwarden).

### Removed

- `ClaudeMdConfig` backward-compatibility alias (TD-001). Use
  `AgentConfigConfig` directly.
- 6 OWB-native backend files: `age_backend.py`, `env_backend.py`,
  `keyring_backend.py`, `bitwarden_backend.py`, `onepassword_backend.py`,
  `base.py`.
- `[age]` optional extra removed from `pyproject.toml`.

### Deprecated

- `from open_workspace_builder.secrets import ...` — import from `himitsubako`
  directly. Shim will be removed in v1.12.0.

## [1.10.0] - 2026-04-11

### Added

- **Slack release notifications (OWB-S119).** New workflow
  `.github/workflows/release-notify-slack.yml` posts a Block Kit message to
  `#owb-releases` on every `release: published` event. Includes pre-release
  `[PRE]` prefix, body truncation at 2,800 characters, and context links to
  the GitHub Release page, SBOM asset, and PyPI page. Failure-isolated from
  the main release pipeline. Uses `slackapi/slack-github-action@v3.0.1`
  (MIT, GREEN health score). Requires repo secret `SLACK_RELEASE_WEBHOOK`.
- Release Notifications section in `docs/contributing/release-process.md`
  covering webhook provisioning, rotation, multi-channel expansion, and
  trigger behavior.

### Fixed

- **SBOM fixture path resolution (OWB-S120).** `sbom/_example.py` no longer
  uses `Path(__file__).resolve().parents[3]` to find the repo root, which
  broke on installed wheels. Path resolution now uses
  `importlib.resources.files()` against package data bundled at
  `sbom/_data/`. The fixture workspace and committed example SBOM moved from
  `tests/fixtures/sbom-example/` and `examples/sbom/` into the package.
  7 new tests in `tests/sbom/test_example_resolver.py`.
- **Ghost-release errata (OWB-S121).** Added errata banners to
  `docs/releases/v1.6.0.md`, `v1.7.0.md`, and `v1.8.0.md` documenting that
  these versions were tagged but never shipped to PyPI. Filed DRN-074
  (no-backfill decision). See the v1.9.0 CHANGELOG entry for full context.

## [1.9.0] - 2026-04-11

### Release Notes

**v1.9.0 is a consolidation release.** Versions 1.6.0, 1.7.0, and 1.8.0 were
tagged in the repository and closed out in the vault between 2026-04-10 and
2026-04-11 but were **never actually published to PyPI** due to a silent
failure in the release workflow's `test` job (missing `[sbom]` extra caused
`ModuleNotFoundError: No module named 'cyclonedx'` at pytest collection
time, blocking the `publish` job). The failure went undetected because the
sprint-close checklist verified only that the tag was pushed, not that the
`publish` job succeeded.

The last version actually present on PyPI before v1.9.0 was **v1.5.0**
(shipped 2026-04-10). Users who ran `pip install open-workspace-builder`
between then and v1.9.0 have been running v1.5.0 and have not seen any of
the SBOM work from Sprints 20, 21, or 22. v1.9.0 ships all of that work
together, plus the release pipeline fix (OWB-S118, Sprint 23) that prevents
this class of silent publish failure from recurring, plus the
`cryptography` 46.0.7 CVE patch (OWB-SEC-003) that had been waiting on its
supply-chain quarantine window.

Detailed changelog entries for `[1.8.0]`, `[1.7.0]`, and `[1.6.0]` remain
below as the historical record of what each tag contained. The
user-facing consolidation of those changes appears in this v1.9.0 entry.

The discovery and no-backfill decision are documented in OWB-S121 (vault
errata) and a forthcoming DRN under the vault `decisions/` folder.

### Added

#### Release pipeline: GitHub Releases adoption (OWB-S118)

- **Canonical release distribution surface.** New `github_release` job in
  `.github/workflows/release.yml` runs after PyPI publish succeeds,
  creating a first-class GitHub Release for every `v*` tag push. The
  Release body is sourced from the `CHANGELOG.md` section matching the
  tag; the assets attached are the wheel, the sdist, and a CycloneDX 1.6
  SBOM of OWB's own Python dependency tree. Downstream consumers can now
  fetch signed release artifacts and audit OWB's supply chain without
  scraping PyPI metadata or cloning the repository. See
  [`docs/contributing/release-process.md`](docs/contributing/release-process.md)
  for the full contributor-facing guide.
- **PEP 440 pre-release detection.** The workflow detects canonical PEP 440
  pre-release versions (`1.9.0a1`, `1.9.0b2`, `1.9.0rc1`, `1.9.0.dev3`,
  `1.9.0.post1`) via regex and flags the resulting Release as a
  prerelease. The RC rehearsal procedure is documented alongside the
  release process. Pre-release tags still publish to PyPI as pre-release
  versions (PEP 440 compliant), visible only via `pip install --pre`.
- **`scripts/extract_changelog.py`**: Keep-a-Changelog section parser that
  extracts the body for a specific version header. Fails loud on missing
  or empty sections — a release cannot proceed with an empty or
  mismatched body.
- **`scripts/generate_sbom.py`**: project SBOM generator. Creates an
  isolated venv, installs the wheel into it, enumerates the installed
  distributions via `importlib.metadata`, and constructs a CycloneDX 1.6
  BOM with OWB as `metadata.component` (APPLICATION) and its transitive
  Python dependency closure in `components` (LIBRARY). Uses
  `cyclonedx-python-lib` directly — already an OWB dependency via the
  `[sbom]` extra, no new third-party tooling introduced. Venv bootstrap
  packages (`pip`, `setuptools`, `wheel`, `distribute`, `pkg_resources`)
  are filtered by canonical name so the SBOM describes OWB's declared
  closure rather than the Python install layer.
- **`docs/contributing/release-process.md`**: new contributor-facing guide
  covering prerequisites, tagging, RC rehearsal procedure, artifact
  inventory, manual fallback, historical tag policy, troubleshooting.
- **AD-17 (vault)**: architectural decision record for GitHub Releases
  adoption, filed in the OWB vault under
  `projects/Open Source/open-workspace-builder/adr.md`.

#### Release pipeline: test job replaced with smoke job (OWB-S118)

- **New `smoke` job in `.github/workflows/release.yml`**. Replaces the
  previous `test` job, which had been silently failing since Sprint 20
  due to two preexisting bugs exposed during the Sprint 23 RC rehearsal:
  - The `test` job installed `dist/*.whl` without the `[sbom]` extra, so
    `cyclonedx-python-lib` was missing, causing `tests/sbom/test_builder.py`
    to fail at pytest collection time with
    `ModuleNotFoundError: No module named 'cyclonedx'`.
  - Even with the extra installed, `tests/sbom/test_example_fixture.py`
    computes `_REPO_ROOT` via `Path(__file__).resolve().parents[3]`, which
    resolves to `/opt/hostedtoolcache/Python/3.12.13/` when OWB is imported
    from an installed wheel rather than the repo root. The example SBOM
    drift check then fails with "Missing committed example SBOM at ..."
    (filed as OWB-S120).
- The new `smoke` job installs the wheel into a clean environment with
  the `[sbom]` extra and verifies the CLI entry point responds to
  `--help` and `--version`. The full test suite is the responsibility of
  `ci.yml`, which runs `uv sync --all-extras && pytest` on every push to
  main across a Python 3.11/3.12/3.13 matrix. Running the full suite
  again in the release workflow was redundant and introduced
  source-tree-assumption bugs that the source-tree-native CI run cannot
  see.
- **Sprint-close skill Item 8a (user-level)**: the `sprint-close` skill
  at `~/.claude/skills/sprint-close/SKILL.md` now verifies that a
  GitHub Release object exists post-tag as part of the close checklist.
  This closes the gap that allowed the ghost-release chain to go
  undetected across three sprints.

#### SBOM foundation (OWB-S107a, originally v1.6.0)

- **`owb sbom generate <workspace>` command.** Produces a CycloneDX 1.6
  JSON Software Bill of Materials for every skill, agent, command, and
  MCP server in a workspace. Output writes to stdout by default;
  `--output PATH` writes to a file.
- **Scanner SBOM emission.** `owb scan <path> --emit-sbom PATH` produces
  both the scan report and an SBOM in a single pass.
- **Versioned content normalization (`norm1`).** New
  `open_workspace_builder.sbom.normalize` module implements the `norm1`
  algorithm — strip trailing whitespace, normalize line endings to LF,
  strip `updated:` YAML frontmatter field before hashing. Hashes are
  tagged `sha256-norm1:<hex>` so future rule changes stay
  backward-compatible. Hash stability is enforced by workflow-level AC
  tests: modifying whitespace or the `updated:` field produces no drift;
  modifying a skill body flips exactly one component hash.
- **`[sbom]` optional extra.** `cyclonedx-python-lib` promoted from
  transitive (via `pip-audit`) to direct dependency. Apache-2.0 (allowed),
  pinned `>=9.0,<11`.
- **Example SBOM fixture.** `examples/sbom/example.cdx.json` committed,
  with a deterministic regeneration path via
  `python -m open_workspace_builder.sbom._example`. CI drift check
  ensures the committed fixture stays in sync with regeneration.

#### SBOM enrichment (OWB-S107b, originally v1.7.0)

- **Provenance** under `owb:provenance:*` properties. Detection priority
  is explicit frontmatter `source:` → install record → git history via
  `git log --follow` → local fallback. Each entry carries a confidence
  score (`high`/`medium`/`low`). Git-history detection records the commit
  SHA and the canonical `https://` form of the origin remote when
  present (SSH URLs normalized).
- **Capabilities** under `owb:capability:*` properties. Declared tools
  (one property per tool, e.g. `owb:capability:tool:Read`), MCP server
  references, explicit `network:` declarations, MCP server transport
  type, exec command names, and env *keys*. Tool wildcards (`*`) raise a
  `owb:capability:warning` marker. **MCP env values are never
  recorded** — only keys, enforced by a dedicated test.
- **License detection** in the spec-native CycloneDX `licenses` field.
  Detection priority is frontmatter `license:` → sibling
  `LICENSE`/`LICENSE.md`/`COPYING` → parent-directory walk → workspace
  root `LICENSE` → `NOASSERTION`. SPDX identification uses
  distinctive-phrase fingerprinting (case- and whitespace-normalized).
  Recognized licenses: MIT, Apache-2.0, BSD-2-Clause, BSD-3-Clause, ISC,
  GPL-2.0, GPL-3.0, AGPL-3.0, LGPL-2.1, LGPL-3.0, MPL-2.0, Unlicense,
  0BSD.
- **`allowed_licenses.toml`** shipped with the package at
  `src/open_workspace_builder/data/allowed_licenses.toml`. Runtime
  authority for the SBOM license cross-reference.
- **CLI exit code 2 for license warnings.** `owb sbom generate` exits
  with code 2 when one or more components have a non-allowed or
  unrecognized custom license. Top-level metadata aggregate
  `owb:license:non-allowed-count` exposes the count without re-walking
  components.
- **Hash stability regression test** asserts that every S107a `bom-ref`
  and content hash remains byte-identical under S107b regeneration.

#### SBOM operational commands (OWB-S107c, originally v1.8.0)

- **`owb sbom diff <old> <new>`** — structural diff joined by `bom-ref`
  over content hash, license, capability set, and provenance. JSON by
  default; `--format text` for human-readable. Exit codes 0 (clean) /
  1 (error) / 2 (differences).
- **`owb sbom verify [--workspace PATH] [--against PATH]`** — regenerate
  the workspace SBOM and compare against `.owb/sbom.cdx.json` (or a
  custom canonical). The pre-commit / CI drift gate. Exit codes
  0 / 1 / 2.
- **`owb sbom show <sbom> [--component BOM-REF]`** — read-only inspector
  with a one-line-per-component summary by default and a full property
  dump when a single component is selected. Both `text` and `json`
  formats.
- **`owb sbom quarantine [--workspace PATH] [--days N] [--sbom PATH]`** —
  flag AI extensions added inside the last N days (default 7) using the
  `owb:provenance:added-at` field. Exit codes 0 / 1 / 2.
- **`owb sbom generate --format spdx`** — SPDX 2.3 JSON output via a
  hand-rolled emitter (no new dependency). CycloneDX 1.6 remains the
  canonical internal format.
- **`owb scan --skill-quarantine`** — opt-in scanner gate that wires the
  quarantine check into the existing scan pipeline. Default off.
- **Provenance `added_at` field** on every detected `Provenance` record.
  ISO 8601 first-add date sourced from
  `git log --diff-filter=A --follow` (high confidence) or file `mtime`
  (low confidence). Emitted as `owb:provenance:added-at` CycloneDX
  property. **Excluded from the normalized content hash by construction**
  — hash operates on file content, not metadata.
- **Documentation.** New concept page `docs/concepts/sbom.md` and
  how-to `docs/howto-sbom.md` with worked examples and pre-commit / CI
  recipes.

### Security

- **OWB-SEC-003: bump `cryptography` to 46.0.7** (CVE-2026-39892,
  Dependabot alert #16). Medium-severity buffer overflow in
  `Hash.update()` on non-contiguous buffers. In-context risk is low
  because OWB does not route user bytes into crypto APIs, but the patch
  is applied proactively. The supply-chain quarantine pin in `uv.toml`
  was advanced from 2026-04-02 to 2026-04-09 to allow the upgrade four
  days ahead of the natural 7-day window clear (2026-04-15). The
  override is package-owner authorized and recorded in the
  `uv.toml` header comment, the Sprint 23 session log, and this
  release manifest. Only `cryptography` was upgraded — every other
  package remains at its prior lock entry.

### Changed

- `owb sbom generate --format` now accepts `cyclonedx` or `spdx`.
- `Component` dataclass extended with three optional fields
  (`provenance`, `capabilities`, `license`) defaulting to empty so all
  v1.5.0 callers continue to work unchanged.
- `pyproject.toml` and `MANIFEST.in` extended to ship `data/*.toml`
  files in the package distribution.
- PRD: new UC-18 (AI Workspace SBOM Generation).
- ADR: new AD-17 (GitHub Releases distribution), plus the previously
  filed AD-17 (CycloneDX 1.6) and AD-18 (versioned normalization) from
  Sprint 20. Vault ADR numbering reconciled separately.

### Tests

- Total test count grew across the Sprint 20–23 work. v1.5.0 had 1563
  tests; v1.9.0 ships 1814+ (exact count pinned at sprint close).
- Workflow-level AC tests exercise the full SBOM lifecycle through the
  CLI per the integration-verification-policy.
- 40 new tests for the release pipeline helper scripts
  (`tests/test_extract_changelog.py`, `tests/test_generate_sbom.py`).
- SBOM module coverage 93% post-S107c.

### Known Limitations

- `cyclonedx-python-lib` emits a `UserWarning` during project SBOM
  generation because the BOM does not declare the root component's
  direct-vs-transitive dependency graph. Declaring the graph requires
  parsing the wheel's `Requires-Dist` metadata and doing a full
  topological walk; deferred as future enrichment, not a correctness
  issue.
- `src/open_workspace_builder/sbom/_example.py` still computes
  `_REPO_ROOT` via a source-tree assumption. Works when OWB is imported
  from the source tree, fails against an installed wheel. Worked around
  in the release pipeline via the `smoke` job. Fix tracked as OWB-S120.

## [1.8.0] - 2026-04-11

### Added
- **SBOM operational commands, SPDX 2.3, quarantine, docs (OWB-S107c).**
  Third and final slice of OWB-S107. Adds the operator-facing surface on
  top of the S107a/b SBOM substrate:
  - `owb sbom diff <old> <new>` — structural diff joined by `bom-ref` over
    content hash, license, capability set, and provenance source/commit.
    JSON output by default; `--format text` for human-readable. Exit codes
    0 (clean) / 1 (error) / 2 (differences).
  - `owb sbom verify [--workspace PATH] [--against PATH]` — regenerate the
    workspace SBOM and compare against `.owb/sbom.cdx.json` (or a custom
    canonical). The pre-commit / CI drift gate. Exit codes 0 / 1 / 2.
  - `owb sbom show <sbom> [--component BOM-REF]` — read-only inspector with
    a one-line-per-component summary by default and a full property dump
    when a single component is selected. Both `text` and `json` formats.
  - `owb sbom quarantine [--workspace PATH] [--days N] [--sbom PATH]` —
    flag AI extensions added inside the last N days (default 7) using the
    new `owb:provenance:added-at` field. Mirrors the Python package
    quarantine policy from S089. Exit codes 0 / 1 / 2.
  - `owb sbom generate --format spdx` — SPDX 2.3 JSON output via a
    hand-rolled emitter (no new dependency). CycloneDX 1.6 remains the
    canonical internal format; SPDX is a write-only secondary format for
    downstream tools that only consume SPDX.
  - `owb scan --skill-quarantine` — opt-in scanner gate that wires the
    quarantine check into the existing scan pipeline. Default off until a
    future deprecation cycle.
- **Provenance `added_at` field.** Every detected `Provenance` record now
  carries an ISO 8601 first-add date sourced from
  `git log --diff-filter=A --follow` (high confidence) or file `mtime`
  (low confidence). Emitted as the `owb:provenance:added-at` CycloneDX
  property. **Excluded from the normalized content hash by construction**:
  the hash function operates on file content, not metadata, so v1.6.0 and
  v1.7.0 component hashes remain byte-stable. The hash-stability regression
  test enforces this.
- **Documentation.** New concept page `docs/concepts/sbom.md` (CycloneDX
  rationale, normalization model, property namespaces, capability honesty
  caveat, SPDX as secondary, quarantine model). New how-to
  `docs/howto-sbom.md` with worked examples for `generate`, `show`, `diff`,
  `verify`, `quarantine`, `--format spdx`, plus pre-commit and GitHub
  Actions recipes. New cross-link from `docs/concepts/supply-chain-security.md`.
  mkdocs nav updated for both pages.

### Changed
- `owb sbom generate --format` now accepts `cyclonedx` or `spdx` (was
  CycloneDX-only with an "SPDX is deferred to S107c" disclaimer).
- The example fixture `examples/sbom/example.cdx.json` is regenerated to
  include the `owb:provenance:added-at` property on every component.
- `tests/sbom/test_cli.py::test_format_spdx_rejected_in_s107a` is replaced
  by `test_format_spdx_accepted_in_s107c` to reflect the new behavior.

## [1.7.0] - 2026-04-11

### Added
- **SBOM enrichment: provenance, capability, license (OWB-S107b).** Each
  component in `owb sbom generate` output is now decorated with three new
  enrichment surfaces:
  - **Provenance** under `owb:provenance:*` properties: detection priority
    is explicit frontmatter `source:` → install record (`.owb/install-records/skills.json`,
    reader-only in S107b) → git history via `git log --follow` → local
    fallback. Each entry carries a confidence score (`high`/`medium`/`low`).
    Git-history detection records the commit SHA and the canonical
    `https://` form of the origin remote when present (SSH URLs are
    normalized).
  - **Capabilities** under `owb:capability:*` properties: declared tools
    (one property per tool, e.g. `owb:capability:tool:Read`), MCP server
    references, explicit `network:` declarations, MCP server transport
    type, exec command names, and env *keys*. Tool wildcards (`*`) raise
    a `owb:capability:warning` marker. **MCP env values are never
    recorded** — only keys, enforced by a dedicated test that asserts
    no env value appears in any extracted output.
  - **License detection** in the spec-native CycloneDX `licenses` field:
    detection priority is frontmatter `license:` → sibling `LICENSE` /
    `LICENSE.md` / `COPYING` → parent-directory walk → workspace root
    `LICENSE` → `NOASSERTION`. SPDX identification uses distinctive-phrase
    fingerprinting (case- and whitespace-normalized), robust to copyright
    year and holder variation. Recognized licenses today: MIT, Apache-2.0,
    BSD-2-Clause, BSD-3-Clause, ISC, GPL-2.0, GPL-3.0, AGPL-3.0, LGPL-2.1,
    LGPL-3.0, MPL-2.0, Unlicense, 0BSD.
- **`allowed_licenses.toml` shipped with the package** at
  `src/open_workspace_builder/data/allowed_licenses.toml`. Runtime
  authority for the SBOM license cross-reference, machine-readable twin
  of the human-authored vault doc at `Obsidian/code/allowed-licenses.md`.
  Sync is currently manual; the unit tests verify the toml parses and
  contains expected SPDX IDs.
- **CLI exit code 2 for license warnings.** `owb sbom generate` now exits
  with code 2 when one or more components have a non-allowed (or
  unrecognized custom) license. Code 0 stays "clean," code 1 stays
  "hard error." A new top-level metadata aggregate
  `owb:license:non-allowed-count` exposes the count without re-walking
  components.
- **Hash stability regression test** (`tests/sbom/test_example_fixture.py`)
  asserts that every S107a `bom-ref` and content hash from v1.6.0 remains
  byte-identical under S107b regeneration. Any future change to the
  normalization algorithm or `bom-ref` derivation must bump `norm1` →
  `norm2` rather than break this test.

### Changed
- `Component` dataclass extended with three optional fields
  (`provenance`, `capabilities`, `license`) defaulting to empty so all
  S107a callers continue to work unchanged. The first seven fields
  participating in identity are unchanged.
- `examples/sbom/example.cdx.json` regenerated to reflect S107b enrichment;
  CI drift check (introduced in S107a) verifies the committed copy stays
  in sync with regeneration.
- `pyproject.toml` and `MANIFEST.in` extended to ship `data/*.toml` files
  in the package distribution.

### Tests
- 77 new tests across the S107b surface: 28 license, 25 capability,
  13 provenance, 1 hash-stability regression, 10 workflow-level AC tests
  (4 enrichment cases × invocation patterns). Total test count
  1646 → 1723. SBOM module coverage 92%.
- Workflow-level AC test (`tests/sbom/test_workflow_ac_s107b.py`)
  exercises the full `owb sbom generate` CLI on a four-case fixture
  (frontmatter source, git-history with origin remote, local fallback,
  GPL-3.0 sibling LICENSE) per integration-verification-policy §1.

### Deferred
- **OWB-SEC-003 (cryptography 46.0.7 patch)** was planned as Sprint 21
  filler but deferred due to a 7-day quarantine collision: 46.0.7
  published 2026-04-08, the supply-chain quarantine window does not
  clear until 2026-04-15, and Sprint 21 began 2026-04-11. SEC-003 will
  ship as a v1.7.1 patch on/after 2026-04-15 or roll into Sprint 22.
- S107c (`diff`/`verify`/`show` operational commands, SPDX 2.3 output,
  package quarantine SBOM consultation, concept page + howto) — Sprint
  22 anchor candidate.
- Proper CI sync check between vault `allowed-licenses.md` and
  `allowed_licenses.toml`. Currently manual; the existing toml-parse
  unit test catches the most common drift modes.

## [1.6.0] - 2026-04-11

### Added
- **SBOM foundation for AI workspace extensions (OWB-S107a):** New
  `owb sbom generate <workspace>` command produces a CycloneDX 1.6 JSON Software
  Bill of Materials for every skill, agent, command, and MCP server in a
  workspace. Output writes to stdout by default; `--output PATH` writes to a
  file. First slice of the parent S107 story, split into S107a/b/c per the
  8-point session budget policy from S117.
- **Scanner SBOM emission:** `owb scan <path> --emit-sbom PATH` produces both
  the scan report and an SBOM in a single pass.
- **Versioned content normalization (`norm1`):** New
  `open_workspace_builder.sbom.normalize` module implements the `norm1`
  algorithm — strip trailing whitespace, normalize line endings to LF, strip
  `updated:` YAML frontmatter field before hashing. Hashes are tagged
  `sha256-norm1:<hex>` so future rule changes stay backward-compatible. Hash
  stability is enforced by workflow-level AC tests: modifying whitespace or
  the `updated:` field produces no drift; modifying a skill body flips exactly
  one component hash.
- **`[sbom]` optional extra:** `cyclonedx-python-lib` promoted from transitive
  (via `pip-audit`) to direct dependency. Apache-2.0 (allowed), pinned
  `>=9.0,<11` to defer the 11.x major bump.
- **Example SBOM fixture:** `examples/sbom/example.cdx.json` committed, with
  a deterministic regeneration path via
  `python -m open_workspace_builder.sbom._example`. CI drift check ensures the
  committed fixture stays in sync with regeneration.

### Changed
- PRD: new UC-18 (AI Workspace SBOM Generation) documenting the new command
  flow and outcome.
- ADR: new AD-17 (CycloneDX 1.6 as primary SBOM format) and AD-18 (versioned
  normalization for SBOM content hashing) recording the architectural decisions.

### Deferred
- S107b (provenance + capability extraction + license detection), S107c
  (diff/verify/show commands, SPDX 2.3 output, quarantine integration, docs).
- Migration from `owb:evidence-path` property to spec-native
  `evidence.occurrences[].location` is blocked on `cyclonedx-python-lib` upgrade
  past the 9.x line and will be revisited in S107b/c.

### Filed during sprint
- OWB-SEC-003: bump `cryptography` 46.0.6 → 46.0.7 for CVE-2026-39892
  (Dependabot alert #16, medium-severity buffer overflow in `Hash.update()` on
  non-contiguous buffers). In-context risk is low because OWB does not route
  user bytes into crypto APIs. Queued for the next sprint.

## [1.5.0] - 2026-04-10

### Changed
- **Template consolidation (OWB-S084):** `research-spike.md` merged into `story.md`.
  Stories now support `deliverable: decision` mode with research spike sections as
  HTML comments. New `Integration Verification Plan` section added to the story
  template for system boundary verification.
- **Sprint-close skill enhanced (OWB-S116):** Three new checklist items — session
  budget check (8pt cap warning), integration verification sub-check (doctor/smoke
  test), and memory hygiene check (delineation policy enforcement). Fresh context
  reload documented. Commit-message hook added for release commit reminders.

### Removed
- `_templates/research-spike.md` — consolidated into `story.md`

## [1.4.0] - 2026-04-10

### Changed
- **Stage system capped at Phase 1 (OWB-S111):** `MAX_STAGE` reduced from 3 to 1.
  Phase 2/3 exit criteria methods removed. `owb stage promote` beyond Phase 1 now
  exits with code 1 and directs users to the ABOP Engineering Platform. Enforcement
  hook deployment gate lowered from stage 2 to stage 1 so hooks remain usable at
  the new ceiling.
- **Docs solo-only sweep (OWB-S112):** Remaining Phase 2 language in README and
  `docs/concepts/phases.md` rewritten to solo-only framing. "Four-phase maturity
  model" replaced with Phase 0-1 scope ceiling language.

### Removed
- `_check_stage_1_to_2()` and `_check_stage_2_to_3()` methods from `stage.py`
- Phase 2/3 config generation branches from `_check_exit_criteria()`
- Dead hook deployment block in CLI (unreachable with `MAX_STAGE=1`)

## [1.3.0] - 2026-04-09

### Security
- **SEC-002:** Bumped litellm upper bound from `<=1.82.6` to `<=1.83.0`. Closes
  CVE-2026-35030 (critical, OIDC cache key collision auth bypass), CVE-2026-35029
  (high, proxy config privilege escalation), and pass-the-hash auth bypass (high).
  Supply-chain triage: Sigstore OIDC attestation confirmed, CI hardening verified
  (cosign signing, pinned Codecov SHA, OpenSSF Scorecard), 9-day quarantine passed.
- **SEC-001:** Formally closed sast.py auto-config expansion fix (shipped in v1.2.1,
  commit `c7b01f7`). Semgrep `--config auto` expanded to explicit `p/python` and
  `p/owasp-top-ten` rulesets with `--metrics=off`.

### Added
- **Concept pages:** Three new documentation pages — IDP for AI Coding, Policy as Code,
  Supply Chain Security — framing OWB's three value pillars for the solo developer audience.
- **Glossary:** New reference page defining IDP, Policy as Code, SSCA, SBOM, Golden Path,
  Drift, Pattern Registry, Trust Tier, and Quarantine.
- Cross-links from Security Model and Configuration pages to the new concept pages.

### Changed
- **DRN-066 docs sweep:** Stripped multi-user/team language from published documentation.
  Phase 2/3 in `phases.md` collapsed to out-of-scope section. PRD personas 3-5 and use
  cases UC-11 through UC-15 marked historical. Non-Goals updated with explicit multi-user
  exclusion. ADR AD-6 annotated as historical context.
- **README rewritten:** New one-liner ("open-source IDP for AI coding assistants"), three-pillar
  structure (workspace platform, policy-as-code, supply chain security), explicit scope
  boundary ("designed for individual developers, not teams"). Test badge updated to 1561.
- **Landing page updated:** Hero tagline reframed. Phase 2 teaser replaced with three-pillar
  overview linking to new concept pages.
- MkDocs nav updated with 4 new pages (3 concepts + glossary).

### Fixed
- `test_quarantine.py`: Removed `mix_stderr=False` from CliRunner (Click 8.2 incompatibility).

## [1.2.1] - 2026-04-03

### Changed
- Development process (SDLC) policy updated with sprint completion trigger, research
  review gate (§5a), PII/secrets audit gate (§5b), project status lifecycle taxonomy,
  and security drift baseline setup requirements
- Product development workflow (PLC) updated with security drift baseline paragraph
  in Phase 4 setup and story template `deliverable: decision` documentation

## [1.2.0] - 2026-04-02

### Added
- Pre-commit hook framework with gitleaks and ruff hooks (OWB-S088):
  - `owb init` generates `.pre-commit-config.yaml` at workspace root
  - `owb security hooks install` and `owb security hooks status` commands
  - `owb security scan --all` enables all scanners at once
  - `pre-commit` added as `[hooks]` optional dependency
- Package quarantine enforcement with 7-day window (OWB-S089):
  - `owb init` generates `uv.toml` with `exclude-newer` set to 7 days ago
  - `owb audit pins` checks for safe pin advancement candidates via PyPI
  - `--auto-advance` and `--bypass` with JSONL audit trail
  - OWB's own `uv.toml` enforces quarantine at `2026-03-25`
- Configurable secrets scanner with gitleaks/ggshield backends (OWB-S086):
  - `owb security secrets` scans paths for hardcoded credentials
  - Gitleaks as zero-config default, ggshield as opt-in with API key
  - `--secrets` flag on `owb security scan`
- Programmatic pre-install SCA gate with 5-check battery (OWB-S090):
  - `owb audit gate <package>` runs pip-audit, GuardDog, OSS health, license,
    and quarantine checks with consolidated pass/fail
  - `--all` mode checks all direct dependencies from pyproject.toml
  - Gate failures recorded to reputation ledger
- Trivy integration pinned to safe v0.69.3 (OWB-S091):
  - `owb security trivy` scans for multi-ecosystem vulnerabilities
  - Version safety enforcement blocks compromised versions 0.69.4-0.69.6
  - `--trivy` flag on `owb security scan`
- Baseline metrics CLI command (OWB-S049):
  - `owb metrics baseline` collects source LOC, test LOC, test count, commits,
    date range, and per-module breakdown
  - `--tag-range`, `--json`, `--output-dir` options
- 144 new tests (1405 → 1549)

### Changed
- SCA and SAST scanning enabled by default in SecurityConfig (OWB-S092):
  - `sca_enabled` and `sast_enabled` now default to `True`
  - Reputation ledger wired into SourceUpdater (blocks above threshold)
  - Scanner records FlagEvents for malicious verdicts when source is known
- Moved `content/` and `vendor/` inside `src/open_workspace_builder/` for pip
  distribution (OWB-S094)
- `_find_content_root()` resolves via `__file__` instead of walking to repo root
- `dependency-security.md` updated to cover Python, npm, Rust, Go with quarantine
- PLC Phase 5 QA and sprint completion checklist include supply chain verification
- `vault-policies.md` references `supply-chain-protection.md` (OWB-S093)

### Fixed
- Dry-run now reports `[skip]` for existing files instead of `[write]` (OWB-S062)

## [1.1.0] - 2026-03-29

### Added
- Directive drift detection (`owb security drift`) for workspace config files (OWB-S082):
  - SHA-256 baseline comparison for CLAUDE.md, agents, rules, and commands
  - `--update-baseline` creates/updates the drift baseline
  - `--json` flag for machine-readable output
  - `--files <glob>` restricts check to matching paths
  - Exit codes: 0 (clean), 1 (drift detected), 2 (no baseline)
  - Closes Vector 8 gap from AWS Bedrock attack vector research
- First-party ECC trust manifest for migrate operations (OWB-S061):
  - `security/trust.py` computes SHA-256 checksums of vendor/ecc/ files
  - Migrator skips scanning for unmodified first-party content
  - Modified first-party files still go through normal security scanning
- Registry `min_owb_version` gate and unknown field warnings (OWB-S083):
  - Registry items can declare `min_owb_version` in metadata envelope
  - Items requiring a newer OWB version are skipped with a warning
  - Unknown fields produce warnings but don't block loading (graceful degradation)
- 50 new tests (1356 → 1405)

### Fixed
- `owb init` no longer overwrites existing vault scaffold files (OWB-S060):
  - `_bootstrap.md`, `_index.md`, status files, templates, and policies are
    preserved if they already exist
  - Dry-run output shows `[skip]` for existing files
- `owb init` detects when target is an existing vault directory (OWB-S063):
  - Checks for vault markers (`_bootstrap.md`, `_templates/`) before building
  - Raises clear error instead of creating nested `Obsidian/` scaffold

## [1.0.0] - 2026-03-29

### Added
- Bootstrap stage tracking system (OWB-S079):
  - `StageConfig` frozen dataclass with four PRD stages (0: Cold Start, 1: Interactive
    Operation, 2: Build Farm, 3: Director Model)
  - `StageEvaluator` with automated exit criteria checks for Stage 0 → 1 (structural
    files, context populated, project scaffolded) and manual verification gates for
    stages 1→2 and 2→3
  - `owb stage status` command — shows current stage and exit criteria pass/fail
  - `owb stage promote` command — verifies criteria and advances stage
  - Wizard `_step_stage_selection()` detects starting stage from existing vaults
  - Builder writes `vault-meta.json` with stage, version, and builder name
- Hook-based policy enforcement for Phase 2 workspaces (OWB-S067):
  - `EnforcementConfig` frozen dataclass (`hooks_enabled` flag)
  - Policy manifest generator scans `content/policies/` and writes
    `~/.owb/policy-manifest.yaml` with file paths and one-line summaries
  - `policy-reminder.sh` hook script deployed to `.owb/hooks/`, registered in
    `.claude/settings.json` as a `UserPromptSubmit` hook
  - Phase-gated: only deploys when stage >= 2 and `--enable-hooks` passed to
    `owb stage promote`
  - `remove_hook_registration()` removes hook entry while preserving script files
- 73 new tests (1283 → 1356)

### Fixed
- `_with_resolved_paths` now preserves `tokens` and `stage` config fields
  (previously silently dropped `tokens` on path resolution)
- stealth-004 regex alternation precedence bug in security scanner patterns (OWB-S081)

## [0.8.2] - 2026-03-29

### Fixed
- Security scanner false-positives blocking ECC self-update on major version jumps (#1):
  - Only "malicious" (critical-flag) verdicts now block files; "flagged" (warning-only)
    verdicts are accepted with a printed warning instead of being silently blocked
  - Reputation ledger records use actual scan severity and disposition instead of
    hardcoding all blocked files as `confirmed_malicious`/`critical`
  - Ledger deduplicates by (source, file_path) — repeated scans of the same file
    update the existing entry instead of inflating the threshold count
  - Threshold check counts distinct files, not accumulated repeat entries
  - 7 high-false-positive patterns tuned to reduce false positives on legitimate
    agent definition content: inject-004, mcp-003, stealth-001, selfmod-002,
    path-005 (negative lookaheads and tighter anchors)
  - 2 patterns downgraded from warning to info: priv-003, mcp-001
  - `--accept-all` now works correctly for first-party ECC content — previously
    18 files were blocked with no way to override

### Added
- Trusted upstream URL allowlist (`SecurityConfig.trusted_upstream_urls`): when the
  ECC upstream URL matches a trusted source, Layer 2 pattern scanning is skipped
  during updates (Layer 1 structural checks still run)
- `trusted_source_exempt` field in update log entries — audit trail when Layer 2 is bypassed
- `files_warned` field in update log entries for flagged-but-accepted files
- `UpdateResult.warnings` field for flagged-but-accepted files
- CLI output now shows warned file count alongside accepted/rejected/blocked
- 22 new tests (1253 → 1275):
  - 5 ledger deduplication tests
  - 3 severity differentiation tests
  - 4 trusted-source exemption tests
  - 11 false-positive regression tests (paired positive/negative for each tuned pattern)

## [0.8.0] - 2026-03-28

### Added
- Token tracking Level C — automation and forecasting (OWB-S076-C):
  - `owb metrics record` command: append session costs to local JSONL ledger with `--story` tagging
  - `owb metrics sync` command: record + optional Google Sheets export for sprint-close hooks
  - `owb metrics forecast` command: monthly cost projection from ledger data (linear extrapolation)
  - `owb metrics budget-check` command: month-to-date threshold check with exit code 2 for hook integration
  - `owb metrics by-story` command: cost breakdown grouped by story ID tag
  - `LedgerEntry` frozen dataclass for session cost records
  - `TokensConfig` added to config system (ledger_path, budget_threshold, auto_record)
  - File locking on ledger writes for concurrent hook safety
  - Date validation at function boundaries
- Phase model documentation page (`docs/concepts/phases.md`) explaining Phases 0-3 (OWB-S080)
- CLI reference expanded from 6 to 15 documented commands (OWB-S080)
- ADR entries for xlsxwriter (AD-15) and Google Sheets OAuth (AD-16) (OWB-S080)
- Token tracking feature card on landing page and README (OWB-S080)
- Phase 2 preview section on landing page and README (OWB-S080)
- Optional dependency groups documented in configuration guide (OWB-S080)
- SDR sprint plan entries through Sprint 13 (OWB-S080)
- 5 vault research notes from model hosting research spike (OWB-S077):
  - US-based providers: Together AI (primary), Fireworks AI (secondary)
  - Models: Qwen 3.5 27B recommended (SWE-bench 72.4, 17 GB Q4)
  - Local frameworks: Ollama now, MLX/vllm-mlx for 96+ GB hardware
  - 7-scenario cost model: Max plan subsidy makes hybrid uneconomical for single user
  - Architecture decision tree with trigger events for hybrid adoption
- 40 new tests (1213 → 1253)

### Fixed
- Age backend pyrage identity generation now writes public key comment line matching age-keygen format

### Changed
- Security scanner pattern count corrected in docs (42 → 58 patterns across 12 categories)
- README test badge updated (713 → 1253)

## [0.7.0] - 2026-03-28

### Added
- Token consumption tracking CLI (OWB-S075):
  - `owb metrics tokens` command: parse Claude Code JSONL sessions, calculate API-equivalent costs
  - Per-project, per-model, per-day breakdowns with date filtering and project filtering
  - Cache efficiency analysis (hit ratio, cost reduction percentage)
  - Pricing registry with hardcoded Anthropic rates and YAML override support
  - JSON output mode for machine-readable reports
  - Google Sheets export via `owb metrics export --format gsheets` (OAuth 2.0 flow)
  - Excel export via `owb metrics export --format xlsx` (xlsxwriter, replaces openpyxl)
  - `owb auth google-store` and `owb auth google` commands for Sheets OAuth setup
  - New optional dependency groups: `[sheets]` (google-api-python-client, google-auth-oauthlib), `[xlsx]` (xlsxwriter)
- Token analysis skill with workflow integration (OWB-S076):
  - `content/skills/token-analysis/SKILL.md` with AgentSkills spec compliance
  - Sprint close workflow: cost section in retro, tracking sheet update
  - Sprint planning workflow: trailing cost trend, cost-per-story estimate
  - Monthly review workflow: full breakdown with trend analysis
  - Sprint-complete Item 5 updated with token consumption sub-item (5a)
  - Sprint-plan Step 8 added for cost estimation
  - token-analysis registered in default skills install list
- 82 new tests (1131 → 1213)

### Changed
- openpyxl dependency replaced by xlsxwriter (openpyxl scored RED on OSS health check: bus factor 1, no funding, 21-month release gap; xlsxwriter scored GREEN: BSD-2-Clause, 70M monthly downloads, 13 years mature)

## [0.6.0] - 2026-03-27

### Added
- 16 new security scanner patterns across 3 new categories (OWB-S071):
  - Jailbreak preambles (6 patterns): DAN mode, developer mode, unrestricted mode, safety bypass
  - Markdown/HTML exfiltration (5 patterns): tracking pixels, iframes, data URIs, HTML comment exploits
  - MCP/tool manipulation (5 patterns): protocol keywords, tool invocation, connected service access, output redirection
  - Tiered severity: service data access and output redirection are critical; documentation-overlapping patterns are warning
- Unicode tag character detection (U+E0001–E007F) at critical severity in structural scanner
- Variation selector detection (U+FE00–FE0F, U+E0100–E01EF) at warning severity
- Layer 3 semantic prompt updated with MCP/tool manipulation threat category
- Multi-file correlation mode via `owb security scan <dir> --correlate` for cross-file attack detection
- Skill-creator fork in content store with AgentSkills spec compliance (CSK-S001):
  - Core skill creation workflow retained from upstream, plugin-specific content stripped
  - Spec compliance section: name constraints, description limits, metadata/license fields
  - `owb validate` integrated into iteration loop
- 85 new tests (1046 → 1131)

### Fixed
- Registry pattern category names now normalize hyphens to underscores, matching YAML source

See [release manifest](docs/releases/v0.6.0.md) for full details.

## [0.5.1] - 2026-03-26

### Fixed
- Configuration errors now fail loudly instead of silently returning defaults (OWB-S073):
  - `load_config()` raises on missing explicit config path and invalid YAML
  - `_find_content_root()` raises when no content directory found
  - `WorkspaceBuilder.build()` validates content_root before filesystem writes
  - Secrets backends distinguish misconfiguration from missing keys

### Changed
- Factory and builder tests use real constructor signatures alongside mocks (OWB-S074)

### Added
- CLI contract tests (29 tests) verifying all subcommand exit codes and error messages
- Pipeline smoke tests (9 tests) for end-to-end build, evaluate, and audit workflows
- Updated sprint-complete skill with vault audit as numbered gate item

## [0.5.0] - 2026-03-25

### Added
- Inline policy enforcement rules deployed to workspace rules directory (OWB-S066):
  - Replaced pointer-style vault-policies.md with compact enforceable checklist
  - Conditional policy compliance preamble in generated agent config
  - Privacy scrubbing enforced via blocklist test
  - 20 new tests across test_policy_deployment.py and test_agent_config.py
- License audit command checking deps against allowed-licenses policy (OWB-S068):
  - `owb audit licenses` CLI command with `--policy`, `--format json|text`, `--output`
  - Runtime parsing of allowed-licenses.md into allow/conditional/deny categories
  - Case-insensitive license matching with common alias support
  - `--licenses` flag on `owb audit deps` for combined audit
  - Exit codes: 0 (all pass), 1 (fail/unknown), 2 (conditional only)
  - 32 new tests in tests/security/test_license_audit.py
- Agent Skills spec validation with CLI and evaluator integration (OWB-S051):
  - `owb validate <path>` CLI command for SKILL.md validation
  - Spec validator checking frontmatter, structure, and optional subdirectories
  - Evaluator integration for automated skill quality assessment
  - 508 tests in tests/evaluator/test_spec_validator.py
- Bitwarden and 1Password secrets backends (OWB-S052):
  - `bitwarden_backend.py` wrapping Bitwarden CLI (`bw`)
  - `onepassword_backend.py` wrapping 1Password CLI (`op`)
  - Wizard integration with availability detection and graceful fallback
  - 365 new tests across test_secrets.py and test_wizard_secrets.py
- MCP server exposing security scan, dep audit, and license audit tools (OWB-S065):
  - `owb mcp serve` CLI command for Model Context Protocol server
  - Three tool endpoints: security_scan, dep_audit, license_audit
  - 509 tests in tests/test_mcp_server.py
- Sprint-complete, retro, write-story skills (CSK-S003, S004, S005):
  - Sprint completion checklist orchestration skill
  - Retrospective scaffolding skill with sequential ID management
  - Story writer skill with workflow-level acceptance criteria
- Enhanced tdd-guide agent for Claude Code CLI parity (CSK-S006)
- Updated oss-health-check skill with GitHub API integration (CSK-S002)
- Sprint planning orchestration skill for open and close workflows (CSK-S007)

#### Project
- PRD Bootstrap Stages framework (Stage 0–3) with 5 new use cases (UC-11–15) and 2 new personas (Persona 4–5)
- MkDocs Material documentation site with GitHub Pages deployment
- Research-spike vault template (`content/templates/research-spike.md`)
- Allowed-licenses policy: CLI tool invocation exemption for copyleft tools (Semgrep LGPL-2.1)

### Changed
- Genericized Claude-specific remnants in OWB core (TD-001):
  - Renamed `claude-md.template.md` to `agent-config.template.md`
  - Updated all docstrings and comments to generic language
  - Broadened security patterns to match both CLAUDE.md and WORKSPACE.md
  - Wizard model prompt no longer defaults to Anthropic
  - `generic.yaml` marketplace uses `.ai` and `Context` defaults
  - Added deprecation note to `ClaudeMdConfig` alias (removal target: v0.6.0)
- `vault-policies` added to default ECC common rules deployment list

## [0.4.0] - 2026-03-25

### Added
- Cross-project policy deployment during vault build (OWB-S064):
  - VaultBuilder deploys content/policies/*.md to Obsidian/code/ during init
  - Migrator automatically detects missing/outdated policies via reference diff
  - Graceful skip when content/policies/ is missing or empty
  - 8 new tests in test_policy_deployment.py
- Pluggable secrets backend with `SecretsBackend` protocol and three implementations (OWB-S050):
  - OS keyring (macOS Keychain, GNOME Keyring, Windows Credential Manager) via `keyring` package
  - Age encryption with pyrage/CLI fallback and automatic key generation
  - Environment variable fallback (backward compatible, zero config)
- `owb auth` CLI command group: `store-key`, `get-key`, `status`, `backends`
- Runtime API key resolution with four-step fallback: CLI flag → secrets backend → env var → error
- `SecretsConfig` section in config overlay (`secrets.backend`, `secrets.age_identity`, etc.)
- Wizard secrets backend selection step with availability checking and graceful fallbacks
- Wizard API key storage now routes through the configured secrets backend
- `keyring`, `age`, and `secrets` optional dependency groups in pyproject.toml
- 88 new tests (625 → 713)
- Dependency supply chain scanning with two-layer architecture (OWB-S053):
  - Layer A: pip-audit Python API wrapper for known vulnerability scanning against OSV database
  - Layer B: GuardDog subprocess wrapper (`uvx guarddog`) for heuristic malware detection
- `owb audit deps` CLI command with `--deep`, `--fix`, `--format json|text`, `--output FILE` options
- `owb audit package <name>` CLI command for pre-addition single-package vetting with `--version` option
- Bundled suppressions YAML for acknowledged GuardDog false positives
- Makefile with `check-deps`, `audit-deps`, `audit-deps-deep` targets
- GitHub Actions CI workflow: pip-audit on every push, GuardDog on pyproject.toml changes
- `audit` optional dependency group in pyproject.toml
- 42 new tests (713 → 755)

- Context file lifecycle management:
  - `ContextDeployer` detects existing files and skips instead of overwriting
  - `owb context migrate` command for interactive reformatting against current templates
  - `owb context status` command reports filled/stub/missing state per file
  - Workspace config template includes "First Session Tasks" for assistant-guided fill
  - Wizard informational notice about context file stubs
- 16 new tests for context lifecycle (755 → 771)
- Pre-install SCA gate ECC rule (`dependency-security.md`) — instructs Claude Code to run `owb audit package` before any pip/uv install (OWB-S055)
- Semgrep SAST integration (OWB-S056):
  - `security/sast.py` module wrapping Semgrep CLI with JSON output parsing
  - `owb security sast` CLI command with `--config`, `--sarif`, `--format` options
  - `sast` optional dependency group in pyproject.toml
  - GitHub Actions SAST CI job, Makefile `sast` and `sast-json` targets
  - `sast-scanning.md` ECC rule for evaluated component scanning
- SCA and SAST wired into evaluator and security scan (OWB-S057):
  - `--sca` and `--sast` flags on `owb security scan` for combined reporting
  - Dependency discovery from requirements.txt, pyproject.toml, and import statements
  - `SecurityConfig.sca_enabled` and `sast_enabled` fields for config-driven activation
  - Trust tier scoring: critical SCA findings or SAST errors block T0, force manual review
- Automated CVE suppression monitoring (OWB-S059):
  - Suppression registry (`security/data/suppressions.yaml`) with CVE-2026-4539 entry
  - `owb audit check-suppressions` CLI command querying OSV API for fix availability
  - Weekly CI job (`suppression-monitor.yml`) opens GitHub issues when fixes land
  - `suppressions_schema.py` dataclass and YAML loader with validation
- 57 new tests for S055-S059 (771 → 828)

### Changed
- `VaultConfig.parent_dir` default changed from `"Context"` to `""` — vault deploys directly under workspace root instead of an intermediate folder
- pyyaml promoted from optional to core dependency — evaluator and security modules import it unconditionally

### Fixed
- CI: pip-audit `--skip-editable` for local package, `--ignore-vuln CVE-2026-4539` for pygments ReDoS (no upstream fix)
- CI: removed 3 unused imports caught by ruff lint on Python 3.13 matrix
- Stale `Claude Context/` path references in workspace config template and SKILL.md

## [0.3.0] - 2026-03-24

### Added
- Full skill evaluation pipeline: classify, generate tests, execute, score, judge, decide (S022-S024)
- Three evaluation modes: new skill (UC-1), update existing (UC-2), overlapping capability (UC-3) (S024)
- Evaluator scorer with per-dimension and weighted composite scoring via ModelBackend judge operation (S022)
- Quality judge with pairwise comparison and prompt injection hardening via system/user separation and XML delimiters (S023)
- Evaluation manager orchestrator chaining classify → generate → execute → score → judge → decide (S024)
- Test suite generator and persistence layer extracted from CWB, adapted to OWB's LiteLLM ModelBackend (S024)
- Skill type classifier with 10 skill types and configurable weight vectors (S028)
- Organizational layer classifier (L0-L3) with few-shot examples from YAML and confidence-gated manual review (S028)
- Trust tier assignment from registry-loaded policies with data-driven tier transitions (T0/T1/T2) (S029)
- Multi-source content discovery with per-source glob patterns, exclude rules, and SourcesConfig (S035)
- Repo-level security audit with pass/warn/block verdicts for hooks dirs, setup scripts, event triggers (S036)
- `owb update <source>` command replacing hardcoded ECC update path with config-driven multi-source pipeline (S037)
- SourcesConfig in config.py for named upstream sources with repo URL, pin, and discovery rules (S035)
- 251 new tests (374 → 625)

### Changed
- `owb ecc update` preserved as backward-compatible alias for `owb update ecc` (S037)

## [0.2.0] - 2026-03-23

### Added
- Config-driven architecture with three-layer overlay system (defaults, user file, CLI flags) (S040)
- LiteLLM-backed ModelBackend for model-agnostic provider routing — works with Anthropic, OpenAI, Ollama, and any LiteLLM-supported provider (S041)
- Extensible registry system for security patterns, trust policies, and marketplace formats with metadata envelopes and overlay support (S042)
- Interactive setup wizard (`owb init`) with 7-step configuration: model provider, API keys, vault tiers, marketplace format, security patterns, trust policies (S043)
- Vault config generation from existing vaults (`owb init --from-vault <path>`) (S043)
- `--no-wizard` flag to skip interactive setup and use defaults (S043)
- VaultConfig.assistant_name for configurable generated content (S044)
- AgentConfigConfig with configurable directory and filename (defaults: `.ai/WORKSPACE.md`) (S044)
- EccConfig.enabled flag (default: false) and configurable target_dir (S044)
- PathsConfig with runtime resolution from CLI name
- CLI name-aware config resolution (`owb` uses `~/.owb/`, `cwb` uses `~/.cwb/`)
- ModelsConfig with per-operation model strings for classify, generate, judge, security_scan
- SecurityConfig, TrustConfig, MarketplaceConfig as first-class config sections
- 42 security patterns split into 9 registry files with metadata envelopes
- Trust tier policy file (T0/T1/T2) in registry format
- Marketplace format configs (generic, anthropic, openai) in registry format
- `config.example.yaml` documenting full schema
- 121 new tests (253 to 374)

### Changed
- VaultConfig.parent_dir default changed from "Claude Context" to "Context" (S044)
- ECC installation disabled by default (enable via config) (S044)
- Agent config deploys to `.ai/WORKSPACE.md` by default (configurable) (S044)
- Security scanner accepts SecurityConfig and Registry for pattern loading
- Semantic analysis uses ModelBackend instead of direct anthropic SDK (S041)
- Scanner accepts ModelBackend instead of api_key/model parameters (S041)
- All Claude-specific references in generated content replaced with configurable assistant_name (S044)

### Removed
- Direct `anthropic` SDK dependency (replaced by LiteLLM)
- Hardcoded Claude-specific paths and content in engine modules

## [0.1.0] - 2026-03-23

### Added
- CLI entry point (`owb`) with Click-based commands: init, diff, migrate, ecc update/status, security scan
- Config module with defaults-first strategy and optional YAML overlay
- Build engine: vault generator, ECC installer, skills installer, context deployer
- Three-layer security scanner: structural validation, pattern matching, semantic analysis
- Reputation ledger with threshold-based drop recommendations
- Workspace diff engine and interactive migration
- ECC upstream update workflow with fetch, diff, scan, accept/reject
- 253 tests

[Unreleased]: https://github.com/originalrgsec/open-workspace-builder/compare/v0.5.0...HEAD
[0.5.0]: https://github.com/originalrgsec/open-workspace-builder/compare/v0.4.0...v0.5.0
[0.4.0]: https://github.com/originalrgsec/open-workspace-builder/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/originalrgsec/open-workspace-builder/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/originalrgsec/open-workspace-builder/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/originalrgsec/open-workspace-builder/releases/tag/v0.1.0
