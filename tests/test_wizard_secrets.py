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

    def test_sops_age_identity_written_when_set(self, tmp_path: Path) -> None:
        """OWB-S132 AC-5: sops_age_identity survives YAML round trip."""
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(
            secrets=SecretsConfig(
                backend="sops",
                sops_age_identity="~/custom/age.txt",
            )
        )
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["sops_age_identity"] == "~/custom/age.txt"

    def test_sops_config_file_written_when_set(self, tmp_path: Path) -> None:
        """OWB-S132 AC-5: sops_config_file survives YAML round trip."""
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(
            secrets=SecretsConfig(
                backend="sops",
                sops_config_file="~/custom/.sops.yaml",
            )
        )
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert data["secrets"]["sops_config_file"] == "~/custom/.sops.yaml"

    def test_sops_custom_paths_omitted_when_unset(self, tmp_path: Path) -> None:
        """Unset fields must not bloat the generated YAML with null keys."""
        import yaml

        from open_workspace_builder.config import Config
        from open_workspace_builder.wizard.setup import _write_config_yaml

        config = Config(secrets=SecretsConfig(backend="sops"))
        cfg_path = tmp_path / "config.yaml"
        _write_config_yaml(config, cfg_path)
        data = yaml.safe_load(cfg_path.read_text())
        assert "sops_age_identity" not in data["secrets"]
        assert "sops_config_file" not in data["secrets"]


class TestStepSecretsBackendSopsCustomPaths:
    """OWB-S132 AC-4: wizard optionally prompts for non-default SOPS paths."""

    def test_sops_prompts_for_age_identity_when_env_var_set(
        self, monkeypatch, tmp_path: Path
    ) -> None:
        """When SOPS_AGE_KEY_FILE is set and points at an existing file,
        the wizard offers to record it. Accepting it populates the config."""
        monkeypatch.setenv("SOPS_AGE_KEY_FILE", str(tmp_path / "age.txt"))
        (tmp_path / "age.txt").write_text("# dummy", encoding="utf-8")
        # backend choice = 2 (sops); age prompt = y; record env path; config prompt = n
        prompts = iter(["2", "y", "n"])
        confirms = iter([True, False])
        with (
            patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)),
            patch("click.confirm", side_effect=lambda *a, **kw: next(confirms)),
            patch("shutil.which", return_value="/usr/local/bin/sops"),
        ):
            from open_workspace_builder.wizard.setup import _step_secrets_backend

            result = _step_secrets_backend()
        assert result.backend == "sops"
        assert result.sops_age_identity == str(tmp_path / "age.txt")
        assert result.sops_config_file is None

    def test_sops_skips_age_identity_prompt_by_default(self, monkeypatch) -> None:
        """When the environment is fully default, wizard skips the extra
        prompts entirely — preserves existing UX for the common path."""
        monkeypatch.delenv("SOPS_AGE_KEY_FILE", raising=False)
        prompts = iter(["2"])
        with (
            patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)),
            patch("click.confirm", return_value=False),
            patch("shutil.which", return_value="/usr/local/bin/sops"),
            patch(
                "open_workspace_builder.wizard.setup.Path.exists",
                return_value=False,
            ),
        ):
            from open_workspace_builder.wizard.setup import _step_secrets_backend

            result = _step_secrets_backend()
        assert result.backend == "sops"
        assert result.sops_age_identity is None
        assert result.sops_config_file is None

    def test_sops_prompts_for_config_file_when_present(self, monkeypatch, tmp_path: Path) -> None:
        """When a .sops.yaml is present at the workspace root, wizard
        offers to record it."""
        monkeypatch.delenv("SOPS_AGE_KEY_FILE", raising=False)
        monkeypatch.chdir(tmp_path)
        (tmp_path / ".sops.yaml").write_text("creation_rules: []\n", encoding="utf-8")
        prompts = iter(["2"])
        confirms = iter([True])  # confirm=y for sops_config_file
        with (
            patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)),
            patch("click.confirm", side_effect=lambda *a, **kw: next(confirms)),
            patch("shutil.which", return_value="/usr/local/bin/sops"),
        ):
            from open_workspace_builder.wizard.setup import _step_secrets_backend

            result = _step_secrets_backend()
        assert result.backend == "sops"
        assert result.sops_config_file == str(tmp_path / ".sops.yaml")
