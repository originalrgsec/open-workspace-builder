"""Tests for vault scanning and config generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from open_workspace_builder.config import Config
from open_workspace_builder.wizard.vault_scan import _detect_vault_tiers, scan_vault


class TestDetectVaultTiers:
    """Tier detection from vault directory structure."""

    def test_empty_vault(self, tmp_path: Path) -> None:
        tiers = _detect_vault_tiers(tmp_path)
        assert tiers == ()

    def test_nonexistent_vault(self, tmp_path: Path) -> None:
        tiers = _detect_vault_tiers(tmp_path / "nope")
        assert tiers == ()

    def test_vault_with_tier_dirs(self, tmp_path: Path) -> None:
        # Create tier dirs with project subdirs containing _index.md
        for tier in ("Work", "Personal"):
            tier_dir = tmp_path / tier
            tier_dir.mkdir()
            proj = tier_dir / "my-project"
            proj.mkdir()
            (proj / "_index.md").write_text("# Index\n", encoding="utf-8")

        tiers = _detect_vault_tiers(tmp_path)
        assert tiers == ("Personal", "Work")  # sorted

    def test_vault_with_status_md(self, tmp_path: Path) -> None:
        tier_dir = tmp_path / "Open Source"
        tier_dir.mkdir()
        proj = tier_dir / "my-oss"
        proj.mkdir()
        (proj / "status.md").write_text("# Status\n", encoding="utf-8")

        tiers = _detect_vault_tiers(tmp_path)
        assert tiers == ("Open Source",)

    def test_ignores_dot_dirs(self, tmp_path: Path) -> None:
        dot_dir = tmp_path / ".obsidian"
        dot_dir.mkdir()
        proj = dot_dir / "something"
        proj.mkdir()
        (proj / "_index.md").write_text("", encoding="utf-8")

        tiers = _detect_vault_tiers(tmp_path)
        assert tiers == ()

    def test_ignores_underscore_dirs(self, tmp_path: Path) -> None:
        under_dir = tmp_path / "_templates"
        under_dir.mkdir()
        proj = under_dir / "something"
        proj.mkdir()
        (proj / "_index.md").write_text("", encoding="utf-8")

        tiers = _detect_vault_tiers(tmp_path)
        assert tiers == ()

    def test_dir_without_projects_ignored(self, tmp_path: Path) -> None:
        # Dir exists but has no subdirs with _index.md or status.md
        (tmp_path / "Empty").mkdir()
        tiers = _detect_vault_tiers(tmp_path)
        assert tiers == ()


class TestScanVault:
    """scan_vault generates a Config from an existing vault."""

    def test_scan_empty_vault(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with patch(
            "open_workspace_builder.wizard.vault_scan._resolve_paths",
            side_effect=lambda p, cli: type(p)(
                config_dir=str(fake_home / f".{cli}"),
                data_dir=str(fake_home / f".{cli}" / "data"),
                credentials_dir=str(fake_home / f".{cli}" / "credentials"),
            ),
        ):
            config = scan_vault(tmp_path, cli_name="owb")

        assert isinstance(config, Config)
        assert config.models.classify == ""  # owb defaults = empty

    def test_scan_vault_with_tiers(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        # Create vault structure
        vault = tmp_path / "vault"
        vault.mkdir()
        for tier in ("Work", "Personal"):
            t = vault / tier
            t.mkdir()
            proj = t / "proj"
            proj.mkdir()
            (proj / "_index.md").write_text("", encoding="utf-8")

        with patch(
            "open_workspace_builder.wizard.vault_scan._resolve_paths",
            side_effect=lambda p, cli: type(p)(
                config_dir=str(fake_home / f".{cli}"),
                data_dir=str(fake_home / f".{cli}" / "data"),
                credentials_dir=str(fake_home / f".{cli}" / "credentials"),
            ),
        ):
            config = scan_vault(vault, cli_name="owb")

        assert isinstance(config, Config)
        config_file = fake_home / ".owb" / "config.yaml"
        assert config_file.exists()

    def test_scan_vault_with_meta(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        vault = tmp_path / "vault"
        vault.mkdir()
        import json

        (vault / "vault-meta.json").write_text(json.dumps({"version": "1.0.0"}), encoding="utf-8")

        with patch(
            "open_workspace_builder.wizard.vault_scan._resolve_paths",
            side_effect=lambda p, cli: type(p)(
                config_dir=str(fake_home / f".{cli}"),
                data_dir=str(fake_home / f".{cli}" / "data"),
                credentials_dir=str(fake_home / f".{cli}" / "credentials"),
            ),
        ):
            config = scan_vault(vault, cli_name="owb")

        assert isinstance(config, Config)


class TestCwbFlavor:
    """CWB init --from-vault applies Claude defaults."""

    def test_cwb_uses_cwb_defaults(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with patch(
            "open_workspace_builder.wizard.vault_scan._resolve_paths",
            side_effect=lambda p, cli: type(p)(
                config_dir=str(fake_home / f".{cli}"),
                data_dir=str(fake_home / f".{cli}" / "data"),
                credentials_dir=str(fake_home / f".{cli}" / "credentials"),
            ),
        ):
            config = scan_vault(tmp_path, cli_name="cwb")

        # CWB models come from CWB config overlay, not hardcoded in OWB core
        assert config.models.classify == ""
        assert config.marketplace.format == "anthropic"

    def test_owb_uses_empty_models(self, tmp_path: Path) -> None:
        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with patch(
            "open_workspace_builder.wizard.vault_scan._resolve_paths",
            side_effect=lambda p, cli: type(p)(
                config_dir=str(fake_home / f".{cli}"),
                data_dir=str(fake_home / f".{cli}" / "data"),
                credentials_dir=str(fake_home / f".{cli}" / "credentials"),
            ),
        ):
            config = scan_vault(tmp_path, cli_name="owb")

        assert config.models.classify == ""
        assert config.marketplace.format == "generic"
