"""Tests for config overlay resolution, CLI name detection, and new config sections."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from open_workspace_builder.config import (
    Config,
    MarketplaceConfig,
    ModelsConfig,
    PathsConfig,
    SecurityConfig,
    TrustConfig,
    _detect_cli_name,
    _resolve_paths,
    load_config,
)


# ---------------------------------------------------------------------------
# New dataclass defaults
# ---------------------------------------------------------------------------


class TestNewSectionDefaults:
    """All new config sections have correct defaults."""

    def test_models_defaults(self) -> None:
        m = ModelsConfig()
        assert m.classify == ""
        assert m.generate == ""
        assert m.judge == ""
        assert m.security_scan == ""

    def test_security_defaults(self) -> None:
        s = SecurityConfig()
        assert s.active_patterns == ("owb-default",)
        assert s.scanner_layers == (1, 2, 3)

    def test_trust_defaults(self) -> None:
        t = TrustConfig()
        assert t.active_policies == ("owb-default",)

    def test_marketplace_defaults(self) -> None:
        m = MarketplaceConfig()
        assert m.format == "generic"

    def test_paths_defaults(self) -> None:
        p = PathsConfig()
        assert p.config_dir == ""
        assert p.data_dir == ""
        assert p.credentials_dir == ""

    def test_config_includes_new_sections(self) -> None:
        config = Config()
        assert isinstance(config.models, ModelsConfig)
        assert isinstance(config.security, SecurityConfig)
        assert isinstance(config.trust, TrustConfig)
        assert isinstance(config.marketplace, MarketplaceConfig)
        assert isinstance(config.paths, PathsConfig)

    def test_new_sections_are_frozen(self) -> None:
        with pytest.raises(AttributeError):
            ModelsConfig().classify = "x"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            SecurityConfig().active_patterns = ()  # type: ignore[misc]
        with pytest.raises(AttributeError):
            TrustConfig().active_policies = ()  # type: ignore[misc]
        with pytest.raises(AttributeError):
            MarketplaceConfig().format = "x"  # type: ignore[misc]
        with pytest.raises(AttributeError):
            PathsConfig().config_dir = "x"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# CLI name detection
# ---------------------------------------------------------------------------


class TestCliNameDetection:
    """CLI name detection from sys.argv[0]."""

    def test_detects_owb(self) -> None:
        with patch("open_workspace_builder.config.sys") as mock_sys:
            mock_sys.argv = ["/usr/local/bin/owb"]
            assert _detect_cli_name() == "owb"

    def test_detects_cwb(self) -> None:
        with patch("open_workspace_builder.config.sys") as mock_sys:
            mock_sys.argv = ["/usr/local/bin/cwb"]
            assert _detect_cli_name() == "cwb"

    def test_detects_owb_from_python_m(self) -> None:
        with patch("open_workspace_builder.config.sys") as mock_sys:
            mock_sys.argv = ["some_script.py"]
            assert _detect_cli_name() == "owb"

    def test_empty_argv_defaults_to_owb(self) -> None:
        with patch("open_workspace_builder.config.sys") as mock_sys:
            mock_sys.argv = [""]
            assert _detect_cli_name() == "owb"

    def test_no_argv_defaults_to_owb(self) -> None:
        with patch("open_workspace_builder.config.sys") as mock_sys:
            mock_sys.argv = []
            assert _detect_cli_name() == "owb"


# ---------------------------------------------------------------------------
# PathsConfig resolution
# ---------------------------------------------------------------------------


class TestPathsResolution:
    """PathsConfig runtime resolution from empty defaults."""

    def test_resolves_owb_paths(self) -> None:
        resolved = _resolve_paths(PathsConfig(), "owb")
        home = str(Path.home())
        assert resolved.config_dir == f"{home}/.owb"
        assert resolved.data_dir == f"{home}/.owb/data"
        assert resolved.credentials_dir == f"{home}/.owb/credentials"

    def test_resolves_cwb_paths(self) -> None:
        resolved = _resolve_paths(PathsConfig(), "cwb")
        home = str(Path.home())
        assert resolved.config_dir == f"{home}/.cwb"
        assert resolved.data_dir == f"{home}/.cwb/data"
        assert resolved.credentials_dir == f"{home}/.cwb/credentials"

    def test_explicit_config_dir_overrides(self) -> None:
        p = PathsConfig(config_dir="/custom/dir")
        resolved = _resolve_paths(p, "owb")
        assert resolved.config_dir == "/custom/dir"
        assert resolved.data_dir == "/custom/dir/data"
        assert resolved.credentials_dir == "/custom/dir/credentials"

    def test_all_explicit_paths_preserved(self) -> None:
        p = PathsConfig(
            config_dir="/a",
            data_dir="/b",
            credentials_dir="/c",
        )
        resolved = _resolve_paths(p, "owb")
        assert resolved.config_dir == "/a"
        assert resolved.data_dir == "/b"
        assert resolved.credentials_dir == "/c"

    def test_load_config_resolves_paths(self) -> None:
        config = load_config(cli_name="owb")
        home = str(Path.home())
        assert config.paths.config_dir == f"{home}/.owb"


# ---------------------------------------------------------------------------
# Config overlay precedence
# ---------------------------------------------------------------------------


class TestOverlayPrecedence:
    """Config overlay: defaults < user file < CLI flag."""

    def test_defaults_when_no_files(self) -> None:
        config = load_config(cli_name="owb")
        assert config.target == "output"
        assert config.models.classify == ""
        assert config.security.scanner_layers == (1, 2, 3)

    def test_user_file_overrides_defaults(self, tmp_path: Path) -> None:
        user_dir = tmp_path / ".owb"
        user_dir.mkdir()
        user_config = user_dir / "config.yaml"
        user_config.write_text(
            "target: from-user-file\nmodels:\n  classify: anthropic/claude-haiku-3\n",
            encoding="utf-8",
        )
        with patch("open_workspace_builder.config.Path.home", return_value=tmp_path):
            config = load_config(cli_name="owb")
        assert config.target == "from-user-file"
        assert config.models.classify == "anthropic/claude-haiku-3"
        # Unspecified sections keep defaults
        assert config.vault.name == "Obsidian"

    def test_cli_flag_overrides_user_file(self, tmp_path: Path) -> None:
        # Set up user file
        user_dir = tmp_path / ".owb"
        user_dir.mkdir()
        user_config = user_dir / "config.yaml"
        user_config.write_text("target: from-user-file\n", encoding="utf-8")

        # Set up CLI-specified file
        cli_config = tmp_path / "cli.yaml"
        cli_config.write_text("target: from-cli-flag\n", encoding="utf-8")

        with patch("open_workspace_builder.config.Path.home", return_value=tmp_path):
            config = load_config(config_path=cli_config, cli_name="owb")
        assert config.target == "from-cli-flag"

    def test_cwb_user_file_location(self, tmp_path: Path) -> None:
        user_dir = tmp_path / ".cwb"
        user_dir.mkdir()
        user_config = user_dir / "config.yaml"
        user_config.write_text("target: cwb-target\n", encoding="utf-8")

        with patch("open_workspace_builder.config.Path.home", return_value=tmp_path):
            config = load_config(cli_name="cwb")
        assert config.target == "cwb-target"


# ---------------------------------------------------------------------------
# Merge for new sections
# ---------------------------------------------------------------------------


class TestMergeNewSections:
    """_merge_dataclass works for all new sections via YAML overlay."""

    def test_models_overlay(self, tmp_path: Path) -> None:
        cfg = tmp_path / "c.yaml"
        cfg.write_text(
            "models:\n  classify: openai/gpt-4o\n  generate: anthropic/claude-sonnet-4-20250514\n",
            encoding="utf-8",
        )
        config = load_config(cfg, cli_name="owb")
        assert config.models.classify == "openai/gpt-4o"
        assert config.models.generate == "anthropic/claude-sonnet-4-20250514"
        assert config.models.judge == ""

    def test_security_overlay(self, tmp_path: Path) -> None:
        cfg = tmp_path / "c.yaml"
        cfg.write_text(
            "security:\n  scanner_layers: [1, 2]\n  active_patterns:\n    - custom-patterns\n",
            encoding="utf-8",
        )
        config = load_config(cfg, cli_name="owb")
        assert config.security.scanner_layers == (1, 2)
        assert config.security.active_patterns == ("custom-patterns",)

    def test_trust_overlay(self, tmp_path: Path) -> None:
        cfg = tmp_path / "c.yaml"
        cfg.write_text(
            "trust:\n  active_policies:\n    - strict\n    - cwb-enterprise\n",
            encoding="utf-8",
        )
        config = load_config(cfg, cli_name="owb")
        assert config.trust.active_policies == ("strict", "cwb-enterprise")

    def test_marketplace_overlay(self, tmp_path: Path) -> None:
        cfg = tmp_path / "c.yaml"
        cfg.write_text("marketplace:\n  format: vscode\n", encoding="utf-8")
        config = load_config(cfg, cli_name="owb")
        assert config.marketplace.format == "vscode"

    def test_paths_overlay(self, tmp_path: Path) -> None:
        cfg = tmp_path / "c.yaml"
        cfg.write_text("paths:\n  config_dir: /opt/owb\n", encoding="utf-8")
        config = load_config(cfg, cli_name="owb")
        assert config.paths.config_dir == "/opt/owb"
        assert config.paths.data_dir == "/opt/owb/data"


# ---------------------------------------------------------------------------
# Schema fallback on malformed YAML
# ---------------------------------------------------------------------------


class TestMalformedYaml:
    """Malformed YAML produces warning and falls back to defaults."""

    def test_malformed_yaml_returns_defaults(self, tmp_path: Path) -> None:
        cfg = tmp_path / "bad.yaml"
        cfg.write_text("{{invalid yaml: [", encoding="utf-8")
        with pytest.warns(UserWarning, match="Could not load config file"):
            config = load_config(cfg, cli_name="owb")
        assert config.target == "output"
        assert isinstance(config.models, ModelsConfig)


# ---------------------------------------------------------------------------
# SecurityConfig flows to Scanner
# ---------------------------------------------------------------------------


class TestScannerSecurityConfig:
    """Scanner accepts and uses SecurityConfig."""

    def test_scanner_uses_security_config_layers(self) -> None:
        from open_workspace_builder.security.scanner import Scanner

        sc = SecurityConfig(scanner_layers=(1, 2))
        scanner = Scanner(security_config=sc)
        assert scanner._layers == (1, 2)

    def test_scanner_explicit_layers_override_config(self) -> None:
        from open_workspace_builder.security.scanner import Scanner

        sc = SecurityConfig(scanner_layers=(1, 2))
        scanner = Scanner(layers=(1,), security_config=sc)
        assert scanner._layers == (1,)

    def test_scanner_default_without_config(self) -> None:
        from open_workspace_builder.security.scanner import Scanner

        scanner = Scanner()
        assert scanner._layers == (1, 2, 3)
