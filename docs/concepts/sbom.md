# AI Extension SBOMs

A **Software Bill of Materials** (SBOM) is a structured inventory of every component that participates in a piece of software. OWB produces an SBOM for the *AI extension surface* of any workspace: every skill, agent, slash command, and MCP server is one entry, with content hash, provenance, declared capabilities, license, and first-add date.

The SBOM is the answer to four operational questions that show up the moment a workspace has more than a handful of components:

1. **What is in here?** — `owb sbom show`
2. **What changed between two states?** — `owb sbom diff`
3. **Did the workspace drift from the canonical state?** — `owb sbom verify`
4. **Was anything added inside the supply-chain quarantine window?** — `owb sbom quarantine`

## Why CycloneDX 1.6

CycloneDX 1.6 is the canonical internal format. The reasons:

- **Spec coverage.** CycloneDX has a stable, versioned JSON schema that covers components, hashes, licenses, properties, and metadata without requiring relationships, files, or snippets the way SPDX does.
- **Properties namespace.** OWB carries provenance, capability, and license-policy decisions in `owb:*` namespaced properties. CycloneDX property semantics let downstream tools ignore the namespace cleanly while still exposing it to anyone who knows to look.
- **Ecosystem.** Dependency-Track, Harness SSCA, and most modern SCA pipelines accept CycloneDX as a first-class input.
- **Library quality.** `cyclonedx-python-lib` produces a strict-validator-clean BOM with one call.

SPDX 2.3 is supported as a **write-only secondary format** (`owb sbom generate --format spdx`) for downstream tools that only consume SPDX. OWB does not parse SPDX back in. CycloneDX is the source of truth.

## Content normalization (`sha256-norm1`)

Component hashes need to be stable across cosmetic edits or pre-commit hooks would fail every time someone fixed trailing whitespace. The OWB normalization algorithm `norm1` enforces:

1. Trailing whitespace stripped per line
2. CRLF and CR line endings normalized to LF
3. The `updated:` YAML frontmatter field stripped (templates bump it on every save)
4. Trailing empty lines collapsed
5. SHA-256 over the normalized UTF-8 bytes

The hash is emitted as `sha256-norm1:<hex>`. Any future change to the rules must bump the version tag (`norm1` → `norm2`) so SBOMs generated under the old rules remain interpretable. Both the v1.6.0 and v1.7.0 fixtures have a hash-stability regression test that fails the build if any existing component hash changes between releases.

## OWB property namespaces

Every namespace below is an OWB extension carried in CycloneDX `properties`. Downstream consumers can read or ignore them at will.

| Namespace | Purpose |
|---|---|
| `owb:kind` | Component kind: `skill`, `agent`, `command`, `mcp-server` |
| `owb:source` | The literal `source:` string from frontmatter (or `local`) |
| `owb:content-hash` | Full tagged hash string (`sha256-norm1:<hex>`) |
| `owb:normalization` | Normalization algorithm version (`norm1`) |
| `owb:evidence-path` | Workspace-relative path to the evidence file |
| `owb:provenance:type` | `frontmatter`, `install-record`, `git-history`, or `local` |
| `owb:provenance:confidence` | `high`, `medium`, or `low` |
| `owb:provenance:source` | Canonical upstream URL (https-normalized) |
| `owb:provenance:commit` | First-add commit SHA when known |
| `owb:provenance:added-at` | First-add date (`YYYY-MM-DD`); used by quarantine |
| `owb:provenance:installed-at` | Install timestamp from `.owb/install-records/` |
| `owb:provenance:package` | Package name from an install record |
| `owb:capability:tool:<name>` | Declared tool authorization |
| `owb:capability:mcp:<server>` | Declared MCP server connection |
| `owb:capability:network:declared` | Component declared network access |
| `owb:capability:transport:<type>` | MCP transport: `stdio`, `sse`, `http` |
| `owb:capability:exec` | MCP exec command (no values, just presence) |
| `owb:capability:env:<KEY>` | MCP env *key* (values are never recorded) |
| `owb:capability:warning` | Wildcard or other capability oddity |
| `owb:license:warning` | Component carries a non-allowed or unrecognized license |
| `owb:license:non-allowed-count` | Top-level metadata aggregate |

License information itself is emitted as the spec-native CycloneDX `licenses` field, not in a `owb:` property.

## The capability honesty caveat

Capability extraction reads what skills and agents *declare* in their frontmatter. It does not enforce anything at runtime. A skill that declares no `allowed-tools` may still call any tool the LLM grants it; OWB cannot statically prove otherwise. The SBOM is therefore an inventory of *declared posture*, not a contract of *runtime behavior*. This distinction is load-bearing for any downstream policy decision and is documented here so consumers do not over-claim from the data.

For MCP servers, the same caveat applies in reverse: the `owb:capability:env:<KEY>` properties record the *names* of environment variables the server reads, never the values. A leaked secret cannot end up in an SBOM by construction.

## Quarantine model

`owb sbom quarantine [--days N]` applies the same supply-chain hygiene to AI extensions that the package quarantine applies to Python dependencies. Every component carries a `owb:provenance:added-at` field (`YYYY-MM-DD`) sourced from `git log --diff-filter=A --follow` (high confidence) or file `mtime` (low confidence). A component whose `added-at` falls inside the last N days is "quarantined" — the operator should review the addition before relying on it.

Default window is 7 days, mirroring the Python package quarantine policy in [`Obsidian/code/supply-chain-protection.md`](https://github.com/originalrgsec/open-workspace-builder/blob/main/Obsidian/code/supply-chain-protection.md). The number is not magic; it is the working assumption that 7 days is long enough for the broader open-source community to flag a compromised release.

**Onboarding caveat.** A fresh clone of a workspace will look like every component was added today. The recommended workflow is to run `owb sbom quarantine --days 0` once after cloning to baseline the workspace, then use the default `--days 7` going forward against changes only.

The same logic is also exposed as a scanner gate via `owb scan --skill-quarantine`. The flag is **opt-in by default**; flipping the default will ship in a follow-on after a deprecation cycle so existing scan workflows do not break silently.

## Operational commands

| Command | Purpose | Exit codes |
|---|---|---|
| `owb sbom generate` | Build a workspace SBOM | 0 clean / 1 error / 2 non-allowed license present |
| `owb sbom diff` | Structurally diff two SBOMs | 0 no diff / 1 error / 2 differences |
| `owb sbom verify` | Compare workspace state to a canonical SBOM | 0 match / 1 error / 2 drift |
| `owb sbom show` | Pretty-print an SBOM (or one component) | 0 OK / 1 error / 2 component not found |
| `owb sbom quarantine` | Flag recently-added AI extensions | 0 clean / 1 error / 2 inside window |

The diff comparable surface is intentionally narrow: content hash, license, capability set, and provenance source/commit. The `added_at` field is *not* in the diff surface — it is metadata, and a workspace with stable content but updated mtimes must not register as drift.

## What the SBOM does not (and will not) cover

- **Signing.** No in-toto, sigstore, or cosign integration. Signing is a follow-on story.
- **Vulnerability enrichment.** OWB does not look up CVEs per component. Use a downstream SBOM consumer (Dependency-Track, Harness SSCA) for that.
- **Runtime telemetry.** The SBOM is static-content-only. It does not record what tools a session actually called.
- **Round-trip from SPDX.** SPDX 2.3 is write-only. CycloneDX is the source of truth.
- **Static analysis of skill bodies.** The SBOM records *declared* capabilities, not *guaranteed* enforcement (see capability honesty caveat above).

## See also

- [SBOM howto](../howto-sbom.md) — worked examples for `generate`, `show`, `diff`, `verify`, `quarantine`, SPDX output, pre-commit hook, GitHub Actions recipe.
- [Supply Chain Security](supply-chain-security.md) — the broader SSCA model the SBOM fits inside.
- [CycloneDX 1.6 spec](https://cyclonedx.org/docs/1.6/json/) — upstream schema reference.
- [SPDX 2.3 spec](https://spdx.github.io/spdx-spec/v2.3/) — the secondary output format.
