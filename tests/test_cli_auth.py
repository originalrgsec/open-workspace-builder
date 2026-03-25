"""Tests for the owb auth CLI command group."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── auth store-key ───────────────────────────────────────────────────────


class TestStoreKey:
    def test_store_key_env_backend(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "store-key"], input="my-secret\n")
        assert result.exit_code == 0
        assert "stored in env backend" in result.output

    def test_store_key_custom_key_name(self, runner: CliRunner) -> None:
        result = runner.invoke(
            owb,
            ["auth", "store-key", "--key-name", "openai_api_key"],
            input="sk-test\n",
        )
        assert result.exit_code == 0
        assert "openai_api_key" in result.output

    def test_store_key_empty_value_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "store-key"], input="   \n")
        assert result.exit_code == 1
        assert "empty value" in result.output

    def test_store_key_with_backend_override(self, runner: CliRunner) -> None:
        result = runner.invoke(
            owb,
            ["auth", "store-key", "--backend", "env"],
            input="test-value\n",
        )
        assert result.exit_code == 0
        assert "stored in env backend" in result.output

    def test_store_key_unknown_backend_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(
            owb,
            ["auth", "store-key", "--backend", "unknown"],
            input="test-value\n",
        )
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_store_key_keyring_backend(self, runner: CliRunner) -> None:
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = None
        with patch(
            "open_workspace_builder.secrets.keyring_backend._import_keyring",
            return_value=mock_kr,
        ):
            result = runner.invoke(
                owb,
                ["auth", "store-key", "--backend", "keyring", "--key-name", "my_key"],
                input="keyring-secret\n",
            )
            assert result.exit_code == 0
            assert "stored in keyring backend" in result.output
            mock_kr.set_password.assert_any_call("open-workspace-builder", "my_key", "keyring-secret")


# ── auth get-key ─────────────────────────────────────────────────────────


class TestGetKey:
    def test_get_key_aborted(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "get-key"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output

    def test_get_key_displays_value(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        # Clear any leftover from store-key tests, then set the env var
        monkeypatch.delenv("anthropic_api_key", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
        result = runner.invoke(owb, ["auth", "get-key"], input="y\n")
        assert result.exit_code == 0
        assert "sk-ant-test123" in result.output

    def test_get_key_custom_name(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUSTOM_KEY", "custom-val")
        result = runner.invoke(
            owb, ["auth", "get-key", "--key-name", "custom_key"], input="y\n"
        )
        assert result.exit_code == 0
        assert "custom-val" in result.output

    def test_get_key_not_found(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_KEY", raising=False)
        result = runner.invoke(
            owb, ["auth", "get-key", "--key-name", "missing_key"], input="y\n"
        )
        assert result.exit_code == 1
        assert "Could not resolve key" in result.output

    def test_get_key_shows_warning(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        result = runner.invoke(owb, ["auth", "get-key"], input="y\n")
        assert "WARNING" in result.output
        assert "sensitive data" in result.output


# ── auth status ──────────────────────────────────────────────────────────


class TestAuthStatus:
    def test_status_env_backend(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        result = runner.invoke(owb, ["auth", "status"])
        assert result.exit_code == 0
        assert "Configured backend: env" in result.output
        assert "available" in result.output

    def test_status_shows_stored_keys(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        result = runner.invoke(owb, ["auth", "status"])
        assert "ANTHROPIC_API_KEY" in result.output

    def test_status_no_keys(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OWB_API_KEY", "LITELLM_API_KEY"):
            monkeypatch.delenv(key, raising=False)
        result = runner.invoke(owb, ["auth", "status"])
        assert "Stored keys: (none)" in result.output

    def test_status_keyring_backend(self, runner: CliRunner, tmp_path: Path) -> None:
        mock_kr = MagicMock()
        mock_kr.get_password.return_value = None
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("secrets:\n  backend: keyring\n", encoding="utf-8")
        with patch(
            "open_workspace_builder.secrets.keyring_backend._import_keyring",
            return_value=mock_kr,
        ):
            with patch(
                "open_workspace_builder.secrets.keyring_backend.KeyringBackend.is_available",
                return_value=True,
            ):
                result = runner.invoke(owb, ["auth", "status", "-c", str(cfg_file)])
                assert "Configured backend: keyring" in result.output
                assert "available" in result.output

    def test_status_env_vars_listed(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        result = runner.invoke(owb, ["auth", "status"])
        assert "OPENAI_API_KEY" in result.output


# ── auth backends ────────────────────────────────────────────────────────


class TestAuthBackends:
    def test_backends_lists_env(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "backends"])
        assert result.exit_code == 0
        assert "env" in result.output
        assert "available" in result.output

    def test_backends_lists_keyring(self, runner: CliRunner) -> None:
        with patch(
            "open_workspace_builder.secrets.keyring_backend.KeyringBackend.is_available",
            return_value=True,
        ):
            result = runner.invoke(owb, ["auth", "backends"])
            assert "keyring" in result.output

    def test_backends_lists_age(self, runner: CliRunner) -> None:
        with patch(
            "open_workspace_builder.secrets.age_backend.AgeBackend.is_available",
            return_value=True,
        ):
            result = runner.invoke(owb, ["auth", "backends"])
            assert "age" in result.output
            assert "available" in result.output

    def test_backends_shows_not_installed(self, runner: CliRunner) -> None:
        with patch(
            "open_workspace_builder.secrets.keyring_backend.KeyringBackend.is_available",
            side_effect=ImportError("no keyring"),
        ):
            result = runner.invoke(owb, ["auth", "backends"])
            # Should still complete without error
            assert result.exit_code == 0
