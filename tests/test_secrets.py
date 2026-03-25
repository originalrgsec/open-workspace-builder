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

    def test_bitwarden_backend(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        backend = get_backend(SecretsConfig(backend="bitwarden"))
        assert backend.backend_name() == "bitwarden"

    def test_onepassword_backend(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        backend = get_backend(SecretsConfig(backend="onepassword"))
        assert backend.backend_name() == "onepassword"

    def test_bitwarden_custom_item(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        backend = get_backend(SecretsConfig(backend="bitwarden", bitwarden_item="Custom"))
        assert backend._item_name == "Custom"

    def test_onepassword_custom_vault(self) -> None:
        from open_workspace_builder.config import SecretsConfig

        backend = get_backend(SecretsConfig(backend="onepassword", onepassword_vault="Prod"))
        assert backend._vault == "Prod"

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
        assert sc.bitwarden_item == "OWB API Keys"
        assert sc.onepassword_vault == "Development"

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

    def test_bitwarden_yaml_overlay(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import load_config

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "secrets:\n  backend: bitwarden\n  bitwarden_item: My Keys\n",
            encoding="utf-8",
        )
        config = load_config(str(cfg_file), cli_name="owb")
        assert config.secrets.backend == "bitwarden"
        assert config.secrets.bitwarden_item == "My Keys"

    def test_onepassword_yaml_overlay(self, tmp_path: Path) -> None:
        from open_workspace_builder.config import load_config

        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text(
            "secrets:\n  backend: onepassword\n  onepassword_vault: Production\n",
            encoding="utf-8",
        )
        config = load_config(str(cfg_file), cli_name="owb")
        assert config.secrets.backend == "onepassword"
        assert config.secrets.onepassword_vault == "Production"


# ── BitwardenBackend ─────────────────────────────────────────────────────


class TestBitwardenBackend:
    def _make_bw_item_json(self, fields: list[tuple[str, str]], item_id: str = "abc123") -> str:
        data = {
            "id": item_id,
            "name": "OWB API Keys",
            "fields": [{"name": k, "value": v, "type": 0} for k, v in fields],
        }
        return json.dumps(data)

    def test_get_returns_value(self) -> None:
        item_json = self._make_bw_item_json([("MY_KEY", "secret")])
        run_result = MagicMock(returncode=0, stdout=item_json, stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            assert BitwardenBackend().get("MY_KEY") == "secret"

    def test_get_returns_none_when_not_found(self) -> None:
        run_result = MagicMock(returncode=1, stdout="", stderr="Not found")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            assert BitwardenBackend().get("MISSING") is None

    def test_get_returns_none_for_missing_field(self) -> None:
        item_json = self._make_bw_item_json([("OTHER", "val")])
        run_result = MagicMock(returncode=0, stdout=item_json, stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            assert BitwardenBackend().get("MISSING") is None

    def test_set_creates_item_when_missing(self) -> None:
        fetch_fail = MagicMock(returncode=1, stdout="", stderr="Not found")
        create_ok = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", side_effect=[fetch_fail, create_ok]):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            BitwardenBackend().set("NEW_KEY", "new_val")

    def test_set_updates_existing_item(self) -> None:
        item_json = self._make_bw_item_json([("OLD", "old_val")])
        fetch_ok = MagicMock(returncode=0, stdout=item_json, stderr="")
        edit_ok = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", side_effect=[fetch_ok, fetch_ok, edit_ok]):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            BitwardenBackend().set("NEW_KEY", "new_val")

    def test_delete_removes_field(self) -> None:
        item_json = self._make_bw_item_json([("DEL_KEY", "val"), ("KEEP", "v")])
        fetch_ok = MagicMock(returncode=0, stdout=item_json, stderr="")
        edit_ok = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", side_effect=[fetch_ok, fetch_ok, edit_ok]):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            BitwardenBackend().delete("DEL_KEY")

    def test_delete_noop_when_item_missing(self) -> None:
        fetch_fail = MagicMock(returncode=1, stdout="", stderr="Not found")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=fetch_fail):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            BitwardenBackend().delete("MISSING")

    def test_delete_noop_when_field_missing(self) -> None:
        item_json = self._make_bw_item_json([("OTHER", "val")])
        fetch_ok = MagicMock(returncode=0, stdout=item_json, stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=fetch_ok):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            BitwardenBackend().delete("MISSING")

    def test_list_keys(self) -> None:
        item_json = self._make_bw_item_json([("A", "1"), ("B", "2")])
        run_result = MagicMock(returncode=0, stdout=item_json, stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            assert BitwardenBackend().list_keys() == ["A", "B"]

    def test_list_keys_empty_when_no_item(self) -> None:
        run_result = MagicMock(returncode=1, stdout="", stderr="Not found")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            assert BitwardenBackend().list_keys() == []

    def test_backend_name(self) -> None:
        from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
        assert BitwardenBackend().backend_name() == "bitwarden"

    def test_is_available_true(self) -> None:
        status_result = MagicMock(returncode=0, stdout='{"status":"unlocked"}', stderr="")
        with patch("shutil.which", return_value="/usr/bin/bw"):
            with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=status_result):
                from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
                assert BitwardenBackend.is_available() is True

    def test_is_available_false_no_binary(self) -> None:
        with patch("shutil.which", return_value=None):
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            assert BitwardenBackend.is_available() is False

    def test_is_available_false_bad_status(self) -> None:
        status_result = MagicMock(returncode=1, stdout="not json", stderr="")
        with patch("shutil.which", return_value="/usr/bin/bw"):
            with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=status_result):
                from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
                assert BitwardenBackend.is_available() is False

    def test_session_env_var_used(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("BW_SESSION", "test-session-token")
        item_json = self._make_bw_item_json([("K", "V")])
        run_result = MagicMock(returncode=0, stdout=item_json, stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=run_result) as mock_run:
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            BitwardenBackend().get("K")
            cmd = mock_run.call_args[0][0]
            assert "--session" in cmd
            assert "test-session-token" in cmd

    def test_custom_item_name(self) -> None:
        item_json = self._make_bw_item_json([("K", "V")])
        run_result = MagicMock(returncode=0, stdout=item_json, stderr="")
        with patch("open_workspace_builder.secrets.bitwarden_backend.subprocess.run", return_value=run_result) as mock_run:
            from open_workspace_builder.secrets.bitwarden_backend import BitwardenBackend
            BitwardenBackend(item_name="Custom Item").get("K")
            cmd = mock_run.call_args[0][0]
            assert "Custom Item" in cmd


# ── OnePasswordBackend ───────────────────────────────────────────────────


class TestOnePasswordBackend:
    def test_get_returns_value(self) -> None:
        run_result = MagicMock(returncode=0, stdout="secret_value\n", stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            assert OnePasswordBackend().get("MY_KEY") == "secret_value"

    def test_get_returns_none_when_not_found(self) -> None:
        run_result = MagicMock(returncode=1, stdout="", stderr="not found")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            assert OnePasswordBackend().get("MISSING") is None

    def test_get_returns_none_for_empty_output(self) -> None:
        run_result = MagicMock(returncode=0, stdout="", stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            assert OnePasswordBackend().get("EMPTY") is None

    def test_set_edits_existing(self) -> None:
        run_result = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result) as mock_run:
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            OnePasswordBackend().set("KEY", "VAL")
            cmd = mock_run.call_args[0][0]
            assert "item" in cmd and "edit" in cmd and "KEY=VAL" in cmd

    def test_set_creates_when_not_found(self) -> None:
        edit_fail = MagicMock(returncode=1, stdout="", stderr="item not found")
        create_ok = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", side_effect=[edit_fail, create_ok]):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            OnePasswordBackend().set("NEW", "VAL")

    def test_delete_calls_edit(self) -> None:
        run_result = MagicMock(returncode=0, stdout="{}", stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result) as mock_run:
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            OnePasswordBackend().delete("DEL_KEY")
            cmd = mock_run.call_args[0][0]
            assert "DEL_KEY[delete]" in cmd

    def test_delete_noop_on_failure(self) -> None:
        run_result = MagicMock(returncode=1, stdout="", stderr="not found")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            OnePasswordBackend().delete("MISSING")

    def test_list_keys(self) -> None:
        item_data = {"fields": [{"label": "notesPlain", "value": "", "purpose": "NOTES"}, {"label": "KEY_A", "value": "a"}, {"label": "KEY_B", "value": "b"}]}
        run_result = MagicMock(returncode=0, stdout=json.dumps(item_data), stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            assert OnePasswordBackend().list_keys() == ["KEY_A", "KEY_B"]

    def test_list_keys_empty_on_failure(self) -> None:
        run_result = MagicMock(returncode=1, stdout="", stderr="not found")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            assert OnePasswordBackend().list_keys() == []

    def test_backend_name(self) -> None:
        from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
        assert OnePasswordBackend().backend_name() == "onepassword"

    def test_is_available_true(self) -> None:
        account_result = MagicMock(returncode=0, stdout='[{"account_uuid": "abc"}]', stderr="")
        with patch("shutil.which", return_value="/usr/bin/op"):
            with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=account_result):
                from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
                assert OnePasswordBackend.is_available() is True

    def test_is_available_false_no_binary(self) -> None:
        with patch("shutil.which", return_value=None):
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            assert OnePasswordBackend.is_available() is False

    def test_is_available_false_no_accounts(self) -> None:
        account_result = MagicMock(returncode=0, stdout="[]", stderr="")
        with patch("shutil.which", return_value="/usr/bin/op"):
            with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=account_result):
                from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
                assert OnePasswordBackend.is_available() is False

    def test_is_available_false_on_error(self) -> None:
        account_result = MagicMock(returncode=1, stdout="", stderr="error")
        with patch("shutil.which", return_value="/usr/bin/op"):
            with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=account_result):
                from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
                assert OnePasswordBackend.is_available() is False

    def test_custom_vault_name(self) -> None:
        run_result = MagicMock(returncode=0, stdout="val\n", stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result) as mock_run:
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            OnePasswordBackend(vault_name="Production").get("K")
            cmd = mock_run.call_args[0][0]
            assert "Production" in cmd

    def test_service_account_token_in_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OP_SERVICE_ACCOUNT_TOKEN", "test-token")
        run_result = MagicMock(returncode=0, stdout="val\n", stderr="")
        with patch("open_workspace_builder.secrets.onepassword_backend.subprocess.run", return_value=run_result) as mock_run:
            from open_workspace_builder.secrets.onepassword_backend import OnePasswordBackend
            OnePasswordBackend().get("K")
            env = mock_run.call_args[1].get("env", {})
            assert env.get("OP_SERVICE_ACCOUNT_TOKEN") == "test-token"

