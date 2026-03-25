"""Interactive setup wizard for first-run configuration."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import click

from open_workspace_builder.config import (
    Config,
    MarketplaceConfig,
    ModelsConfig,
    PathsConfig,
    SecretsConfig,
    SecurityConfig,
    TrustConfig,
    _resolve_paths,
)


# ── Provider presets ─────────────────────────────────────────────────────────

_ANTHROPIC_MODELS = ModelsConfig(
    classify="anthropic/claude-sonnet-4-20250514",
    generate="anthropic/claude-sonnet-4-20250514",
    judge="anthropic/claude-sonnet-4-20250514",
    security_scan="anthropic/claude-haiku-4-5-20251001",
)

_OPENAI_MODELS = ModelsConfig(
    classify="openai/gpt-4o",
    generate="openai/gpt-4o",
    judge="openai/gpt-4o",
    security_scan="openai/gpt-4o",
)

_PROVIDER_CHOICES = {
    "1": ("Anthropic (Claude)", "anthropic"),
    "2": ("OpenAI", "openai"),
    "3": ("Ollama (local)", "ollama"),
    "4": ("Other (manual)", "other"),
    "5": ("Skip", "skip"),
}


# ── Step functions ───────────────────────────────────────────────────────────


def _step_models() -> tuple[ModelsConfig, str]:
    """Step 1: Model provider selection. Returns (ModelsConfig, provider_key)."""
    click.echo("\nWhich model provider will you use?")
    for key, (label, _) in _PROVIDER_CHOICES.items():
        click.echo(f"  [{key}] {label}")

    choice = click.prompt("Selection", type=click.Choice(list(_PROVIDER_CHOICES)), default="1")
    _, provider = _PROVIDER_CHOICES[choice]

    if provider == "anthropic":
        return _ANTHROPIC_MODELS, provider
    if provider == "openai":
        return _OPENAI_MODELS, provider
    if provider == "ollama":
        model_name = click.prompt("Ollama model name", default="ollama/mistral")
        if not model_name.startswith("ollama/"):
            model_name = f"ollama/{model_name}"
        models = ModelsConfig(
            classify=model_name,
            generate=model_name,
            judge=model_name,
            security_scan=model_name,
        )
        return models, provider
    if provider == "other":
        classify = click.prompt("Model for classify", default="")
        generate = click.prompt("Model for generate", default="")
        judge = click.prompt("Model for judge", default="")
        security_scan = click.prompt("Model for security_scan", default="")
        return ModelsConfig(
            classify=classify,
            generate=generate,
            judge=judge,
            security_scan=security_scan,
        ), provider

    # skip
    return ModelsConfig(), provider


def _step_secrets_backend() -> SecretsConfig:
    """Step 2a: Secrets backend selection."""
    click.echo("\nHow should API keys be stored?")
    click.echo("  [1] Environment variables (default — keys set in shell)")
    click.echo("  [2] OS keyring (macOS Keychain, GNOME Keyring, etc.)")
    click.echo("  [3] Age encryption (file-based, encrypted at rest)")

    bw_status = _check_bitwarden_available()
    bw_suffix = "" if bw_status else " [not found — https://bitwarden.com/help/cli/]"
    click.echo(f"  [4] Bitwarden CLI{bw_suffix}")

    op_status = _check_onepassword_available()
    op_suffix = "" if op_status else " [not found — https://developer.1password.com/docs/cli/]"
    click.echo(f"  [5] 1Password CLI{op_suffix}")

    choice = click.prompt(
        "Selection", type=click.Choice(["1", "2", "3", "4", "5"]), default="1"
    )

    if choice == "1":
        return SecretsConfig(backend="env")

    if choice == "2":
        try:
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            if not KeyringBackend.is_available():
                click.echo("Warning: keyring is installed but using a fail backend.")
                click.echo("Falling back to env.")
                return SecretsConfig(backend="env")
        except ImportError:
            click.echo("Warning: keyring not installed. Install with:")
            click.echo("  pip install 'open-workspace-builder[keyring]'")
            click.echo("Falling back to env.")
            return SecretsConfig(backend="env")
        return SecretsConfig(backend="keyring")

    if choice == "3":
        try:
            from open_workspace_builder.secrets.age_backend import AgeBackend

            if not AgeBackend.is_available():
                click.echo("Warning: neither pyrage nor age CLI found.")
                click.echo("Install with: pip install 'open-workspace-builder[age]'")
                click.echo("Falling back to env.")
                return SecretsConfig(backend="env")
        except ImportError:
            click.echo("Warning: age backend not available. Falling back to env.")
            return SecretsConfig(backend="env")
        identity = click.prompt("Identity file path", default="~/.config/owb/key.txt")
        return SecretsConfig(backend="age", age_identity=identity)

    if choice == "4":
        if not bw_status:
            click.echo("Warning: bw CLI not found or not functional.")
            click.echo("Install from: https://bitwarden.com/help/cli/")
            click.echo("Falling back to env.")
            return SecretsConfig(backend="env")
        item_name = click.prompt("Bitwarden item name", default="OWB API Keys")
        return SecretsConfig(backend="bitwarden", bitwarden_item=item_name)

    # choice == "5" — 1Password
    if not op_status:
        click.echo("Warning: op CLI not found or not authenticated.")
        click.echo("Install from: https://developer.1password.com/docs/cli/")
        click.echo("Falling back to env.")
        return SecretsConfig(backend="env")
    vault_name = click.prompt("1Password vault name", default="Development")
    return SecretsConfig(backend="onepassword", onepassword_vault=vault_name)


def _check_bitwarden_available() -> bool:
    """Check if Bitwarden CLI is available."""
    try:
        from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
        return BitwardenBackend.is_available()
    except Exception:
        return False


def _check_onepassword_available() -> bool:
    """Check if 1Password CLI is available."""
    try:
        from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
        return OnePasswordBackend.is_available()
    except Exception:
        return False


def _step_api_key(provider: str, secrets_cfg: SecretsConfig) -> None:
    """Step 2b: API key storage via secrets backend."""
    if provider == "skip":
        return

    if provider == "ollama":
        endpoint = click.prompt("Ollama endpoint URL", default="http://localhost:11434")
        click.echo(f"Ollama endpoint: {endpoint}")
        click.echo("Set OLLAMA_API_BASE in your environment if it differs from default.")
        return

    if provider in ("anthropic", "openai"):
        env_var = "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY"
        key_name = env_var.lower()

        click.echo(f"\nYou can set {env_var} in your environment instead of storing here.")
        store = click.confirm("Store API key now?", default=False)
        if not store:
            return

        api_key = click.prompt("API key", hide_input=True)
        if not api_key.strip():
            click.echo("No key entered, skipping.")
            return

        from open_workspace_builder.secrets.factory import get_backend

        try:
            backend = get_backend(secrets_cfg)
            backend.set(key_name, api_key.strip())
            click.echo(f"API key stored in {backend.backend_name()} backend as '{key_name}'.")
        except Exception as exc:
            click.echo(f"Error storing key: {exc}")
            click.echo(f"Set {env_var} in your environment instead.")
        return

    # "other" provider — no standard key storage
    click.echo("\nSet the appropriate API key environment variable for your provider.")


def _step_vault_tiers() -> tuple[str, ...]:
    """Step 3: Vault tier names."""
    defaults = ("Work", "Personal", "Open Source")
    click.echo(f"\nDefault workspace tiers: {', '.join(defaults)}")
    customize = click.confirm("Customize tier names?", default=False)
    if not customize:
        return defaults

    tiers: list[str] = []
    for i, default in enumerate(defaults, 1):
        name = click.prompt(f"Tier {i} name", default=default)
        tiers.append(name)

    # Allow adding more tiers
    while click.confirm("Add another tier?", default=False):
        name = click.prompt(f"Tier {len(tiers) + 1} name")
        tiers.append(name)

    return tuple(tiers)


def _step_marketplace() -> MarketplaceConfig:
    """Step 4: Marketplace format."""
    click.echo("\nMarketplace output format:")
    click.echo("  [1] Generic (default)")
    click.echo("  [2] Anthropic")
    click.echo("  [3] OpenAI")
    choice = click.prompt("Selection", type=click.Choice(["1", "2", "3"]), default="1")
    formats = {"1": "generic", "2": "anthropic", "3": "openai"}
    return MarketplaceConfig(format=formats[choice])


def _step_security_patterns() -> SecurityConfig:
    """Step 5: Security pattern selection."""
    click.echo("\nSecurity pattern sets to activate:")
    click.echo("  [1] All defaults (recommended)")
    click.echo("  [2] Select individually")
    choice = click.prompt("Selection", type=click.Choice(["1", "2"]), default="1")

    if choice == "1":
        return SecurityConfig()

    # List available pattern sets from the registry
    pattern_ids = [
        "owb-exfiltration",
        "owb-persistence",
        "owb-stealth",
        "owb-self-modification",
        "owb-encoded",
        "owb-network",
        "owb-privilege",
        "owb-sensitive-paths",
        "owb-prompt-injection",
    ]
    selected: list[str] = []
    for pid in pattern_ids:
        if click.confirm(f"  Enable {pid}?", default=True):
            selected.append(pid)

    active = tuple(selected) if selected else ("owb-default",)
    return SecurityConfig(active_patterns=active)


def _step_trust_policy() -> TrustConfig:
    """Step 6: Trust tier policy."""
    click.echo("\nTrust tier policy:")
    click.echo("  [1] Default (T0/T1/T2 — recommended)")
    click.echo("  [2] Skip (configure later)")
    choice = click.prompt("Selection", type=click.Choice(["1", "2"]), default="1")
    if choice == "2":
        return TrustConfig(active_policies=())
    return TrustConfig()


def _write_config_yaml(config: Config, config_path: Path) -> None:
    """Serialize Config to YAML and write to disk."""
    import yaml  # type: ignore[import-untyped]

    data: dict[str, Any] = {"target": config.target}

    if any(getattr(config.models, f) for f in ("classify", "generate", "judge", "security_scan")):
        data["models"] = {
            "classify": config.models.classify,
            "generate": config.models.generate,
            "judge": config.models.judge,
            "security_scan": config.models.security_scan,
        }

    data["vault"] = {
        "name": config.vault.name,
        "parent_dir": config.vault.parent_dir,
        "create_bootstrap": config.vault.create_bootstrap,
        "create_templates": config.vault.create_templates,
    }

    if config.marketplace.format != "generic":
        data["marketplace"] = {"format": config.marketplace.format}

    if config.security.active_patterns != ("owb-default",):
        data["security"] = {"active_patterns": list(config.security.active_patterns)}

    if config.trust.active_policies != ("owb-default",):
        data["trust"] = {"active_policies": list(config.trust.active_policies)}

    # Only write secrets config if non-default
    if config.secrets.backend != "env":
        secrets_data: dict[str, str] = {"backend": config.secrets.backend}
        if config.secrets.backend == "age" and config.secrets.age_identity != "~/.config/owb/key.txt":
            secrets_data["age_identity"] = config.secrets.age_identity
        if config.secrets.age_secrets_dir:
            secrets_data["age_secrets_dir"] = config.secrets.age_secrets_dir
        if config.secrets.keyring_service != "open-workspace-builder":
            secrets_data["keyring_service"] = config.secrets.keyring_service
        if config.secrets.bitwarden_item != "OWB API Keys":
            secrets_data["bitwarden_item"] = config.secrets.bitwarden_item
        if config.secrets.onepassword_vault != "Development":
            secrets_data["onepassword_vault"] = config.secrets.onepassword_vault
        data["secrets"] = secrets_data

    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(
        yaml.dump(data, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )


# ── Main entry point ────────────────────────────────────────────────────────


def run_setup_wizard(cli_name: str = "owb") -> Config:
    """Run the interactive setup wizard and return the configured Config."""
    click.echo(f"=== {cli_name.upper()} Setup Wizard ===\n")

    paths = _resolve_paths(PathsConfig(), cli_name)
    credentials_dir = Path(paths.credentials_dir)

    # Step 1 — Models
    models, provider = _step_models()

    # Step 2a — Secrets backend
    secrets_cfg = _step_secrets_backend()

    # Step 2b — API key (now uses secrets backend)
    _step_api_key(provider, secrets_cfg)

    # Step 3 — Vault tiers
    vault_tiers = _step_vault_tiers()

    # Step 4 — Marketplace format
    marketplace = _step_marketplace()

    # Step 5 — Security patterns
    security = _step_security_patterns()

    # Step 6 — Trust policy
    trust = _step_trust_policy()

    # Context files notice
    click.echo("\nContext files (about-me.md, brand-voice.md, working-style.md) will be")
    click.echo("created as stubs during the first build. Your assistant will help you")
    click.echo("fill them out on first session. You can also run 'owb context migrate'")
    click.echo("to reformat existing files against the templates.")

    # Build Config
    config = Config(
        models=models,
        marketplace=marketplace,
        security=security,
        trust=trust,
        secrets=secrets_cfg,
        paths=paths,
    )

    # Step 7 — Write config
    config_dir = Path(paths.config_dir)
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "data").mkdir(exist_ok=True)
    credentials_dir.mkdir(parents=True, exist_ok=True)

    config_path = config_dir / "config.yaml"
    _write_config_yaml(config, config_path)

    click.echo(f"\nConfiguration written to {config_path}")
    click.echo(f"Vault tiers: {', '.join(vault_tiers)}")
    if models.classify:
        click.echo(f"Model provider: {provider}")
    click.echo("Setup complete.\n")

    return config
