# Release Process

This page documents the end-to-end process for cutting an OWB release. It is the contributor-facing complement to [AD-17](../adr.md#ad-17-github-releases-as-canonical-release-distribution-surface-sprint-23), which captures the architectural decision behind the release pipeline.

## Overview

OWB releases ship through five stages on every `v*` tag push, all within `release.yml`:

1. **Build** — construct the wheel and sdist with `pyproject-build`.
2. **Smoke** — install the wheel into a clean environment and verify the CLI entry point responds.
3. **Publish** — upload to PyPI via trusted publishing (`pypa/gh-action-pypi-publish@release/v1`, no API tokens).
4. **GitHub Release** — create a canonical Release object on GitHub with the wheel, sdist, and project SBOM attached as assets. Body sourced from the `CHANGELOG.md` section matching the tag.
5. **Slack notification** (sequential after GitHub Release, failure-isolated) — post a Block Kit message to `#owb-releases`. See [Release Notifications](#release-notifications) below.

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

Release workflow changes cannot be validated in isolation — the workflow only runs on a real tag push. The sanctioned way to exercise a workflow change without burning a real version number is a PEP 440 pre-release tag against a scratch branch.

**Pre-release versions must be canonical PEP 440.** That means `1.9.0rc1`, not `1.9.0-rc.1`. Python packaging tools normalize the latter to the former when building wheels, so if you use the hyphen-dot form in `pyproject.toml` the built wheel and the git tag will disagree on the version string. Stick to canonical PEP 440 for tags, `pyproject.toml`, and CHANGELOG section headers. Supported pre-release suffixes: `a<N>`, `b<N>`, `rc<N>`, `.dev<N>`, `.post<N>` (per PEP 440).

```bash
git checkout -b sprint-23-release-rehearsal

# 1. bump pyproject.toml version to the PEP 440 pre-release form
#    version = "1.9.0rc1"

# 2. add a temporary CHANGELOG section for the RC
#    ## [1.9.0rc1] - 2026-04-12
#    ### Rehearsal
#    - Validating AD-17 GitHub Release workflow.

git commit -am "chore: release workflow rehearsal (1.9.0rc1)"
git push origin sprint-23-release-rehearsal

git tag v1.9.0rc1
git push origin v1.9.0rc1
```

The workflow detects pre-release versions via a PEP 440 regex (`(a|b|rc|dev|post)[0-9]+$`) and adds `--prerelease` to the `gh release create` call. The resulting GitHub Release is flagged as a prerelease, clearly distinguishable from canonical releases.

Pre-release tags still publish to PyPI via the existing `publish` job. PyPI stores them as pre-release versions per PEP 440 and surfaces them only to users who opt in via `pip install --pre`. **PyPI is append-only** — the published version string is permanently reserved even if you later yank the file. Budget one version number per rehearsal and accept that `v1.9.0rc1` cannot be reused.

After validation:

```bash
gh release delete v1.9.0rc1 --yes
git push origin :refs/tags/v1.9.0rc1
git tag -d v1.9.0rc1
git branch -D sprint-23-release-rehearsal
git push origin --delete sprint-23-release-rehearsal
# revert the temporary CHANGELOG stub and pyproject.toml version bump
# before merging the real release PR
```

The PyPI pre-release file can be yanked via `pypi.org` if the rehearsal produced a broken artifact, but the version string itself is not reclaimable. The sprint-close skill reminds the operator to clean up the tag and Release object; PyPI cleanup is manual.

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

The `generate_sbom.py` helper creates an isolated venv, installs only the wheel into it, enumerates the resulting installed distributions via the venv's `importlib.metadata`, and constructs a CycloneDX 1.6 BOM directly via `cyclonedx-python-lib` with OWB in `metadata.component` and its dependencies in `components`. Venv bootstrap packages (`pip`, `setuptools`, `wheel`, etc.) are filtered out of the component list. Failures usually fall into one of:

- **Missing wheel** — the build job did not produce a wheel. Check the build job logs.
- **`venv creation` / `pip upgrade` / `wheel install` failed** — a pip or venv-layer error. Check the job logs. Usually network or index-resolution issues.
- **`dist enumeration failed`** — the isolated venv's Python could not run the `importlib.metadata` enumeration snippet. Almost always means the wheel install succeeded but left the venv in an inconsistent state. Re-run the workflow.
- **`generated BOM is not a CycloneDX document`** — `cyclonedx-python-lib` produced output that did not round-trip through JSON parsing. This is a library-level defect and should not happen; pin the library version if it recurs.

### PyPI publish succeeded but no GitHub Release was created

Re-run the `github_release` job from the Actions tab, or create the Release manually via the fallback procedure. PyPI state is not affected — PyPI cannot be unpublished, so the v1.9.0 version is locked on PyPI even if the GitHub Release is missing.

## Release Notifications

Every successful release posts a Block Kit notification to the `#owb-releases` Slack channel via the `notify_slack` job in `release.yml`. The notification runs after the `github_release` job and is failure-isolated: a Slack outage or misconfigured webhook does not block PyPI publish or Release creation. Notification failure is not a sprint-close gate.

**Why not a separate workflow?** Events created by `GITHUB_TOKEN` do not trigger other workflows (GitHub's infinite-loop prevention). A standalone `release-notify-slack.yml` listening for `release: published` would never fire because the Release is created by `GITHUB_TOKEN` in `release.yml`. The notification must live in the same workflow.

### How it works

1. The `release.yml` workflow creates a GitHub Release object (the `github_release` job).
2. The `notify_slack` job runs after `github_release` succeeds, fetches the Release body via `gh api`, truncates at 2,800 characters if needed, and posts a Block Kit message with:
   - **Header:** `OWB <version> released` (or `[PRE] OWB <version> released` for pre-releases).
   - **Section:** release body text.
   - **Context:** links to the GitHub Release page and PyPI page.

### Webhook provisioning (one-time)

The Slack notification requires an Incoming Webhook URL stored as a GitHub repo secret.

1. Go to [api.slack.com/apps](https://api.slack.com/apps) and create a new app named "OWB Release Bot" in your workspace (or reuse an existing app if you are close to the 10-app free-tier cap).
2. Under **Incoming Webhooks**, toggle on, then **Add New Webhook to Workspace** and select `#owb-releases`.
3. Copy the webhook URL.
4. Store it as a repo secret:
   ```bash
   gh secret set SLACK_RELEASE_WEBHOOK
   # paste the URL when prompted
   ```

The webhook URL grants write access to `#owb-releases`. Do not commit it to workflow YAML or any other file.

### Webhook rotation

If the webhook URL is exposed:

1. Go to the Slack app's **Incoming Webhooks** page, delete the compromised webhook.
2. Add a new webhook bound to the same channel.
3. Update the repo secret: `gh secret set SLACK_RELEASE_WEBHOOK` with the new URL.

No workflow file changes are needed; the secret name stays the same.

### Adding notifications to additional channels

To post to a second channel (e.g., a future `#owb-prereleases`):

1. Add another Incoming Webhook under the same "OWB Release Bot" Slack app, bound to the new channel. Do not create a separate Slack app (free-tier 10-app cap).
2. Store the new webhook URL as a separate repo secret (e.g., `SLACK_PRERELEASE_WEBHOOK`).
3. Add a second step in the `notify_slack` job of `release.yml` (or a conditional step) referencing the new secret.

### Trigger behavior

| Event | Notification? |
|-------|--------------|
| `v*` tag push (stable) | Yes, after successful GitHub Release |
| `v*` tag push (pre-release) | Yes, with `[PRE]` header prefix |

### Troubleshooting

- **"SLACK_RELEASE_WEBHOOK secret not set" notice.** The `notify_slack` job exits cleanly with a notice if the secret is missing. Common for forks or new contributors. Set the secret per the provisioning steps above.
- **Payload too large.** Release bodies longer than 2,800 characters are truncated with a "see full release notes" link. If Slack still rejects the payload, check for non-UTF-8 characters or unexpected JSON in the CHANGELOG section.
- **Notification did not post but workflow shows green.** Slack's Incoming Webhook API returns 200 even if the message is silently dropped (e.g., channel archived, webhook revoked). Check the channel directly.

## References

- [AD-17: GitHub Releases as Canonical Release Distribution Surface](../adr.md#ad-17-github-releases-as-canonical-release-distribution-surface-sprint-23)
- [`.github/workflows/release.yml`](https://github.com/originalrgsec/open-workspace-builder/blob/main/.github/workflows/release.yml)
- [`scripts/extract_changelog.py`](https://github.com/originalrgsec/open-workspace-builder/blob/main/scripts/extract_changelog.py)
- [`scripts/generate_sbom.py`](https://github.com/originalrgsec/open-workspace-builder/blob/main/scripts/generate_sbom.py)
- [Keep a Changelog 1.1.0](https://keepachangelog.com/en/1.1.0/)
- [Semantic Versioning 2.0.0](https://semver.org/spec/v2.0.0.html)
