# Using OWB as a Library

OWB is designed as a first-class dependency for downstream packages. A vendor-specific wrapper can import OWB's engine, security scanner, evaluator, and configuration infrastructure, then overlay its own defaults and extensions.

## How It Works

A downstream package like CWB (Claude Workspace Builder) depends on OWB and adds vendor-specific behavior on top:

1. **Declare the dependency**: Add `open-workspace-builder>=0.5.0` to your project's requirements.
2. **Provide a pre-baked config**: Ship a YAML file with vendor-specific defaults (model strings, trust policies, default skills). OWB's config loader merges it with user overrides.
3. **Register a CLI entry point**: Create a Click CLI that sets `cli_name` in the Click context. OWB's name-aware config resolution automatically reads from `~/.<cli_name>/config.yaml`.
4. **Extend or wrap**: Use OWB's evaluator, security scanner, and source infrastructure directly, or add vendor-specific modules (e.g., CWB adds `PolicyInstaller` after migrate).

## Config Namespace Isolation

OWB resolves paths from the binary name at runtime. When a user invokes `cwb`, OWB reads config from `~/.cwb/config.yaml`. When the same user invokes `owb`, it reads from `~/.owb/config.yaml`. The two namespaces are completely independent. A user can run both tools on the same machine without config collision.

## What You Get from OWB

| Component | What It Provides |
|-----------|-----------------|
| Config engine | Three-layer overlay, name-aware resolution, YAML schema |
| Vault builder | Directory scaffolding, template deployment, bootstrap generation |
| Security scanner | Three-layer pipeline, extensible pattern registry, trust tiers |
| Skill evaluator | Classification, test generation, scoring, incorporate/reject decisions |
| Source manager | Config-driven upstream content discovery, diff, and update |
| Migration engine | Drift detection, interactive file review, security-gated writes |

## Example: CWB

CWB (Claude Workspace Builder) is the reference downstream implementation. It wraps OWB's CLI with Claude-specific additions: `PolicyInstaller` runs after every migrate to ensure Claude-specific policies are applied, `vault-meta.json` tracks workspace versions for CWB-specific upgrade logic, and pre-baked config auto-installs to `~/.cwb/` on first run.

The CWB source is available at [github.com/VolcanixLLC/claude-workspace-builder](https://github.com/VolcanixLLC/claude-workspace-builder).
