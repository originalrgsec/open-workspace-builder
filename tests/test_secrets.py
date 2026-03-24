"""Tests for pluggable secrets backend infrastructure."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.secrets.base import SecretsBackend
from open_workspace_builder.secrets.env_backend import EnvVarBackend
from open_workspace_builder.secrets.factory import get_backend
from open_workspace_builder.secrets.resolver import resolve_key


# ── Protocol conformance ──────────────────────────────────────────────────


class TestSecretsBackendProtocol:
    def test_env_backend_satisfies_protocol(self) -> None:
        assert isinstance(EnvVarBackend(), SecretsBackend)

    def test_mock_satisfies_protocol(self) -> None:
        mock = MagicMock(spec=SecretsBackend)
        assert isinstance(mock, SecretsBackend)


# ── EnvVarBackend ─────────────────────────────────────────────────────────


class TestEnvVarBackend:
    def test_get_returns_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "secret123")
        assert EnvVarBackend().get("MY_KEY") == "secret123"

    def test_get_returns_none_for_missing(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("NONEXISTENT_KEY", raising=False)
        assert EnvVarBackend().get("NONEXISTENT_KEY") is None

    def test_set_stores_in_environ(self) -> None:
        backend = EnvVarBackend()
        backend.set("_OWB_TEST_SET", "val")
        assert os.environ.get("_OWB_TEST_SET") == "val"
        os.environ.pop("_OWB_TEST_SET", None)

    def test_delete_removes_from_environ(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("_OWB_TEST_DEL", "val")
        backend = EnvVarBackend()
        backend.delete("_OWB_TEST_DEL")
        assert "_OWB_TEST_DEL" not in os.environ

    def test_delete_noop_for_missing(self) -> None:
        EnvVarBackend().delete("_DEFINITELY_NOT_SET_123456")

    def test_list_keys_includes_set_known_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
        keys = EnvVarBackend().list_keys()
        assert "ANTHROPIC_API_KEY" in keys

    def test_list_keys_excludes_unset_known_keys(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        keys = EnvVarBackend().list_keys()
        assert "OPENAI_API_KEY" not in keys

    def test_backend_name(self) -> None:
        assert EnvVarBackend().backend_name() == "env"


# ── KeyringBackend ────────────────────────────────────────────────────────


class TestKeyringBackend:
    def _make_mock_keyring(self) -> MagicMock:
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = None
        return mock_kr

    def test_get_calls_keyring(self) -> None:
        mock_kr = self._make_mock_keyring()
        mock_kr.get_password.return_value = "secret"
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            backend = KeyringBackend()
            assert backend.get("MY_KEY") == "secret"
            mock_kr.get_password.assert_called_with("open-workspace-builder", "MY_KEY")

    def test_set_calls_keyring_and_updates_metadata(self) -> None:
        mock_kr = self._make_mock_keyring()
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            backend = KeyringBackend()
            backend.set("NEW_KEY", "value")
            mock_kr.set_password.assert_any_call("open-workspace-builder", "NEW_KEY", "value")

    def test_delete_calls_keyring(self) -> None:
        mock_kr = self._make_mock_keyring()
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            backend = KeyringBackend()
            backend.delete("OLD_KEY")
            mock_kr.delete_password.assert_called_with("open-workspace-builder", "OLD_KEY")

    def test_list_keys_reads_metadata(self) -> None:
        mock_kr = self._make_mock_keyring()
        mock_kr.get_password.side_effect = lambda svc, key: (
            json.dumps(["KEY_A", "KEY_B"]) if key == "_owb_keys" else None
        )
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            backend = KeyringBackend()
            assert backend.list_keys() == ["KEY_A", "KEY_B"]

    def test_list_keys_empty_when_no_metadata(self) -> None:
        mock_kr = self._make_mock_keyring()
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            assert KeyringBackend().list_keys() == []

    def test_backend_name(self) -> None:
        mock_kr = self._make_mock_keyring()
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            assert KeyringBackend().backend_name() == "keyring"

    def test_custom_service_name(self) -> None:
        mock_kr = self._make_mock_keyring()
        mock_kr.get_password.return_value = "val"
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            backend = KeyringBackend(service="custom-svc")
            backend.get("K")
            mock_kr.get_password.assert_called_with("custom-svc", "K")

    def test_is_available_true(self) -> None:
        mock_backend = MagicMock()
        type(mock_backend).__module__ = "keyring.backends.SecretService"
        mock_kr = MagicMock()
        mock_kr.get_keyring.return_value = mock_backend
        with patch.dict("sys.modules", {"keyring": mock_kr}):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            assert KeyringBackend.is_available() is True

    def test_is_available_false_for_fail_backend(self) -> None:
        mock_backend = MagicMock()
        type(mock_backend).__module__ = "keyring.backends.fail"
        mock_kr = MagicMock()
        mock_kr.get_keyring.return_value = mock_backend
        with patch.dict("sys.modules", {"keyring": mock_kr}):
            from open_workspace_builder.secrets.keyring_backend import KeyringBackend

            assert KeyringBackend.is_available() is False

    def test_import_error_gives_instructions(self) -> None:
        with patch.dict("sys.modules", {"keyring": None}):
            with pytest.raises(ImportError, match="keyring package is required"):
                from open_workspace_builder.secrets.keyring_backend import _import_keyring

                _import_keyring()


# ── AgeBackend ────────────────────────────────────────────────────────────


class TestAgeBackend:
    def test_get_returns_none_when_file_missing(self, tmp_path: Path) -> None:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        backend = AgeBackend(
            identity_path=str(tmp_path / "key.txt"),
            secrets_dir=str(tmp_path / "secrets"),
        )
        assert backend.get("nonexistent") is None

    def test_list_keys_empty_when_dir_missing(self, tmp_path: Path) -> None:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        backend = AgeBackend(
            identity_path=str(tmp_path / "key.txt"),
            secrets_dir=str(tmp_path / "no-such-dir"),
        )
        assert backend.list_keys() == []

    def test_list_keys_finds_age_files(self, tmp_path: Path) -> None:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        (secrets_dir / "KEY_A.age").write_bytes(b"encrypted")
        (secrets_dir / "KEY_B.age").write_bytes(b"encrypted")
        (secrets_dir / "not_a_key.txt").write_text("ignore")

        backend = AgeBackend(
            identity_path=str(tmp_path / "key.txt"),
            secrets_dir=str(secrets_dir),
        )
        assert backend.list_keys() == ["KEY_A", "KEY_B"]

    def test_delete_removes_file(self, tmp_path: Path) -> None:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        secrets_dir = tmp_path / "secrets"
        secrets_dir.mkdir()
        age_file = secrets_dir / "MY_KEY.age"
        age_file.write_bytes(b"encrypted")

        backend = AgeBackend(
            identity_path=str(tmp_path / "key.txt"),
            secrets_dir=str(secrets_dir),
        )
        backend.delete("MY_KEY")
        assert not age_file.exists()

    def test_delete_noop_when_missing(self, tmp_path: Path) -> None:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        backend = AgeBackend(
            identity_path=str(tmp_path / "key.txt"),
            secrets_dir=str(tmp_path / "secrets"),
        )
        backend.delete("nonexistent")  # should not raise

    def test_backend_name(self, tmp_path: Path) -> None:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        backend = AgeBackend(
            identity_path=str(tmp_path / "key.txt"),
            secrets_dir=str(tmp_path / "secrets"),
        )
        assert backend.backend_name() == "age"

    def test_is_available_with_pyrage(self) -> None:
        mock_pyrage = MagicMock()
        with patch("open_workspace_builder.secrets.age_backend._try_import_pyrage", return_value=mock_pyrage):
            from open_workspace_builder.secrets.age_backend import AgeBackend

            assert AgeBackend.is_available() is True

    def test_is_available_with_age_cli(self) -> None:
        with patch("open_workspace_builder.secrets.age_backend._try_import_pyrage", return_value=None):
            with patch("shutil.which", return_value="/usr/bin/age"):
                from open_workspace_builder.secrets.age_backend import AgeBackend

                assert AgeBackend.is_available() is True

    def test_is_available_false_when_nothing(self) -> None:
        with patch("open_workspace_builder.secrets.age_backend._try_import_pyrage", return_value=None):
            with patch("shutil.which", return_value=None):
                from open_workspace_builder.secrets.age_backend import AgeBackend

                assert AgeBackend.is_available() is False

    def test_ensure_identity_generates_with_pyrage(self, tmp_path: Path) -> None:
        mock_pyrage = MagicMock()
        mock_identity = MagicMock()
        mock_identity.__str__ = lambda _: "AGE-SECRET-KEY-1FAKE\n# public key: age1fakepubkey"
        mock_pyrage.x25519.Identity.generate.return_value = mock_identity

        with patch("open_workspace_builder.secrets.age_backend._try_import_pyrage", return_value=mock_pyrage):
            from open_workspace_builder.secrets.age_backend import AgeBackend

            identity_path = tmp_path / "key.txt"
            backend = AgeBackend(
                identity_path=str(identity_path),
                secrets_dir=str(tmp_path / "secrets"),
            )
            backend._ensure_identity()
            assert identity_path.is_file()
            assert identity_path.stat().st_mode & 0o777 == stat.S_IRUSR | stat.S_IWUSR

    def test_ensure_identity_skips_if_exists(self, tmp_path: Path) -> None:
        from open_workspace_builder.secrets.age_backend import AgeBackend

        identity_path = tmp_path / "key.txt"
        identity_path.write_text("existing key")

        backend = AgeBackend(
            identity_path=str(identity_path),
            secrets_dir=str(tmp_path / "secrets"),
        )
        backend._ensure_identity()
        assert identity_path.read_text() == "existing key"

    def test_set_creates_secrets_dir(self, tmp_path: Path) -> None:
        mock_pyrage = MagicMock()
        mock_identity = MagicMock()
        mock_identity.__str__ = lambda _: "AGE-SECRET-KEY-1FAKE\n# public key: age1fakepubkey"
        mock_pyrage.x25519.Identity.generate.return_value = mock_identity
        mock_pyrage.x25519.Recipient.from_str.return_value = MagicMock()
        mock_pyrage.encrypt.return_value = b"encrypted"

        with patch("open_workspace_builder.secrets.age_backend._try_import_pyrage", return_value=mock_pyrage):
            from open_workspace_builder.secrets.age_backend import AgeBackend

            secrets_dir = tmp_path / "new_secrets"
            backend = AgeBackend(
                identity_path=str(tmp_path / "key.txt"),
                secrets_dir=str(secrets_dir),
            )
            backend.set("MY_KEY", "secret_value")
            assert secrets_dir.is_dir()
            assert (secrets_dir / "MY_KEY.age").is_file()


# ── resolve_key ───────────────────────────────────────────────────────────


class TestResolveKey:
    def test_cli_override_wins(self) -> None:
        backend = MagicMock()
        backend.get.return_value = "backend_value"
        result = resolve_key("my_key", backend, cli_override="cli_value")
        assert result == "cli_value"
        backend.get.assert_not_called()

    def test_backend_used_when_no_cli(self) -> None:
        backend = MagicMock()
        backend.get.return_value = "backend_value"
        backend.backend_name.return_value = "mock"
        result = resolve_key("my_key", backend)
        assert result == "backend_value"

    def test_env_var_used_when_no_backend_value(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "env_value")
        backend = MagicMock()
        backend.get.return_value = None
        backend.backend_name.return_value = "mock"
        result = resolve_key("my_key", backend, env_var="MY_KEY")
        assert result == "env_value"

    def test_env_var_derived_from_key_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("MY_KEY", "derived_env")
        result = resolve_key("my_key", None)
        assert result == "derived_env"

    def test_error_when_nothing_found(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_KEY", raising=False)
        with pytest.raises(ValueError, match="Could not resolve key"):
            resolve_key("missing_key", None)

    def test_none_backend_skips_backend_step(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("FALLBACK_KEY", "fallback")
        result = resolve_key("fallback_key", None, env_var="FALLBACK_KEY")
        assert result == "fallback"

    def test_empty_cli_override_falls_through(self) -> None:
        backend = MagicMock()
        backend.get.return_value = "backend_val"
        backend.backend_name.return_value = "mock"
        result = resolve_key("k", backend, cli_override="  ")
        assert result == "backend_val"

    def test_empty_backend_value_falls_through(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("K", "env_val")
        backend = MagicMock()
        backend.get.return_value = "  "
        backend.backend_name.return_value = "mock"
        result = resolve_key("k", backend, env_var="K")
        assert result == "env_val"

    def test_error_message_lists_sources(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("SOME_KEY", raising=False)
        backend = MagicMock()
        backend.get.return_value = None
        backend.backend_name.return_value = "test-backend"
        with pytest.raises(ValueError, match="test-backend backend"):
            resolve_key("some_key", backend, env_var="SOME_KEY")


# ── get_backend factory ───────────────────────────────────────────────────


class TestGetBackend:
    def test_env_backend(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        backend = get_backend(SecretsConfig(backend="env"))
        assert backend.backend_name() == "env"

    def test_keyring_backend(self) -> None:
        mock_kr = MagicMock()
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.config import SecretsConfig

            backend = get_backend(SecretsConfig(backend="keyring"))
            assert backend.backend_name() == "keyring"

    def test_age_backend(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import SecretsConfig

        backend = get_backend(
            SecretsConfig(
                backend="age",
                age_identity=str(tmp_path / "key.txt"),
                age_secrets_dir=str(tmp_path / "secrets"),
            )
        )
        assert backend.backend_name() == "age"

    def test_unknown_backend_raises(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        with pytest.raises(ValueError, match="Unknown secrets backend"):
            get_backend(SecretsConfig(backend="vault"))

    def test_custom_keyring_service(self) -> None:
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = "val"
        with patch("open_workspace_builder.secrets.keyring_backend._import_keyring", return_value=mock_kr):
            from open_workspace_builder.config import SecretsConfig

            backend = get_backend(SecretsConfig(backend="keyring", keyring_service="my-svc"))
            backend.get("K")
            mock_kr.get_password.assert_called_with("my-svc", "K")


# ── SecretsConfig in config.py ────────────────────────────────────────────


class TestSecretsConfig:
    def test_defaults(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        sc = SecretsConfig()
        assert sc.backend == "env"
        assert sc.age_identity == "~/.config/owb/key.txt"
        assert sc.age_secrets_dir == ""
        assert sc.keyring_service == "open-workspace-builder"

    def test_frozen(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        sc = SecretsConfig()
        with pytest.raises(AttributeError):
            sc.backend = "keyring"  # type: ignore[misc]

    def test_config_has_secrets_field(self) -> None:
        from open_workspace_builder.config import Config, SecretsConfig

        config = Config()
        assert isinstance(config.secrets, SecretsConfig)

    def test_yaml_overlay(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import load_config

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "secrets:\n  backend: keyring\n  keyring_service: custom\n",
            encoding="utf-8",
        )
        config = load_config(str(cfg_file), cli_name="owb")
        assert config.secrets.backend == "keyring"
        assert config.secrets.keyring_service == "custom"

    def test_partial_yaml_keeps_defaults(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import load_config

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("secrets:\n  backend: age\n", encoding="utf-8")
        config = load_config(str(cfg_file), cli_name="owb")
        assert config.secrets.backend == "age"
        assert config.secrets.keyring_service == "open-workspace-builder"
