# How to: Software Bill of Materials

This guide walks through the operational SBOM commands for an AI workspace. Read [AI Extension SBOMs](concepts/sbom.md) first if you want the conceptual model.

## Generate an SBOM

```bash
owb sbom generate examples/workspace
```

By default the SBOM goes to stdout. Pipe it to a file or use `--output`:

```bash
owb sbom generate examples/workspace -o examples/workspace.cdx.json
```

The default format is CycloneDX 1.6. Pass `--format spdx` for an SPDX 2.3 JSON document for downstream tools that only consume SPDX:

```bash
owb sbom generate examples/workspace --format spdx -o examples/workspace.spdx.json
```

Exit codes from `generate`:

- `0` — clean
- `1` — error (workspace missing, serialization failure)
- `2` — one or more components have a non-allowed or unrecognized license

## Inspect an SBOM

`owb sbom show` is a read-only inspector. Default mode prints a one-line-per-component summary:

```bash
owb sbom show examples/workspace.cdx.json
```

```
KIND        NAME       VERSION    LICENSE    PROV                  CAPS  BOM-REF
skill       hello      1.0.0      MIT        git-history/high      2     owb:skill/hello@1.0.0
agent       planner    abc123     —          local/low             0     owb:agent/planner@abc123
mcp-server  example    def456     —          git-history/high      3     owb:mcp-server/example@def456
```

For the full enrichment dump on a single component:

```bash
owb sbom show examples/workspace.cdx.json --component owb:skill/hello@1.0.0
```

Use `--format json` if you want machine-readable output instead of the table.

## Diff two SBOMs

```bash
owb sbom diff old.cdx.json new.cdx.json
```

Default output is a stable JSON document with `added`, `removed`, `changed`, and `unchanged_count` buckets. Use `--format text` for a one-line-per-change human summary:

```bash
owb sbom diff old.cdx.json new.cdx.json --format text
```

```
+ added    owb:skill/new-skill@abc123
- removed  owb:skill/retired@def456
~ changed  owb:agent/planner@xyz789  [licenses] ['MIT'] -> ['Apache-2.0']
~ changed  owb:agent/planner@xyz789  [content_hash] aaa... -> bbb...
summary: +1 -1 ~1 =4
```

The diff comparable surface is intentionally narrow: content hash, license, capability set, and provenance source/commit. The `added_at` metadata field is excluded so cosmetic mtime changes do not register as drift.

Exit codes:

- `0` — no differences
- `1` — read or parse error
- `2` — differences present

## Verify a workspace against a canonical SBOM

```bash
owb sbom verify --workspace . --against .owb/sbom.cdx.json
```

Both flags have sensible defaults: `--workspace .` and `--against .owb/sbom.cdx.json`. So in the common case:

```bash
owb sbom verify
```

`verify` regenerates the workspace SBOM in-memory and runs the same diff against the canonical file. Exit codes match `diff` (0 / 1 / 2).

## Quarantine recently-added AI extensions

```bash
owb sbom quarantine --days 7
```

Reports every component whose `owb:provenance:added-at` falls inside the last 7 days. Default window is 7. Use `--days 0` once after a fresh clone to baseline a new workspace, then go back to the default for change-only enforcement:

```bash
# Right after cloning:
owb sbom quarantine --days 0
# In normal use:
owb sbom quarantine
```

If you already have an SBOM file, point at it directly to skip the in-memory regeneration:

```bash
owb sbom quarantine --sbom .owb/sbom.cdx.json --days 7
```

Exit codes:

- `0` — no components inside the window
- `1` — error
- `2` — one or more components inside the window

## Pre-commit recipe

Add this to `.pre-commit-config.yaml` to fail any commit that drifts from the canonical SBOM:

```yaml
repos:
  - repo: local
    hooks:
      - id: owb-sbom-verify
        name: owb sbom verify
        entry: owb sbom verify
        language: system
        pass_filenames: false
        always_run: true
```

Pair it with a pre-commit step that *regenerates* the canonical SBOM if you prefer drift-detection-then-update over fail-on-drift:

```yaml
      - id: owb-sbom-regenerate
        name: owb sbom generate
        entry: bash -c 'owb sbom generate . -o .owb/sbom.cdx.json && git add .owb/sbom.cdx.json'
        language: system
        pass_filenames: false
        always_run: true
```

Pick one. Running both would be a footgun (the first edits the canonical and the second checks against the just-edited copy).

## GitHub Actions recipe

`owb sbom diff` against the base branch is the simplest "what changed" gate for a PR:

```yaml
name: SBOM diff
on:
  pull_request:
    branches: [main]

jobs:
  sbom-diff:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0
      - name: Install OWB
        run: pip install open-workspace-builder
      - name: Generate base SBOM
        run: |
          git checkout origin/main -- .
          owb sbom generate . -o /tmp/base.cdx.json
          git checkout HEAD -- .
      - name: Generate head SBOM
        run: owb sbom generate . -o /tmp/head.cdx.json
      - name: Diff
        run: owb sbom diff /tmp/base.cdx.json /tmp/head.cdx.json --format text
```

Set `continue-on-error: true` on the diff step if you want a soft warning instead of a hard fail.

## Skill quarantine in the scanner

The `owb scan` command can also consult the SBOM as part of its gate pipeline:

```bash
owb scan . --skill-quarantine
```

This wires `owb sbom quarantine --days 7` into the scanner's existing check pipeline, so the same `has_issues` exit-code logic that catches a `pip-audit` finding also catches a recently-added skill. The flag is opt-in by default to preserve backwards compatibility; a future release will flip the default after a deprecation cycle.

## See also

- [AI Extension SBOMs](concepts/sbom.md) — conceptual overview
- [Supply Chain Security](concepts/supply-chain-security.md) — the broader SSCA model
- [CycloneDX 1.6 spec](https://cyclonedx.org/docs/1.6/json/)
- [SPDX 2.3 spec](https://spdx.github.io/spdx-spec/v2.3/)
