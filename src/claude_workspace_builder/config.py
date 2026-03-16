"""Configuration loading with defaults and optional YAML overlay."""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class VaultConfig:
    name: str = "Obsidian"
    parent_dir: str = "Claude Context"
    create_bootstrap: bool = True
    create_templates: bool = True


@dataclass(frozen=True)
class EccConfig:
    source_dir: str = "vendor/ecc"
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
    rules: dict[str, tuple[str, ...]] = field(default_factory=lambda: {
        "common": (
            "agents",
            "coding-style",
            "development-workflow",
            "git-workflow",
            "patterns",
            "performance",
            "security",
            "testing",
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
    })


@dataclass(frozen=True)
class SkillsConfig:
    source_dir: str = "content/skills"
    install: tuple[str, ...] = (
        "mobile-inbox-triage",
        "vault-audit",
        "oss-health-check",
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
class ClaudeMdConfig:
    deploy: bool = True


@dataclass(frozen=True)
class Config:
    target: str = "output"
    vault: VaultConfig = field(default_factory=VaultConfig)
    ecc: EccConfig = field(default_factory=EccConfig)
    skills: SkillsConfig = field(default_factory=SkillsConfig)
    context_templates: ContextTemplatesConfig = field(default_factory=ContextTemplatesConfig)
    claude_md: ClaudeMdConfig = field(default_factory=ClaudeMdConfig)


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


def load_config(config_path: str | Path | None = None) -> Config:
    """Load config from optional YAML file, overlaying on defaults.

    If PyYAML is not installed, warns and returns defaults.
    """
    defaults = Config()

    if config_path is None:
        return defaults

    config_path = Path(config_path)
    if not config_path.exists():
        return defaults

    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        warnings.warn(
            "PyYAML not installed. Using default config. Install with: pip install pyyaml",
            stacklevel=2,
        )
        return defaults

    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    except Exception as exc:
        warnings.warn(f"Could not load config file: {exc}", stacklevel=2)
        return defaults

    return _build_config_from_dict(defaults, raw)


def _build_config_from_dict(defaults: Config, raw: dict[str, Any]) -> Config:
    """Build a Config from raw dict, overlaying on defaults."""
    vault = (
        _merge_dataclass(VaultConfig, defaults.vault, raw["vault"])
        if "vault" in raw
        else defaults.vault
    )
    ecc = (
        _merge_dataclass(EccConfig, defaults.ecc, raw["ecc"])
        if "ecc" in raw
        else defaults.ecc
    )
    skills = (
        _merge_dataclass(SkillsConfig, defaults.skills, raw["skills"])
        if "skills" in raw
        else defaults.skills
    )
    context_templates = (
        _merge_dataclass(
            ContextTemplatesConfig,
            defaults.context_templates,
            raw["context_templates"],
        )
        if "context_templates" in raw
        else defaults.context_templates
    )
    claude_md = (
        _merge_dataclass(ClaudeMdConfig, defaults.claude_md, raw["claude_md"])
        if "claude_md" in raw
        else defaults.claude_md
    )

    return Config(
        target=raw.get("target", defaults.target),
        vault=vault,
        ecc=ecc,
        skills=skills,
        context_templates=context_templates,
        claude_md=claude_md,
    )
