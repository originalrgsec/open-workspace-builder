"""Tests for the owb auth CLI command group (himitsubako backends)."""

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
    def test_store_key_env_backend_is_read_only(self, runner: CliRunner) -> None:
        """himitsubako EnvBackend is read-only; store-key should error."""
        result = runner.invoke(owb, ["auth", "store-key"], input="my-secret\n")
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_store_key_with_mock_writable_backend(self, runner: CliRunner) -> None:
        mock_backend = MagicMock()
        mock_backend.backend_name = "mock"
        with patch(
            "open_workspace_builder.secrets.factory.get_backend",
            return_value=mock_backend,
        ):
            result = runner.invoke(
                owb,
                ["auth", "store-key", "--key-name", "openai_api_key"],
                input="sk-test\n",
            )
            assert result.exit_code == 0
            assert "openai_api_key" in result.output
            mock_backend.set.assert_called_once_with("openai_api_key", "sk-test")

    def test_store_key_empty_value_rejected(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "store-key"], input="   \n")
        assert result.exit_code == 1
        assert "empty value" in result.output

    def test_store_key_unknown_backend_errors(self, runner: CliRunner) -> None:
        result = runner.invoke(
            owb,
            ["auth", "store-key", "--backend", "unknown"],
            input="test-value\n",
        )
        assert result.exit_code == 1
        assert "Error" in result.output

    def test_store_key_keychain_backend(self, runner: CliRunner) -> None:
        mock_backend = MagicMock()
        mock_backend.backend_name = "keychain"
        with patch(
            "open_workspace_builder.secrets.factory.get_backend",
            return_value=mock_backend,
        ):
            result = runner.invoke(
                owb,
                ["auth", "store-key", "--backend", "keychain", "--key-name", "my_key"],
                input="keychain-secret\n",
            )
            assert result.exit_code == 0
            assert "stored in keychain backend" in result.output
            mock_backend.set.assert_called_once_with("my_key", "keychain-secret")


# ── auth get-key ─────────────────────────────────────────────────────────


class TestGetKey:
    def test_get_key_aborted(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "get-key"], input="n\n")
        assert result.exit_code == 0
        assert "Aborted" in result.output

    def test_get_key_displays_value(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.delenv("anthropic_api_key", raising=False)
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test123")
        result = runner.invoke(owb, ["auth", "get-key"], input="y\n")
        assert result.exit_code == 0
        assert "sk-ant-test123" in result.output

    def test_get_key_custom_name(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("CUSTOM_KEY", "custom-val")
        result = runner.invoke(owb, ["auth", "get-key", "--key-name", "custom_key"], input="y\n")
        assert result.exit_code == 0
        assert "custom-val" in result.output

    def test_get_key_not_found(self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("MISSING_KEY", raising=False)
        result = runner.invoke(owb, ["auth", "get-key", "--key-name", "missing_key"], input="y\n")
        assert result.exit_code == 1
        assert "Could not resolve key" in result.output

    def test_get_key_shows_warning(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_status_shows_stored_keys(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        result = runner.invoke(owb, ["auth", "status"])
        assert "ANTHROPIC_API_KEY" in result.output

    def test_status_lists_env_vars(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """himitsubako EnvBackend.list_keys() enumerates all env vars."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        result = runner.invoke(owb, ["auth", "status"])
        assert "Stored keys:" in result.output
        assert "ANTHROPIC_API_KEY" in result.output

    def test_status_keychain_backend(self, runner: CliRunner, tmp_path: Path) -> None:
        mock_backend = MagicMock()
        mock_backend.backend_name = "keychain"
        mock_backend.list_keys.return_value = ["my_key"]
        cfg_file = tmp_path / "config.yaml"
        cfg_file.write_text("secrets:\n  backend: keychain\n", encoding="utf-8")
        with patch(
            "open_workspace_builder.secrets.factory.get_backend",
            return_value=mock_backend,
        ):
            result = runner.invoke(owb, ["auth", "status", "-c", str(cfg_file)])
            assert "Configured backend: keychain" in result.output
            assert "available" in result.output

    def test_status_env_vars_listed(
        self, runner: CliRunner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
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

    def test_backends_lists_sops(self, runner: CliRunner) -> None:
        with patch("shutil.which", return_value="/usr/local/bin/sops"):
            result = runner.invoke(owb, ["auth", "backends"])
            assert "sops" in result.output

    def test_backends_lists_keychain(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "backends"])
        assert "keychain" in result.output

    def test_backends_lists_bitwarden(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "backends"])
        assert "bitwarden" in result.output

    def test_backends_shows_himitsubako(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "backends"])
        assert "himitsubako" in result.output
        assert result.exit_code == 0
