"""Scan an existing vault to generate a starter Config."""

from __future__ import annotations

import json
from pathlib import Path

import click

from open_workspace_builder.config import (
    Config,
    MarketplaceConfig,
    ModelsConfig,
    PathsConfig,
    _resolve_paths,
)
from open_workspace_builder.wizard.setup import _write_config_yaml


# ── CWB preset models ───────────────────────────────────────────────────────

_CWB_MODELS = ModelsConfig(
    classify="anthropic/claude-sonnet-4-20250514",
    generate="anthropic/claude-sonnet-4-20250514",
    judge="anthropic/claude-sonnet-4-20250514",
    security_scan="anthropic/claude-haiku-4-5-20251001",
)


def _detect_vault_tiers(vault_path: Path) -> tuple[str, ...]:
    """Detect tier directories by looking for dirs containing project subdirs.

    A project subdir is one that contains _index.md or status.md.
    """
    tiers: list[str] = []
    if not vault_path.is_dir():
        return ()

    for child in sorted(vault_path.iterdir()):
        if not child.is_dir() or child.name.startswith((".", "_")):
            continue
        # Check if this dir contains subdirs with _index.md or status.md
        has_project = any(
            sub.is_dir() and ((sub / "_index.md").exists() or (sub / "status.md").exists())
            for sub in child.iterdir()
        )
        if has_project:
            tiers.append(child.name)

    return tuple(tiers)


def _detect_vault_meta(vault_path: Path) -> dict | None:
    """Look for vault-meta.json in the vault or its parent .owb/.cwb dir."""
    for name in ("vault-meta.json", ".vault-meta.json"):
        meta_path = vault_path / name
        if meta_path.exists():
            try:
                return json.loads(meta_path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass
    return None


def scan_vault(vault_path: Path, cli_name: str = "owb") -> Config:
    """Scan an existing Obsidian vault and generate a starter Config.

    For cwb, applies Claude model defaults and Anthropic marketplace format.
    For owb, leaves model strings empty.
    """
    click.echo(f"Scanning vault at {vault_path}...")

    tiers = _detect_vault_tiers(vault_path)
    if tiers:
        click.echo(f"Detected tiers: {', '.join(tiers)}")
    else:
        click.echo("No project tiers detected (using defaults).")

    meta = _detect_vault_meta(vault_path)
    if meta:
        click.echo(f"Found vault metadata: version={meta.get('version', 'unknown')}")

    # CWB flavor: Claude models + Anthropic marketplace
    is_cwb = cli_name == "cwb"
    models = _CWB_MODELS if is_cwb else ModelsConfig()
    marketplace = MarketplaceConfig(format="anthropic") if is_cwb else MarketplaceConfig()

    paths = _resolve_paths(PathsConfig(), cli_name)

    config = Config(
        models=models,
        marketplace=marketplace,
        paths=paths,
    )

    # Write config file
    config_dir = Path(paths.config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "data").mkdir(exist_ok=True)
    (config_dir / "credentials").mkdir(exist_ok=True)

    config_path = config_dir / "config.yaml"
    _write_config_yaml(config, config_path)
    click.echo(f"Configuration written to {config_path}")

    return config
