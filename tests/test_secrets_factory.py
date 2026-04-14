"""OWB-S132: Factory plumbs custom SOPS paths into SopsBackend.

Tests AC-3, EC-1, EC-2, EC-3 from the story. The factory lives at
``src/open_workspace_builder/secrets/factory.py``. It routes
``SecretsConfig`` fields into ``himitsubako.backends.sops.SopsBackend``
kwargs. himitsubako 0.7.0 (HMB-S031) added ``age_identity`` and
``sops_config_file`` kwargs that were previously missing.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest


class TestSopsBackendPlumbing:
    """AC-3: Factory passes new fields to SopsBackend as kwargs."""

    def test_sops_backend_receives_age_identity(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        key = tmp_path / "age.txt"
        key.write_text("# dummy", encoding="utf-8")
        cfg = SecretsConfig(
            backend="sops",
            sops_age_identity=str(key),
        )
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        kwargs = init.call_args.kwargs
        assert kwargs["age_identity"] == str(key)

    def test_sops_backend_receives_config_file(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        cfg_file = tmp_path / ".sops.yaml"
        cfg_file.write_text("creation_rules: []\n", encoding="utf-8")
        cfg = SecretsConfig(
            backend="sops",
            sops_config_file=str(cfg_file),
        )
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        kwargs = init.call_args.kwargs
        assert kwargs["sops_config_file"] == str(cfg_file)

    def test_sops_backend_receives_secrets_file_unchanged(self) -> None:
        """Existing behavior: secrets_file still routed when other fields unset."""
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        cfg = SecretsConfig(
            backend="sops",
            sops_secrets_file="custom.enc.yaml",
        )
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        kwargs = init.call_args.kwargs
        assert kwargs["secrets_file"] == "custom.enc.yaml"

    def test_sops_backend_omits_unset_fields(self) -> None:
        """When sops_age_identity / sops_config_file are unset, pass None
        (preserves upstream defaults)."""
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        cfg = SecretsConfig(backend="sops")
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        kwargs = init.call_args.kwargs
        assert kwargs.get("age_identity") is None
        assert kwargs.get("sops_config_file") is None


class TestSopsPathExpansion:
    """EC-1: ~ and absolute paths are normalized before the kwarg is passed."""

    def test_home_expansion_age_identity(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Use a fake HOME so ~/age-key.txt maps to an existing tmp file."""
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        monkeypatch.setenv("HOME", str(tmp_path))
        key = tmp_path / "age-key.txt"
        key.write_text("# dummy", encoding="utf-8")
        cfg = SecretsConfig(
            backend="sops",
            sops_age_identity="~/age-key.txt",
        )
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        passed = init.call_args.kwargs["age_identity"]
        assert "~" not in passed
        assert passed == str(key)

    def test_home_expansion_config_file(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        monkeypatch.setenv("HOME", str(tmp_path))
        cfg_file = tmp_path / ".sops.yaml"
        cfg_file.write_text("creation_rules: []\n", encoding="utf-8")
        cfg = SecretsConfig(
            backend="sops",
            sops_config_file="~/.sops.yaml",
        )
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        passed = init.call_args.kwargs["sops_config_file"]
        assert "~" not in passed
        assert passed == str(cfg_file)

    def test_absolute_path_passes_through(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        key = tmp_path / "key.txt"
        key.write_text("# dummy", encoding="utf-8")
        cfg = SecretsConfig(
            backend="sops",
            sops_age_identity=str(key),
        )
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        assert init.call_args.kwargs["age_identity"] == str(key)


class TestSopsEnvVarFallback:
    """EC-2: When config is unset, env var behavior is preserved."""

    def test_no_config_override_when_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """If sops_age_identity is not set, OWB should not pass any
        age_identity kwarg value that would override the env var the
        user may have set (himitsubako reads SOPS_AGE_KEY_FILE directly
        when age_identity is None)."""
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        monkeypatch.setenv("SOPS_AGE_KEY_FILE", "/user/shell/path.txt")
        cfg = SecretsConfig(backend="sops")
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        assert init.call_args.kwargs.get("age_identity") is None


class TestSopsMissingIdentity:
    """EC-3: Configured-but-missing age_identity file fails loudly."""

    def test_missing_configured_age_identity_raises(self, tmp_path: Path) -> None:
        """If sops_age_identity points at a non-existent file, the factory
        should surface a clear error rather than silently fall back."""
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        missing = tmp_path / "does-not-exist.txt"
        cfg = SecretsConfig(
            backend="sops",
            sops_age_identity=str(missing),
        )
        with pytest.raises(FileNotFoundError, match="sops_age_identity"):
            get_backend(cfg)

    def test_missing_configured_config_file_raises(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        missing = tmp_path / "does-not-exist.sops.yaml"
        cfg = SecretsConfig(
            backend="sops",
            sops_config_file=str(missing),
        )
        with pytest.raises(FileNotFoundError, match="sops_config_file"):
            get_backend(cfg)

    def test_existing_age_identity_passes(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets.factory import get_backend

        key = tmp_path / "age.txt"
        key.write_text("# dummy", encoding="utf-8")
        cfg = SecretsConfig(
            backend="sops",
            sops_age_identity=str(key),
        )
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None) as init:
            get_backend(cfg)
        assert init.call_args.kwargs["age_identity"] == str(key)
