"""Tests for the himitsubako compatibility shim (OWB-S113).

Verifies that:
1. The old import path emits a DeprecationWarning and re-exports himitsubako types.
2. get_backend() returns a himitsubako-backed backend.
3. resolve_key() fallback chain still works with himitsubako backends.
4. SecretsBackend (OWB) is compatible with SecretBackend (himitsubako).
"""

from __future__ import annotations

import warnings
from unittest.mock import MagicMock, patch

import pytest


class TestDeprecationShim:
    """Importing from open_workspace_builder.secrets emits DeprecationWarning."""

    def test_import_emits_deprecation_warning(self) -> None:
        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            # Re-import forces the warning check
            import importlib

            import open_workspace_builder.secrets

            importlib.reload(open_workspace_builder.secrets)
            deprecation_warnings = [x for x in w if issubclass(x.category, DeprecationWarning)]
            assert len(deprecation_warnings) >= 1
            assert "himitsubako" in str(deprecation_warnings[0].message).lower()

    def test_secrets_backend_re_exported(self) -> None:
        from open_workspace_builder.secrets import SecretsBackend

        assert SecretsBackend is not None

    def test_get_backend_re_exported(self) -> None:
        from open_workspace_builder.secrets import get_backend

        assert callable(get_backend)

    def test_resolve_key_re_exported(self) -> None:
        from open_workspace_builder.secrets import resolve_key

        assert callable(resolve_key)


class TestSecretsBackendHimitsubakoCompat:
    """OWB SecretsBackend protocol is satisfied by himitsubako backends."""

    def test_himitsubako_env_backend_satisfies_owb_protocol(self) -> None:
        from himitsubako.backends.env import EnvBackend
        from himitsubako.backends.protocol import SecretBackend

        backend = EnvBackend()
        assert isinstance(backend, SecretBackend)

    def test_himitsubako_sops_backend_has_protocol_methods(self) -> None:
        """SopsBackend has all required protocol methods."""
        from himitsubako.backends.sops import SopsBackend

        assert hasattr(SopsBackend, "get")
        assert hasattr(SopsBackend, "set")
        assert hasattr(SopsBackend, "delete")
        assert hasattr(SopsBackend, "list_keys")
        assert hasattr(SopsBackend, "backend_name")


class TestGetBackendWithHimitsubako:
    """get_backend() routes to himitsubako backends."""

    def test_env_backend_returns_himitsubako_env(self) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets import get_backend

        config = SecretsConfig(backend="env")
        backend = get_backend(config)
        assert backend.backend_name == "env"

    def test_sops_backend_returns_himitsubako_sops(self) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets import get_backend

        config = SecretsConfig(backend="sops")
        # SopsBackend needs sops binary; mock availability
        with patch("himitsubako.backends.sops.SopsBackend.__init__", return_value=None):
            backend = get_backend(config)
            assert backend is not None

    def test_unknown_backend_raises(self) -> None:
        from open_workspace_builder.config import SecretsConfig
        from open_workspace_builder.secrets import get_backend

        config = SecretsConfig(backend="nonexistent")
        with pytest.raises(ValueError, match="Unknown secrets backend"):
            get_backend(config)


class TestResolveKeyWithHimitsubako:
    """resolve_key() works with himitsubako backend instances."""

    def test_cli_override_wins(self) -> None:
        from open_workspace_builder.secrets import resolve_key

        result = resolve_key("api_key", backend=None, cli_override="from-cli")
        assert result == "from-cli"

    def test_backend_value_used(self) -> None:
        from open_workspace_builder.secrets import resolve_key

        mock_backend = MagicMock()
        mock_backend.get.return_value = "from-backend"
        mock_backend.backend_name = "mock"
        result = resolve_key("api_key", backend=mock_backend)
        assert result == "from-backend"

    def test_env_fallback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from open_workspace_builder.secrets import resolve_key

        monkeypatch.setenv("API_KEY", "from-env")
        result = resolve_key("api_key", backend=None)
        assert result == "from-env"

    def test_raises_when_not_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from open_workspace_builder.secrets import resolve_key

        monkeypatch.delenv("API_KEY", raising=False)
        mock_backend = MagicMock()
        mock_backend.get.return_value = None
        mock_backend.backend_name = "mock"
        with pytest.raises(ValueError, match="Could not resolve"):
            resolve_key("api_key", backend=mock_backend)
