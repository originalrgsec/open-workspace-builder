"""Configuration loading with defaults and optional YAML overlay."""

from __future__ import annotations

import sys
import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VaultConfig:
    name: str = "Obsidian"
    parent_dir: str = ""
    assistant_name: str = "AI assistant"
    create_bootstrap: bool = True
    create_templates: bool = True


@dataclass(frozen=True)
class EccConfig:
    enabled: bool = False
    source_dir: str = "vendor/ecc"
    target_dir: str = ".ai"
    agents: tuple[str, ...] = (
        "architect",
        "build-error-resolver",
        "chief-of-staff",
        "code-reviewer",
        "database-reviewer",
        "doc-updater",
        "e2e-runner",
        "go-build-resolver",
        "go-reviewer",
        "harness-optimizer",
        "loop-operator",
        "planner",
        "python-reviewer",
        "refactor-cleaner",
        "security-reviewer",
        "tdd-guide",
    )
    commands: tuple[str, ...] = (
        "build-fix",
        "checkpoint",
        "code-review",
        "e2e",
        "eval",
        "go-build",
        "go-review",
        "go-test",
        "plan",
        "python-review",
        "refactor-clean",
        "tdd",
        "test-coverage",
        "update-docs",
        "verify",
    )
    rules: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: {
            "common": (
                "agents",
                "coding-style",
                "dependency-security",
                "development-workflow",
                "git-workflow",
                "patterns",
                "performance",
                "security",
                "testing",
                "vault-policies",
            ),
            "golang": (
                "coding-style",
                "patterns",
                "security",
                "testing",
            ),
            "python": (
                "coding-style",
                "patterns",
                "security",
                "testing",
            ),
        }
    )


@dataclass(frozen=True)
class SkillsConfig:
    source_dir: str = "content/skills"
    install: tuple[str, ...] = (
        "mobile-inbox-triage",
        "vault-audit",
        "oss-health-check",
        "token-analysis",
    )


@dataclass(frozen=True)
class ContextTemplatesConfig:
    deploy: bool = True
    files: tuple[str, ...] = (
        "about-me.template.md",
        "brand-voice.template.md",
        "working-style.template.md",
    )


@dataclass(frozen=True)
class AgentConfigConfig:
    """Workspace configuration file deployed to the agent config directory."""

    deploy: bool = True
    directory: str = ".ai"
    filename: str = "WORKSPACE.md"


@dataclass(frozen=True)
class ModelsConfig:
    """Per-operation model strings. LiteLLM resolves provider from prefix."""

    classify: str = ""
    generate: str = ""
    judge: str = ""
    security_scan: str = ""


@dataclass(frozen=True)
class SecurityConfig:
    """Security scanner configuration."""

    active_patterns: tuple[str, ...] = ("owb-default",)
    scanner_layers: tuple[int, ...] = (1, 2, 3)
    sca_enabled: bool = True
    sast_enabled: bool = True
    trivy_enabled: bool = False
    secrets_scanner: str = "gitleaks"
    secrets_enabled: bool = False
    trusted_upstream_urls: tuple[str, ...] = ("https://github.com/affaan-m/everything-claude-code",)


@dataclass(frozen=True)
class TrustConfig:
    """Trust tier policy configuration."""

    active_policies: tuple[str, ...] = ("owb-default",)


@dataclass(frozen=True)
class MarketplaceConfig:
    """Marketplace output format."""

    format: str = "generic"


@dataclass(frozen=True)
class SourceEntryConfig:
    """Configuration for a single upstream content source."""

    repo_url: str = ""
    pin: str = ""
    discovery_method: str = "glob"
    patterns: tuple[str, ...] = ("**/SKILL.md",)
    exclude: tuple[str, ...] = ()


@dataclass(frozen=True)
class SourcesConfig:
    """Mapping of source names to their configurations."""

    entries: dict[str, SourceEntryConfig] = field(default_factory=dict)


@dataclass(frozen=True)
class SecretsConfig:
    """Secrets backend configuration (delegates to himitsubako)."""

    backend: str = "env"  # env | sops | keychain | bitwarden
    sops_secrets_file: str = ".secrets.enc.yaml"
    keyring_service: str = "open-workspace-builder"
    bitwarden_item: str = "himitsubako"


@dataclass(frozen=True)
class TokensConfig:
    """Token tracking and budget configuration."""

    ledger_path: str = ""  # empty = derive from paths.data_dir/ledger.jsonl
    budget_threshold: float = 0.0  # monthly budget in dollars, 0 = disabled
    auto_record: bool = False  # enable session-end hook recording


@dataclass(frozen=True)
class StageConfig:
    """Bootstrap stage tracking (PRD stages 0-1)."""

    current_stage: int = 0


@dataclass(frozen=True)
class EnforcementConfig:
    """Policy enforcement configuration."""

    hooks_enabled: bool = False


@dataclass(frozen=True)
class PathsConfig:
    """Directory paths for config, data, and credentials."""

    config_dir: str = ""
    data_dir: str = ""
    credentials_dir: str = ""


@dataclass(frozen=True)
class Config:
    target: str = "output"
    vault: VaultConfig = field(default_factory=VaultConfig)
    ecc: EccConfig = field(default_factory=EccConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    context_templates: ContextTemplatesConfig = field(default_factory=ContextTemplatesConfig)
    agent_config: AgentConfigConfig = field(default_factory=AgentConfigConfig)
    models: ModelsConfig = field(default_factory=ModelsConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)
    trust: TrustConfig = field(default_factory=TrustConfig)
    sources: SourcesConfig = field(default_factory=SourcesConfig)
    marketplace: MarketplaceConfig = field(default_factory=MarketplaceConfig)
    secrets: SecretsConfig = field(default_factory=SecretsConfig)
    tokens: TokensConfig = field(default_factory=TokensConfig)
    stage: StageConfig = field(default_factory=StageConfig)
    enforcement: EnforcementConfig = field(default_factory=EnforcementConfig)
    paths: PathsConfig = field(default_factory=PathsConfig)


# Mapping of section names to their dataclass types for DRY overlay building.
_SECTION_CLASSES: dict[str, type] = {
    "vault": VaultConfig,
    "ecc": EccConfig,
    "skills": SkillsConfig,
    "context_templates": ContextTemplatesConfig,
    "agent_config": AgentConfigConfig,
    "models": ModelsConfig,
    "security": SecurityConfig,
    "trust": TrustConfig,
    "sources": SourcesConfig,
    "marketplace": MarketplaceConfig,
    "secrets": SecretsConfig,
    "tokens": TokensConfig,
    "stage": StageConfig,
    "enforcement": EnforcementConfig,
    "paths": PathsConfig,
}


def _merge_dataclass(cls: type, defaults: Any, overrides: dict[str, Any]) -> Any:
    """Create a new dataclass instance by overlaying overrides on defaults."""
    merged = {}
    for fld in cls.__dataclass_fields__:
        if fld in overrides:
            val = overrides[fld]
            # Convert lists to tuples for frozen dataclasses
            if isinstance(val, list):
                val = tuple(val)
            merged[fld] = val
        else:
            merged[fld] = getattr(defaults, fld)
    return cls(**merged)


def _detect_cli_name() -> str:
    """Detect the CLI tool name from sys.argv[0]."""
    if sys.argv and sys.argv[0]:
        name = Path(sys.argv[0]).name
        if name.endswith("cwb"):
            return "cwb"
    return "owb"


def _resolve_paths(paths: PathsConfig, cli_name: str) -> PathsConfig:
    """Resolve empty PathsConfig fields based on CLI name."""
    config_dir = paths.config_dir or str(Path.home() / f".{cli_name}")
    data_dir = paths.data_dir or str(Path(config_dir) / "data")
    credentials_dir = paths.credentials_dir or str(Path(config_dir) / "credentials")
    return PathsConfig(
        config_dir=config_dir,
        data_dir=data_dir,
        credentials_dir=credentials_dir,
    )


def load_config(
    config_path: str | Path | None = None,
    cli_name: str | None = None,
) -> Config:
    """Load config from optional YAML file, overlaying on defaults.

    Resolution order:
    1. Built-in defaults (dataclass defaults)
    2. User config file (~/.owb/config.yaml or ~/.cwb/config.yaml)
    3. CLI flag (config_path overrides both)

    If PyYAML is not installed, warns and returns defaults.
    """
    if cli_name is None:
        cli_name = _detect_cli_name()

    defaults = Config()

    # Determine which config file to load: explicit path wins, else user config.
    resolved_path: Path | None = None
    if config_path is not None:
        resolved_path = Path(config_path)
        if not resolved_path.exists():
            raise FileNotFoundError(
                f"Config file not found: {resolved_path}. Check the path and try again."
            )
    else:
        user_config = Path.home() / f".{cli_name}" / "config.yaml"
        if user_config.exists():
            resolved_path = user_config

    if resolved_path is None:
        return _with_resolved_paths(defaults, cli_name)

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        warnings.warn(
            "PyYAML not installed. Using default config. Install with: pip install pyyaml",
            stacklevel=2,
        )
        return _with_resolved_paths(defaults, cli_name)

    try:
        raw = yaml.safe_load(resolved_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        raise ValueError(f"Could not parse config file {resolved_path}: {exc}") from exc

    config = _build_config_from_dict(defaults, raw)
    return _with_resolved_paths(config, cli_name)


def _with_resolved_paths(config: Config, cli_name: str) -> Config:
    """Return a new Config with PathsConfig fields resolved."""
    resolved = _resolve_paths(config.paths, cli_name)
    if resolved == config.paths:
        return config
    # Rebuild with resolved paths (frozen dataclass — must reconstruct).
    return Config(
        target=config.target,
        vault=config.vault,
        ecc=config.ecc,
        skills=config.skills,
        context_templates=config.context_templates,
        agent_config=config.agent_config,
        models=config.models,
        security=config.security,
        trust=config.trust,
        sources=config.sources,
        marketplace=config.marketplace,
        secrets=config.secrets,
        tokens=config.tokens,
        stage=config.stage,
        enforcement=config.enforcement,
        paths=resolved,
    )


_SECTION_ALIASES: dict[str, str] = {
    "claude_md": "agent_config",
}


def _build_config_from_dict(defaults: Config, raw: dict[str, Any]) -> Config:
    """Build a Config from raw dict, overlaying on defaults."""
    # Apply backward-compatible aliases before processing.
    for alias, canonical in _SECTION_ALIASES.items():
        if alias in raw and canonical not in raw:
            raw[canonical] = raw.pop(alias)

    sections: dict[str, Any] = {}
    for section_name, cls in _SECTION_CLASSES.items():
        default_val = getattr(defaults, section_name)
        if section_name in raw:
            if section_name == "sources":
                sections[section_name] = _build_sources_config(raw[section_name])
            else:
                sections[section_name] = _merge_dataclass(cls, default_val, raw[section_name])
        else:
            sections[section_name] = default_val

    return Config(
        target=raw.get("target", defaults.target),
        **sections,
    )


def _build_sources_config(raw_sources: dict[str, Any]) -> SourcesConfig:
    """Build SourcesConfig from raw YAML dict of source entries."""
    entries: dict[str, SourceEntryConfig] = {}
    for name, entry_raw in raw_sources.items():
        if not isinstance(entry_raw, dict):
            continue
        defaults = SourceEntryConfig()
        entries[name] = _merge_dataclass(SourceEntryConfig, defaults, entry_raw)
    return SourcesConfig(entries=entries)
