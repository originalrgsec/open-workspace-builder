"""Tests for config loading with defaults, YAML overlay, and partial YAML."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.config import Config, VaultConfig, load_config


class TestLoadConfigDefaults:
    """Config loading without a YAML file returns sensible defaults."""

    def test_returns_config_instance(self) -> None:
        config = load_config()
        assert isinstance(config, Config)

    def test_default_target(self) -> None:
        config = load_config()
        assert config.target == "output"

    def test_default_vault_name(self) -> None:
        config = load_config()
        assert config.vault.name == "Obsidian"

    def test_default_ecc_agents_nonempty(self) -> None:
        config = load_config()
        assert len(config.ecc.agents) > 0

    def test_default_skills_install_nonempty(self) -> None:
        config = load_config()
        assert len(config.skills.install) > 0

    def test_default_context_templates_deploy(self) -> None:
        config = load_config()
        assert config.context_templates.deploy is True

    def test_none_path_returns_defaults(self) -> None:
        config = load_config(None)
        assert config.target == "output"

    def test_nonexistent_path_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            load_config(tmp_path / "nope.yaml")


class TestLoadConfigWithYaml:
    """Config loading with a full YAML file overlays on defaults."""

    def test_yaml_overrides_target(self, sample_yaml_config: Path) -> None:
        config = load_config(sample_yaml_config)
        assert config.target == "custom-output"

    def test_yaml_overrides_vault_name(self, sample_yaml_config: Path) -> None:
        config = load_config(sample_yaml_config)
        assert config.vault.name == "TestVault"

    def test_yaml_overrides_create_templates(self, sample_yaml_config: Path) -> None:
        config = load_config(sample_yaml_config)
        assert config.vault.create_templates is False

    def test_unspecified_fields_keep_defaults(self, sample_yaml_config: Path) -> None:
        config = load_config(sample_yaml_config)
        # parent_dir not in YAML, should keep default
        assert config.vault.parent_dir == ""
        # ecc not in YAML, should keep all defaults
        assert len(config.ecc.agents) > 0


class TestLoadConfigPartialYaml:
    """Config loading with partial YAML preserves unspecified defaults."""

    def test_only_target(self, tmp_path: Path) -> None:
        cfg = tmp_path / "partial.yaml"
        cfg.write_text("target: my-output\n", encoding="utf-8")
        config = load_config(cfg)
        assert config.target == "my-output"
        assert config.vault.name == "Obsidian"

    def test_only_vault_partial(self, tmp_path: Path) -> None:
        cfg = tmp_path / "partial.yaml"
        cfg.write_text("vault:\n  name: CustomVault\n", encoding="utf-8")
        config = load_config(cfg)
        assert config.vault.name == "CustomVault"
        assert config.vault.parent_dir == ""
        assert config.vault.create_bootstrap is True

    def test_empty_yaml(self, tmp_path: Path) -> None:
        cfg = tmp_path / "empty.yaml"
        cfg.write_text("", encoding="utf-8")
        config = load_config(cfg)
        assert config.target == "output"


class TestConfigImmutability:
    """Config dataclasses are frozen."""

    def test_config_is_frozen(self) -> None:
        config = Config()
        with pytest.raises(AttributeError):
            config.target = "changed"  # type: ignore[misc]

    def test_vault_config_is_frozen(self) -> None:
        vault = VaultConfig()
        with pytest.raises(AttributeError):
            vault.name = "changed"  # type: ignore[misc]
