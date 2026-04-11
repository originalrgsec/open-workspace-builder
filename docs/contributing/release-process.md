# Release Process

This page documents the end-to-end process for cutting an OWB release. It is the contributor-facing complement to [AD-17](../adr.md#ad-17-github-releases-as-canonical-release-distribution-surface-sprint-23), which captures the architectural decision behind the release pipeline.

## Overview

OWB releases ship through four stages on every `v*` tag push:

1. **Build** — construct the wheel and sdist with `pyproject-build`.
2. **Test** — install the wheel into a clean environment and run the full test suite.
3. **Publish** — upload to PyPI via trusted publishing (`pypa/gh-action-pypi-publish@release/v1`, no API tokens).
4. **GitHub Release** — create a canonical Release object on GitHub with the wheel, sdist, and project SBOM attached as assets. Body sourced from the `CHANGELOG.md` section matching the tag.

PyPI is the source of truth. If publish fails, no GitHub Release is created. If publish succeeds but the Release job fails, the Release can be created manually via `gh release create` — PyPI state is not affected.

## Prerequisites for a clean release

Before pushing a release tag, confirm:

- [ ] `CHANGELOG.md` has a section header `## [X.Y.Z] - YYYY-MM-DD` matching the tag (without the leading `v`).
- [ ] The section body is non-empty. The release workflow's CHANGELOG extraction step fails loud on empty sections.
- [ ] `pyproject.toml` `version` field matches `X.Y.Z`.
- [ ] All sprint-close gates have passed (see the `sprint-close` skill or `code/development-process.md` §1–8).
- [ ] The release PR has merged to `main`.

## Tagging the release

Tag the release from `main` after the PR merges:

```bash
git checkout main
git pull
git tag v1.9.0
git push origin v1.9.0
```

Do not tag before the merge. Do not force-push or move tags after the release workflow has started — tag moves after PyPI publish can leave the two distribution surfaces out of sync.

## Pre-release tags (RC rehearsal)

Release workflow changes cannot be validated in isolation — the workflow only runs on a real tag push. The sanctioned way to exercise a workflow change without burning a real version number is a release candidate tag against a scratch branch:

```bash
git checkout -b sprint-23-release-rehearsal
# make workflow changes
git commit -am "chore: release workflow rehearsal"
git push origin sprint-23-release-rehearsal

# add a temporary CHANGELOG section for the RC
# ## [1.9.0-rc.1] - 2026-04-12
# ### Rehearsal
# - Validating AD-17 GitHub Release workflow.

git commit -am "chore: rc.1 CHANGELOG stub"
git tag v1.9.0-rc.1
git push origin v1.9.0-rc.1
```

Tags matching `v*-rc.*`, `v*-alpha.*`, and `v*-beta.*` produce a prerelease-flagged GitHub Release. They still publish to PyPI as pre-release versions (PEP 440) and are visible to users who opt into pre-releases. Prefer separate pre-release PyPI project names if you want to avoid any PyPI surface for rehearsal — or accept that RC tags are a real pre-release.

After validation:

```bash
gh release delete v1.9.0-rc.1 --yes
git push origin :refs/tags/v1.9.0-rc.1
git branch -D sprint-23-release-rehearsal
# revert the temporary CHANGELOG stub before merging the real release
```

RC tags and their Release objects are not part of canonical release history and should be deleted after the rehearsal. The sprint-close skill reminds the operator to clean them up.

## What the workflow produces

Every canonical release produces the following artifacts:

| Artifact | Location | Purpose |
|---|---|---|
| Wheel (`*.whl`) | PyPI + GitHub Release assets | Installable Python distribution |
| Source distribution (`*.tar.gz`) | PyPI + GitHub Release assets | Buildable source archive |
| Project SBOM (`*.cdx.json`) | GitHub Release assets | CycloneDX 1.6 inventory of OWB's own Python dependency tree, generated via `scripts/generate_sbom.py` against the wheel in an isolated venv |
| Release body | GitHub Release description | CHANGELOG section for the tag, extracted verbatim via `scripts/extract_changelog.py` |

The project SBOM describes OWB's own declared and transitive Python dependencies. It is **not** the same as `owb sbom generate`, which produces an SBOM of a user workspace's AI extensions (skills, MCP servers, agents). The two SBOMs answer different questions:

- **Project SBOM** (this workflow): "what does the OWB release I just downloaded from PyPI depend on?"
- **Workspace SBOM** (`owb sbom generate`): "what AI extensions are in the workspace I am building?"

Downstream consumers who need to audit OWB's own supply chain should fetch the project SBOM from the GitHub Release. Users who want to inventory their own workspace should run `owb sbom generate` after building the workspace.

## Manual fallback

If the GitHub Release job fails after PyPI publish succeeds, create the Release manually without re-running the full workflow:

```bash
python scripts/extract_changelog.py CHANGELOG.md 1.9.0 > /tmp/release-body.md

python scripts/generate_sbom.py \
  --wheel dist/open_workspace_builder-1.9.0-py3-none-any.whl \
  --version 1.9.0 \
  --output dist/open-workspace-builder-1.9.0.cdx.json

gh release create v1.9.0 \
  --title v1.9.0 \
  --notes-file /tmp/release-body.md \
  dist/open_workspace_builder-1.9.0-py3-none-any.whl \
  dist/open_workspace_builder-1.9.0.tar.gz \
  dist/open-workspace-builder-1.9.0.cdx.json
```

This reuses the same helper scripts the workflow runs, so the output is identical to an automated run.

## Historical tags

OWB shipped v1.0.0 through v1.8.0 before adopting GitHub Releases as a distribution surface. Those historical tags have no Release objects and will not be backfilled. The sprint-close checklist applies only from v1.9.0 forward. If retroactive backfill is ever needed (e.g. for a downstream consumer who cannot fetch historical wheels from PyPI), file it as a separate story — do not run the release workflow against historical tags inside a normal sprint.

## Troubleshooting

### CHANGELOG extraction fails with "section not found"

The tag version and the CHANGELOG section header must match exactly. `v1.9.0` looks for `## [1.9.0]`. `v1.9.0-rc.1` looks for `## [1.9.0-rc.1]`. There is no implicit fallback to `[Unreleased]`, by design — a release must not proceed with the wrong body.

Fix: add the missing section, re-tag, and re-push. Or create the Release manually per the fallback above.

### CHANGELOG extraction fails with "section is empty"

The section header exists but has no content between it and the next section header. Releases must have a non-empty body.

Fix: fill in the CHANGELOG section, re-tag, and re-push.

### SBOM generation fails

The `generate_sbom.py` helper creates an isolated venv, installs the wheel plus `pip-audit`, and runs `pip-audit --local --format cyclonedx-json`. Failures usually fall into one of:

- **Missing wheel** — the build job did not produce a wheel. Check the build job logs.
- **`pip-audit` hard failure** (exit code ≥ 2) — `pip-audit` itself errored. Check the job logs for the underlying cause (network, dependency resolution, etc.). Exit codes 0 (clean) and 1 (vulnerabilities found) are both accepted as success for SBOM generation.
- **Invalid JSON output** — `pip-audit` produced a file that is not parseable CycloneDX JSON. Usually a `pip-audit` version regression; pin the version in the helper script if this recurs.

### PyPI publish succeeded but no GitHub Release was created

Re-run the `github_release` job from the Actions tab, or create the Release manually via the fallback procedure. PyPI state is not affected — PyPI cannot be unpublished, so the v1.9.0 version is locked on PyPI even if the GitHub Release is missing.

## References

- [AD-17: GitHub Releases as Canonical Release Distribution Surface](../adr.md#ad-17-github-releases-as-canonical-release-distribution-surface-sprint-23)
- [`.github/workflows/release.yml`](https://github.com/originalrgsec/open-workspace-builder/blob/main/.github/workflows/release.yml)
- [`scripts/extract_changelog.py`](https://github.com/originalrgsec/open-workspace-builder/blob/main/scripts/extract_changelog.py)
- [`scripts/generate_sbom.py`](https://github.com/originalrgsec/open-workspace-builder/blob/main/scripts/generate_sbom.py)
- [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
