# Using OWB as a Library

OWB is designed as a first-class dependency for downstream packages. A vendor-specific wrapper can import OWB's engine, security scanner, evaluator, and configuration infrastructure, then overlay its own defaults and extensions.

## How It Works

A downstream wrapper depends on OWB and adds vendor-specific behavior on top:

1. **Declare the dependency**: Add `open-workspace-builder>=0.5.0` to your project's requirements.
2. **Provide a pre-baked config**: Ship a YAML file with vendor-specific defaults (model strings, trust policies, default skills). OWB's config loader merges it with user overrides.
3. **Register a CLI entry point**: Create a Click CLI that sets `cli_name` in the Click context. OWB's name-aware config resolution automatically reads from `~/.<cli_name>/config.yaml`.
4. **Extend or wrap**: Use OWB's evaluator, security scanner, and source infrastructure directly, or add vendor-specific modules (e.g., a post-migrate hook that installs vendor policies).

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

## Building a Wrapper

A typical vendor wrapper follows this pattern:

**Project structure:**

```
my-workspace-builder/
├── pyproject.toml          # depends on open-workspace-builder
├── src/my_wb/
│   ├── __init__.py
│   ├── cli.py              # Click CLI with cli_name="mwb"
│   ├── config/
│   │   └── defaults.yaml   # pre-baked vendor defaults
│   └── hooks/
│       └── post_migrate.py # vendor-specific post-migrate logic
```

**CLI entry point** (`cli.py`):

```python
import click
from open_workspace_builder.cli import owb

@click.group(cls=type(owb))
@click.pass_context
def mwb(ctx):
    """My Workspace Builder — powered by OWB."""
    ctx.ensure_object(dict)
    ctx.obj["cli_name"] = "mwb"

# Re-export OWB commands you want to expose
mwb.add_command(owb.commands["init"])
mwb.add_command(owb.commands["migrate"])
mwb.add_command(owb.commands["audit"])
```

**Pre-baked config** (`defaults.yaml`):

```yaml
vault:
  assistant_name: "My Agent"
ecc:
  enabled: true
  target_dir: ".my-agent"
models:
  classify: "anthropic/claude-sonnet-4-20250514"
  generate: "anthropic/claude-sonnet-4-20250514"
```

Ship this file with the package and copy it to `~/.<cli_name>/config.yaml` on first run. OWB's config loader picks it up automatically based on the CLI name.

**Post-migrate hook** (`post_migrate.py`):

```python
from pathlib import Path

def install_vendor_policies(workspace: Path) -> None:
    """Run after owb migrate to apply vendor-specific policies."""
    policies_dir = workspace / ".my-agent" / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    # Deploy vendor-specific content here
```

Wire this into your CLI's migrate command by wrapping OWB's migrate and calling the hook after it completes.

This pattern gives you full access to OWB's engine, security scanner, and evaluator while maintaining a separate config namespace and the ability to layer vendor-specific behavior on top.
