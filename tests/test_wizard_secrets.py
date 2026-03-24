"""Tests for wizard secrets backend integration."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.config import SecretsConfig


class TestStepSecretsBackend:
    """Tests for _step_secrets_backend wizard step."""

    def test_default_env(self) -> None:
        with patch("click.prompt", return_value="1"):
            from open_workspace_builder.wizard.setup import _step_secrets_backend

            result = _step_secrets_backend()
            assert result.backend == "env"

    def test_keyring_when_available(self) -> None:
        with patch("click.prompt", return_value="2"):
            with patch(
                "open_workspace_builder.secrets.keyring_backend.KeyringBackend.is_available",
                return_value=True,
            ):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "keyring"

    def test_keyring_fallback_when_unavailable(self) -> None:
        with patch("click.prompt", return_value="2"):
            with patch(
                "open_workspace_builder.secrets.keyring_backend.KeyringBackend.is_available",
                return_value=False,
            ):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "env"

    def test_keyring_fallback_on_import_error(self) -> None:
        with patch("click.prompt", return_value="2"):
            with patch.dict("sys.modules", {"keyring": None}):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "env"

    def test_age_when_available(self) -> None:
        prompts = iter(["3", "~/.config/owb/key.txt"])
        with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
            with patch(
                "open_workspace_builder.secrets.age_backend.AgeBackend.is_available",
                return_value=True,
            ):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "age"

    def test_age_fallback_when_unavailable(self) -> None:
        with patch("click.prompt", return_value="3"):
            with patch(
                "open_workspace_builder.secrets.age_backend.AgeBackend.is_available",
                return_value=False,
            ):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "env"


class TestStepApiKeyWithBackend:
    """Tests for _step_api_key using secrets backend."""

    def test_skip_provider(self) -> None:
        from open_workspace_builder.wizard.setup import _step_api_key

        # Should return without prompting
        _step_api_key("skip", SecretsConfig())

    def test_ollama_provider(self) -> None:
        with patch("click.prompt", return_value="http://localhost:11434"):
            from open_workspace_builder.wizard.setup import _step_api_key

            _step_api_key("ollama", SecretsConfig())

    def test_anthropic_store_via_backend(self) -> None:
        mock_backend = MagicMock()
        confirms = iter([True])
        prompts = iter(["sk-ant-test"])
        with patch("click.confirm", side_effect=lambda *a, **kw: next(confirms)):
            with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
                with patch(
                    "open_workspace_builder.secrets.factory.get_backend",
                    return_value=mock_backend,
                ):
                    from open_workspace_builder.wizard.setup import _step_api_key

                    _step_api_key("anthropic", SecretsConfig())
                    mock_backend.set.assert_called_once_with(
                        "anthropic_api_key", "sk-ant-test"
                    )

    def test_openai_store_via_backend(self) -> None:
        mock_backend = MagicMock()
        confirms = iter([True])
        prompts = iter(["sk-openai-test"])
        with patch("click.confirm", side_effect=lambda *a, **kw: next(confirms)):
            with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
                with patch(
                    "open_workspace_builder.secrets.factory.get_backend",
                    return_value=mock_backend,
                ):
                    from open_workspace_builder.wizard.setup import _step_api_key

                    _step_api_key("openai", SecretsConfig())
                    mock_backend.set.assert_called_once_with(
                        "openai_api_key", "sk-openai-test"
                    )

    def test_decline_to_store(self) -> None:
        with patch("click.confirm", return_value=False):
            from open_workspace_builder.wizard.setup import _step_api_key

            # Should not prompt for key
            _step_api_key("anthropic", SecretsConfig())

    def test_empty_key_skipped(self) -> None:
        with patch("click.confirm", return_value=True):
            with patch("click.prompt", return_value="   "):
                from open_workspace_builder.wizard.setup import _step_api_key

                _step_api_key("anthropic", SecretsConfig())

    def test_other_provider(self) -> None:
        from open_workspace_builder.wizard.setup import _step_api_key

        _step_api_key("other", SecretsConfig())


class TestWriteConfigYamlSecrets:
    """Tests for secrets config serialization in _write_config_yaml."""

    def test_default_backend_not_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config()
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert "secrets" not in data

    def test_keyring_backend_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="keyring"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["backend"] == "keyring"

    def test_age_backend_with_custom_identity(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(
            secrets=SecretsConfig(backend="age", age_identity="/custom/key.txt")
        )
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["backend"] == "age"
        assert data["secrets"]["age_identity"] == "/custom/key.txt"

    def test_age_default_identity_not_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="age"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert "age_identity" not in data["secrets"]
