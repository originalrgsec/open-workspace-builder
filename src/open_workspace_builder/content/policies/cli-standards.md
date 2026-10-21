---
type: policy
scope: all-projects
created: 2026-03-27
updated: 2026-04-19
tags: [policy, process, cli, standards]
---

# CLI Standards

## Purpose

This document defines shared CLI conventions for Python projects in this workspace that expose a command-line interface. The patterns are extracted from mature CLIs with broad test coverage. New projects adopt these patterns; existing projects converge at the next major CLI change.

Companion documents:

- [[code/development-process]] — sprint mechanics, release notes
- [[code/integration-verification-policy]] — CLI contract testing requirement

## Framework

All CLIs use [Click](https://click.palletsprojects.com/) with the group/command pattern.

```python
@click.group()
@click.version_option(package_name="project-name")
@click.option("--config", "-c", "config_path", type=click.Path(exists=True), default=None)
@click.pass_context
def main(ctx: click.Context, config_path: str | None) -> None:
    """One-line description."""
    ctx.ensure_object(dict)
    ctx.obj["config"] = load_config(config_path)
```

## Command Hierarchy

Commands are organized into Click groups by domain:

```
project-name [--config PATH]
├── <top-level commands>          Direct actions (resolve, run, init, etc.)
└── <group>                       Namespaced subcommands
    └── <subcommand>
```

**Naming rules:**

- Groups: lowercase singular noun (`auth`, `audit`, `schedule`, `cleanup`)
- Commands: lowercase, hyphenated verbs or verb-noun (`store-credentials`, `import-opml`)
- Arguments: positional for required primary input (`<url>`, `<file>`, `<adapter_name>`)
- Options: `--kebab-case` with short forms for common flags (`-c`, `-n`, `-o`)

## Configuration Loading

Three-layer resolution, evaluated in order:

1. `--config` / `-c` CLI flag (explicit override)
2. Environment variable (`PROJECT_NAME_CONFIG` or `PROJECT_NAME_CONFIG_PATH`)
3. Default path (`~/.config/project-name/config.yaml`)
4. Built-in defaults (Pydantic model defaults)

Config models are Pydantic v2, immutable (frozen where appropriate). CLI flags that override config values produce a new config object, not mutation.

```python
# CLI flag overrides config (immutable pattern)
effective_config = config.model_copy(update={"notes": config.notes.model_copy(update={"vault_path": vault})})
```

## Auth Command Pattern

Projects with credential management use a consistent `auth` group:

```
project-name auth
├── store-credentials <provider>   Encrypt and store client credentials
├── <provider>                     Run OAuth flow for a specific provider
└── status                         Show credential and token state
```

**Credential storage:**

- Age encryption (via `pyrage` or the SOPS/age toolchain) for at-rest credential protection
- Secrets file: YAML with provider namespaces (`{ google: { client_id: "...", client_secret: "..." } }`)
- Age key file: standard `age-keygen` format (`# public key: age1...` + `AGE-SECRET-KEY-...`)
- New providers added to existing secrets file without disturbing other entries

**Key file loading** uses a shared helper pattern:

```python
def load_age_keys(key_path: Path) -> tuple[str, str]:
    """Parse public key from comment line, private key from AGE-SECRET-KEY line."""
```

**Interactive input:** `click.prompt(hide_input=True)` for secrets. Never echo credentials.

**Error handling:** `click.ClickException` for user-facing auth errors (missing key file, missing credentials, malformed files). Message includes remediation: "Run `project-name auth store-credentials <provider>` first."

## Exit Codes

| Code | Meaning | When |
|------|---------|------|
| 0 | Success | Command completed as expected |
| 1 | Error | Config error, runtime failure, missing required data |
| 2 | Partial / Critical | Some items failed in batch, or security findings blocking |

For batch operations: 0 = all succeeded, 1 = total failure, 2 = partial (some succeeded, some failed).

## Output Conventions

**User-facing output:** `click.echo()` to stdout. Human-readable by default.

**Machine logging:** `structlog` with structured fields. Never printed to stdout in normal operation.

**JSON output:** Opt-in via `--json` flag (for commands that support it). Always `indent=2`.

**Error messages:** `click.echo(f"Error: {message}", err=True)` to stderr. No stack traces in user output. Sub-items indented with two spaces.

```python
click.echo("Error: configuration error for adapter:", err=True)
for err_msg in errors:
    click.echo(f"  - {err_msg}", err=True)
```

**Progress:** For batch operations, print one line per item processed. Summary at end.

## Async Bridge

CLI commands are sync (Click requirement). Async logic lives in inner functions:

```python
@main.command()
@click.pass_context
def my_command(ctx: click.Context) -> None:
    result = asyncio.run(_my_command_async(ctx.obj["config"]))
    click.echo(result)

async def _my_command_async(config: Config) -> str:
    """Async implementation with resource cleanup."""
    client = AsyncClient(config)
    try:
        return await client.do_work()
    finally:
        await client.close()
```

**Rules:**

- `asyncio.run()` called exactly once per CLI command
- Inner async functions named with leading `_` underscore
- Resource cleanup in `try/finally` blocks

## Destructive Operations

Commands that modify external state require opt-in flags:

- `--dry-run` / `-n`: Preview without executing
- `--confirm`: Required for destructive actions (unfollows, deletes)
- `--no-upload`: Skip external uploads (local-only mode)

When `--dry-run` is active without `--confirm`, print what would happen and suggest adding `--confirm`.

## CLI Contract Testing

Per [[code/integration-verification-policy]], every documented CLI command must respond to `--help` with exit code 0. This is verified by a parametrized test:

```python
DOCUMENTED_COMMANDS: list[list[str]] = [
    ["resolve", "--help"],
    ["collect", "--help"],
    ["auth", "status", "--help"],
    # ... all commands
]

@pytest.mark.parametrize("args", DOCUMENTED_COMMANDS)
def test_command_responds_to_help(runner: CliRunner, args: list[str]) -> None:
    result = runner.invoke(main, args)
    assert result.exit_code == 0
```

The contract test file lives at `tests/test_cli_contract.py`. Updated whenever a command is added or removed.

## Common Option Reference

| Option | Short | Purpose | Common uses |
|--------|-------|---------|-------------|
| `--config` | `-c` | Config file path | All projects |
| `--json` | | JSON output mode | resolve, audit, scan |
| `--dry-run` | `-n` | Preview without writing | migrate, cleanup, init |
| `--no-upload` | | Skip external uploads | collect, batch |
| `--vault` | | Obsidian vault path override | commands that write to the vault |
| `--confirm` | | Execute destructive action | cleanup, audit |
| `--output` | `-o` | Write report to file | scan, audit |
| `--verbose` | `-v` | Extra diagnostic output | digest, debug |

## Applying This Policy

New CLI commands in any project built from this workspace should follow these conventions. When extending an existing CLI, check this document for the applicable pattern before implementing.

The CLI contract test is a sprint acceptance gate per [[code/integration-verification-policy]].
