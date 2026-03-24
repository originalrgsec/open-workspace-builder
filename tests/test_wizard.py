"""Tests for the interactive setup wizard."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from open_workspace_builder.config import (
    Config,
    MarketplaceConfig,
    ModelsConfig,
    SecretsConfig,
    SecurityConfig,
    TrustConfig,
)


def _fake_resolve(fake_home: Path):
    """Return a _resolve_paths replacement that uses fake_home."""

    def resolve(p, cli):
        return type(p)(
            config_dir=str(fake_home / f".{cli}"),
            data_dir=str(fake_home / f".{cli}" / "data"),
            credentials_dir=str(fake_home / f".{cli}" / "credentials"),
        )

    return resolve


class TestWizardAnthropic:
    """Wizard with Anthropic provider selection."""

    def test_produces_valid_config(self, tmp_path: Path) -> None:
        from open_workspace_builder.wizard.setup import run_setup_wizard

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with (
            patch(
                "open_workspace_builder.wizard.setup._step_models",
                return_value=(
                    ModelsConfig(
                        classify="anthropic/claude-sonnet-4-20250514",
                        generate="anthropic/claude-sonnet-4-20250514",
                        judge="anthropic/claude-sonnet-4-20250514",
                        security_scan="anthropic/claude-haiku-4-5-20251001",
                    ),
                    "anthropic",
                ),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_secrets_backend",
                return_value=SecretsConfig(),
            ),
            patch("open_workspace_builder.wizard.setup._step_api_key"),
            patch(
                "open_workspace_builder.wizard.setup._step_vault_tiers",
                return_value=("Work", "Personal", "Open Source"),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_marketplace",
                return_value=MarketplaceConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_security_patterns",
                return_value=SecurityConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_trust_policy",
                return_value=TrustConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._resolve_paths",
                side_effect=_fake_resolve(fake_home),
            ),
        ):
            config = run_setup_wizard(cli_name="owb")

        assert isinstance(config, Config)
        assert config.models.classify == "anthropic/claude-sonnet-4-20250514"
        assert config.models.security_scan == "anthropic/claude-haiku-4-5-20251001"


class TestWizardOpenAI:
    """Wizard with OpenAI provider selection."""

    def test_produces_openai_models(self, tmp_path: Path) -> None:
        from open_workspace_builder.wizard.setup import run_setup_wizard

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with (
            patch(
                "open_workspace_builder.wizard.setup._step_models",
                return_value=(
                    ModelsConfig(
                        classify="openai/gpt-4o",
                        generate="openai/gpt-4o",
                        judge="openai/gpt-4o",
                        security_scan="openai/gpt-4o",
                    ),
                    "openai",
                ),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_secrets_backend",
                return_value=SecretsConfig(),
            ),
            patch("open_workspace_builder.wizard.setup._step_api_key"),
            patch(
                "open_workspace_builder.wizard.setup._step_vault_tiers",
                return_value=("Work", "Personal", "Open Source"),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_marketplace",
                return_value=MarketplaceConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_security_patterns",
                return_value=SecurityConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_trust_policy",
                return_value=TrustConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._resolve_paths",
                side_effect=_fake_resolve(fake_home),
            ),
        ):
            config = run_setup_wizard(cli_name="owb")

        assert config.models.classify == "openai/gpt-4o"
        assert config.models.generate == "openai/gpt-4o"


class TestWizardOllama:
    """Wizard with Ollama provider selection."""

    def test_produces_ollama_models(self, tmp_path: Path) -> None:
        from open_workspace_builder.wizard.setup import run_setup_wizard

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with (
            patch(
                "open_workspace_builder.wizard.setup._step_models",
                return_value=(
                    ModelsConfig(
                        classify="ollama/llama3",
                        generate="ollama/llama3",
                        judge="ollama/llama3",
                        security_scan="ollama/llama3",
                    ),
                    "ollama",
                ),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_secrets_backend",
                return_value=SecretsConfig(),
            ),
            patch("open_workspace_builder.wizard.setup._step_api_key"),
            patch(
                "open_workspace_builder.wizard.setup._step_vault_tiers",
                return_value=("Work", "Personal", "Open Source"),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_marketplace",
                return_value=MarketplaceConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_security_patterns",
                return_value=SecurityConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_trust_policy",
                return_value=TrustConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._resolve_paths",
                side_effect=_fake_resolve(fake_home),
            ),
        ):
            config = run_setup_wizard(cli_name="owb")

        assert config.models.classify == "ollama/llama3"


class TestWizardSkip:
    """Wizard with Skip provider selection."""

    def test_empty_model_strings(self, tmp_path: Path) -> None:
        from open_workspace_builder.wizard.setup import run_setup_wizard

        fake_home = tmp_path / "home"
        fake_home.mkdir()

        with (
            patch(
                "open_workspace_builder.wizard.setup._step_models",
                return_value=(ModelsConfig(), "skip"),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_secrets_backend",
                return_value=SecretsConfig(),
            ),
            patch("open_workspace_builder.wizard.setup._step_api_key"),
            patch(
                "open_workspace_builder.wizard.setup._step_vault_tiers",
                return_value=("Work", "Personal", "Open Source"),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_marketplace",
                return_value=MarketplaceConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_security_patterns",
                return_value=SecurityConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_trust_policy",
                return_value=TrustConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._resolve_paths",
                side_effect=_fake_resolve(fake_home),
            ),
        ):
            config = run_setup_wizard(cli_name="owb")

        assert config.models.classify == ""
        assert config.models.generate == ""


# ── Individual step tests ───────────────────────────────────────────────────


class TestStepModels:
    """Test _step_models with different provider choices."""

    def test_anthropic_selection(self) -> None:
        from open_workspace_builder.wizard.setup import _step_models

        with patch("click.prompt", return_value="1"):
            models, provider = _step_models()
        assert provider == "anthropic"
        assert models.classify == "anthropic/claude-sonnet-4-20250514"

    def test_openai_selection(self) -> None:
        from open_workspace_builder.wizard.setup import _step_models

        with patch("click.prompt", return_value="2"):
            models, provider = _step_models()
        assert provider == "openai"
        assert models.classify == "openai/gpt-4o"

    def test_ollama_selection(self) -> None:
        from open_workspace_builder.wizard.setup import _step_models

        prompts = iter(["3", "ollama/mistral"])
        with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
            models, provider = _step_models()
        assert provider == "ollama"
        assert models.classify == "ollama/mistral"

    def test_ollama_auto_prefix(self) -> None:
        from open_workspace_builder.wizard.setup import _step_models

        prompts = iter(["3", "mistral"])
        with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
            models, provider = _step_models()
        assert models.classify == "ollama/mistral"

    def test_skip_selection(self) -> None:
        from open_workspace_builder.wizard.setup import _step_models

        with patch("click.prompt", return_value="5"):
            models, provider = _step_models()
        assert provider == "skip"
        assert models.classify == ""

    def test_other_selection(self) -> None:
        from open_workspace_builder.wizard.setup import _step_models

        prompts = iter(
            ["4", "custom/model-a", "custom/model-b", "custom/model-c", "custom/model-d"]
        )
        with patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)):
            models, provider = _step_models()
        assert provider == "other"
        assert models.classify == "custom/model-a"
        assert models.generate == "custom/model-b"


class TestStepVaultTiers:
    """Test _step_vault_tiers with various inputs."""

    def test_default_tiers(self) -> None:
        from open_workspace_builder.wizard.setup import _step_vault_tiers

        with patch("click.confirm", return_value=False):
            tiers = _step_vault_tiers()
        assert tiers == ("Work", "Personal", "Open Source")

    def test_custom_tiers(self) -> None:
        from open_workspace_builder.wizard.setup import _step_vault_tiers

        confirms = iter([True, False])  # customize=yes, add another=no
        prompts = iter(["Engineering", "Research", "Side Projects"])
        with (
            patch("click.confirm", side_effect=lambda *a, **kw: next(confirms)),
            patch("click.prompt", side_effect=lambda *a, **kw: next(prompts)),
        ):
            tiers = _step_vault_tiers()
        assert tiers == ("Engineering", "Research", "Side Projects")


class TestStepMarketplace:
    """Test _step_marketplace with various selections."""

    def test_generic(self) -> None:
        from open_workspace_builder.wizard.setup import _step_marketplace

        with patch("click.prompt", return_value="1"):
            mkt = _step_marketplace()
        assert mkt.format == "generic"

    def test_anthropic(self) -> None:
        from open_workspace_builder.wizard.setup import _step_marketplace

        with patch("click.prompt", return_value="2"):
            mkt = _step_marketplace()
        assert mkt.format == "anthropic"

    def test_openai(self) -> None:
        from open_workspace_builder.wizard.setup import _step_marketplace

        with patch("click.prompt", return_value="3"):
            mkt = _step_marketplace()
        assert mkt.format == "openai"


class TestStepSecurityPatterns:
    """Test _step_security_patterns."""

    def test_all_defaults(self) -> None:
        from open_workspace_builder.wizard.setup import _step_security_patterns

        with patch("click.prompt", return_value="1"):
            sec = _step_security_patterns()
        assert sec.active_patterns == ("owb-default",)

    def test_individual_selection(self) -> None:
        from open_workspace_builder.wizard.setup import _step_security_patterns

        confirms = [True, True, False, False, False, False, False, False, False]
        with (
            patch("click.prompt", return_value="2"),
            patch("click.confirm", side_effect=confirms),
        ):
            sec = _step_security_patterns()
        assert "owb-exfiltration" in sec.active_patterns
        assert "owb-persistence" in sec.active_patterns
        assert len(sec.active_patterns) == 2


class TestCredentialStorage:
    """API key storage via secrets backend."""

    def test_api_key_stored_via_backend(self, tmp_path: Path) -> None:
        from unittest.mock import MagicMock

        from open_workspace_builder.wizard.setup import _step_api_key

        mock_backend = MagicMock()
        with (
            patch("click.confirm", return_value=True),
            patch("click.prompt", return_value="sk-test-key-123"),
            patch(
                "open_workspace_builder.secrets.factory.get_backend",
                return_value=mock_backend,
            ),
        ):
            _step_api_key("anthropic", SecretsConfig())

        mock_backend.set.assert_called_once_with("anthropic_api_key", "sk-test-key-123")

    def test_skip_provider_no_storage(self) -> None:
        from open_workspace_builder.wizard.setup import _step_api_key

        _step_api_key("skip", SecretsConfig())  # should not prompt

    def test_decline_storage(self) -> None:
        from open_workspace_builder.wizard.setup import _step_api_key

        with patch("click.confirm", return_value=False):
            _step_api_key("anthropic", SecretsConfig())  # should not store


class TestWizardConfigFileWritten:
    """Wizard writes config to the correct location."""

    def test_config_yaml_created(self, tmp_path: Path) -> None:
        from open_workspace_builder.wizard.setup import run_setup_wizard

        fake_home = tmp_path / "home"
        fake_home.mkdir()
        config_dir = fake_home / ".owb"

        with (
            patch(
                "open_workspace_builder.wizard.setup._step_models",
                return_value=(ModelsConfig(), "skip"),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_secrets_backend",
                return_value=SecretsConfig(),
            ),
            patch("open_workspace_builder.wizard.setup._step_api_key"),
            patch(
                "open_workspace_builder.wizard.setup._step_vault_tiers",
                return_value=("Work", "Personal", "Open Source"),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_marketplace",
                return_value=MarketplaceConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_security_patterns",
                return_value=SecurityConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._step_trust_policy",
                return_value=TrustConfig(),
            ),
            patch(
                "open_workspace_builder.wizard.setup._resolve_paths",
                side_effect=_fake_resolve(fake_home),
            ),
        ):
            run_setup_wizard(cli_name="owb")

        assert (config_dir / "config.yaml").exists()
        assert (config_dir / "data").is_dir()
        assert (config_dir / "credentials").is_dir()


class TestNoWizardFlag:
    """--no-wizard skips the wizard and uses defaults."""

    def test_no_wizard_uses_defaults(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["init", "--no-wizard", "--dry-run", "--target", str(tmp_path)])
        assert "Setup Wizard" not in (result.output or "")


class TestExistingConfigSkipsWizard:
    """Existing config file means wizard is not invoked."""

    def test_existing_config_no_wizard(self, tmp_path: Path) -> None:
        from click.testing import CliRunner

        from open_workspace_builder.cli import owb

        fake_home = tmp_path / "home"
        config_dir = fake_home / ".owb"
        config_dir.mkdir(parents=True)
        (config_dir / "config.yaml").write_text("target: output\n", encoding="utf-8")

        runner = CliRunner()
        with patch("open_workspace_builder.cli.Path.home", return_value=fake_home):
            result = runner.invoke(owb, ["init", "--dry-run", "--target", str(tmp_path / "out")])

        assert "Setup Wizard" not in (result.output or "")
