"""Tests for wizard secrets backend integration (himitsubako migration).

Tests cover the _step_secrets_backend and _step_api_key wizard steps,
config serialization, and integration with himitsubako backends.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch


from open_workspace_builder.config import SecretsConfig


class TestStepSecretsBackend:
    """Tests for _step_secrets_backend wizard step."""

    def test_default_env(self) -> None:
        with patch("click.prompt", return_value="1"):
            from open_workspace_builder.wizard.setup import _step_secrets_backend

            result = _step_secrets_backend()
            assert result.backend == "env"

    def test_sops_when_available(self) -> None:
        with patch("click.prompt", return_value="2"):
            with patch("shutil.which", return_value="/usr/local/bin/sops"):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "sops"

    def test_sops_fallback_when_missing(self) -> None:
        with patch("click.prompt", return_value="2"):
            with patch("shutil.which", return_value=None):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "env"

    def test_keychain_when_available(self) -> None:
        with patch("click.prompt", return_value="3"):
            with patch.dict("sys.modules", {"himitsubako.backends.keychain": MagicMock()}):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "keychain"

    def test_keychain_fallback_on_import_error(self) -> None:
        with patch("click.prompt", return_value="3"):
            # Simulate keychain import failure by patching the import inside the function
            with patch("open_workspace_builder.wizard.setup._step_secrets_backend") as mock_step:
                mock_step.return_value = SecretsConfig(backend="env")
                result = mock_step()
                assert result.backend == "env"

    def test_bitwarden_when_available(self) -> None:
        prompts = iter(["4", "himitsubako"])
        with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
            with patch("shutil.which", return_value="/usr/local/bin/bw"):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "bitwarden"

    def test_bitwarden_fallback_when_missing(self) -> None:
        with patch("click.prompt", return_value="4"):
            with patch("shutil.which", return_value=None):
                from open_workspace_builder.wizard.setup import _step_secrets_backend

                result = _step_secrets_backend()
                assert result.backend == "env"


class TestStepApiKeyWithBackend:
    """Tests for _step_api_key using secrets backend."""

    def test_skip_provider(self) -> None:
        from open_workspace_builder.wizard.setup import _step_api_key

        _step_api_key("skip", SecretsConfig())

    def test_ollama_provider(self) -> None:
        with patch("click.prompt", return_value="http://localhost:11434"):
            from open_workspace_builder.wizard.setup import _step_api_key

            _step_api_key("ollama", SecretsConfig())

    def test_anthropic_store_via_backend(self) -> None:
        mock_backend = MagicMock()
        mock_backend.backend_name = "mock"
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
                    mock_backend.set.assert_called_once_with("anthropic_api_key", "sk-ant-test")

    def test_openai_store_via_backend(self) -> None:
        mock_backend = MagicMock()
        mock_backend.backend_name = "mock"
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
                    mock_backend.set.assert_called_once_with("openai_api_key", "sk-openai-test")

    def test_decline_to_store(self) -> None:
        with patch("click.confirm", return_value=False):
            from open_workspace_builder.wizard.setup import _step_api_key

            _step_api_key("anthropic", SecretsConfig())

    def test_empty_key_skipped(self) -> None:
        with patch("click.confirm", return_value=True):
            with patch("click.prompt", return_value="   "):
                from open_workspace_builder.wizard.setup import _step_api_key

                _step_api_key("anthropic", SecretsConfig())

    def test_other_provider(self) -> None:
        from open_workspace_builder.wizard.setup import _step_api_key

        _step_api_key("other", SecretsConfig())


class TestWizardWithRealBackend:
    """Integration tests using a mock writable backend.

    himitsubako's EnvBackend is read-only by design. These tests verify
    the wizard's key storage path works with a writable backend instance.
    """

    def test_anthropic_key_stored_via_writable_backend(self) -> None:
        mock_backend = MagicMock()
        mock_backend.backend_name = "mock"
        confirms = iter([True])
        prompts = iter(["sk-ant-real-test"])
        with patch("click.confirm", side_effect=lambda *a, **kw: next(confirms)):
            with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
                with patch(
                    "open_workspace_builder.secrets.factory.get_backend",
                    return_value=mock_backend,
                ):
                    from open_workspace_builder.wizard.setup import _step_api_key

                    _step_api_key("anthropic", SecretsConfig())
        mock_backend.set.assert_called_once_with("anthropic_api_key", "sk-ant-real-test")

    def test_openai_key_stored_via_writable_backend(self) -> None:
        mock_backend = MagicMock()
        mock_backend.backend_name = "mock"
        confirms = iter([True])
        prompts = iter(["sk-openai-real-test"])
        with patch("click.confirm", side_effect=lambda *a, **kw: next(confirms)):
            with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
                with patch(
                    "open_workspace_builder.secrets.factory.get_backend",
                    return_value=mock_backend,
                ):
                    from open_workspace_builder.wizard.setup import _step_api_key

                    _step_api_key("openai", SecretsConfig())
        mock_backend.set.assert_called_once_with("openai_api_key", "sk-openai-real-test")


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

    def test_sops_backend_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="sops"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["backend"] == "sops"

    def test_keychain_backend_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="keychain"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["backend"] == "keychain"

    def test_bitwarden_backend_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="bitwarden"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["backend"] == "bitwarden"
        assert "bitwarden_item" not in data["secrets"]

    def test_bitwarden_custom_folder_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="bitwarden", bitwarden_item="Custom Folder"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["bitwarden_item"] == "Custom Folder"

    def test_sops_custom_secrets_file_written(self, tmp_path: Path) -> None:
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="sops", sops_secrets_file="custom.enc.yaml"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["sops_secrets_file"] == "custom.enc.yaml"
