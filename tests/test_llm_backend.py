"""Tests for LLM ModelBackend: construction, routing, retry, error handling."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from open_workspace_builder.config import ModelsConfig
from open_workspace_builder.llm.backend import ModelBackend, ModelBackendError


class TestModelBackendConstruction:
    """Verify ModelBackend reads from ModelsConfig correctly."""

    def test_default_config_when_none(self) -> None:
        backend = ModelBackend()
        assert backend._models_config is not None
        assert backend._models_config.security_scan == ""

    def test_explicit_config(self) -> None:
        config = ModelsConfig(security_scan="anthropic/claude-sonnet-4-6")
        backend = ModelBackend(models_config=config)
        assert backend._models_config.security_scan == "anthropic/claude-sonnet-4-6"

    def test_api_key_stored(self) -> None:
        backend = ModelBackend(api_key="test-key")
        assert backend._api_key == "test-key"


class TestModelResolution:
    """Verify correct model string is selected per operation."""

    def test_resolves_security_scan(self) -> None:
        config = ModelsConfig(security_scan="anthropic/claude-sonnet-4-6")
        backend = ModelBackend(models_config=config)
        assert backend._resolve_model("security_scan") == "anthropic/claude-sonnet-4-6"

    def test_resolves_classify(self) -> None:
        config = ModelsConfig(classify="openai/gpt-4o")
        backend = ModelBackend(models_config=config)
        assert backend._resolve_model("classify") == "openai/gpt-4o"

    def test_resolves_generate(self) -> None:
        config = ModelsConfig(generate="ollama/llama3")
        backend = ModelBackend(models_config=config)
        assert backend._resolve_model("generate") == "ollama/llama3"

    def test_resolves_judge(self) -> None:
        config = ModelsConfig(judge="anthropic/claude-opus-4-6")
        backend = ModelBackend(models_config=config)
        assert backend._resolve_model("judge") == "anthropic/claude-opus-4-6"

    def test_unknown_operation_raises(self) -> None:
        backend = ModelBackend()
        with pytest.raises(ModelBackendError, match="Unknown operation"):
            backend._resolve_model("nonexistent")


class TestEmptyModelString:
    """Verify ModelBackendError when operation has no model configured."""

    def test_empty_security_scan_raises(self) -> None:
        config = ModelsConfig(security_scan="")
        backend = ModelBackend(models_config=config)
        with pytest.raises(ModelBackendError, match="No model configured"):
            backend.completion(
                operation="security_scan",
                system_prompt="test",
                user_message="test",
            )

    def test_empty_classify_raises(self) -> None:
        backend = ModelBackend(models_config=ModelsConfig())
        with pytest.raises(ModelBackendError, match="No model configured.*classify"):
            backend.completion(
                operation="classify",
                system_prompt="test",
                user_message="test",
            )


class TestRetryLogic:
    """Mock litellm.completion to verify retry behavior."""

    def test_retries_on_rate_limit(self) -> None:
        """Fail twice with retryable error, succeed on third attempt."""
        mock_litellm = MagicMock()

        # Create a custom exception class for rate limiting
        rate_limit_error = type("RateLimitError", (Exception,), {})
        mock_litellm.exceptions.RateLimitError = rate_limit_error
        mock_litellm.exceptions.ServiceUnavailableError = type(
            "ServiceUnavailableError", (Exception,), {}
        )
        mock_litellm.exceptions.Timeout = type("Timeout", (Exception,), {})

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "response text"

        mock_litellm.completion.side_effect = [
            rate_limit_error("rate limited"),
            rate_limit_error("rate limited again"),
            mock_response,
        ]

        config = ModelsConfig(security_scan="anthropic/claude-sonnet-4-6")
        backend = ModelBackend(models_config=config)

        with patch.dict(
            "sys.modules", {"litellm": mock_litellm, "litellm.exceptions": mock_litellm.exceptions}
        ):
            result = backend.completion(
                operation="security_scan",
                system_prompt="test",
                user_message="test",
            )

        assert result == "response text"
        assert mock_litellm.completion.call_count == 3

    def test_exhausted_retries_raises(self) -> None:
        """All 3 attempts fail with retryable error."""
        mock_litellm = MagicMock()
        rate_limit_error = type("RateLimitError", (Exception,), {})
        mock_litellm.exceptions.RateLimitError = rate_limit_error
        mock_litellm.exceptions.ServiceUnavailableError = type(
            "ServiceUnavailableError", (Exception,), {}
        )
        mock_litellm.exceptions.Timeout = type("Timeout", (Exception,), {})

        mock_litellm.completion.side_effect = rate_limit_error("rate limited")

        config = ModelsConfig(security_scan="anthropic/claude-sonnet-4-6")
        backend = ModelBackend(models_config=config)

        with patch.dict(
            "sys.modules", {"litellm": mock_litellm, "litellm.exceptions": mock_litellm.exceptions}
        ):
            with pytest.raises(ModelBackendError, match="failed after 3 retries"):
                backend.completion(
                    operation="security_scan",
                    system_prompt="test",
                    user_message="test",
                )

    def test_non_retryable_error_raises_immediately(self) -> None:
        """Non-retryable errors should raise immediately without retry."""
        mock_litellm = MagicMock()
        mock_litellm.exceptions.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_litellm.exceptions.ServiceUnavailableError = type(
            "ServiceUnavailableError", (Exception,), {}
        )
        mock_litellm.exceptions.Timeout = type("Timeout", (Exception,), {})
        mock_litellm.completion.side_effect = ValueError("bad input")

        config = ModelsConfig(security_scan="anthropic/claude-sonnet-4-6")
        backend = ModelBackend(models_config=config)

        with patch.dict(
            "sys.modules", {"litellm": mock_litellm, "litellm.exceptions": mock_litellm.exceptions}
        ):
            with pytest.raises(ModelBackendError, match="LLM completion failed"):
                backend.completion(
                    operation="security_scan",
                    system_prompt="test",
                    user_message="test",
                )

        assert mock_litellm.completion.call_count == 1


class TestLiteLLMUnavailable:
    """Verify graceful ImportError message if litellm not installed."""

    def test_import_error_message(self) -> None:
        config = ModelsConfig(security_scan="anthropic/claude-sonnet-4-6")
        backend = ModelBackend(models_config=config)

        with patch.dict("sys.modules", {"litellm": None}):
            with pytest.raises(ImportError, match="litellm package is required"):
                backend.completion(
                    operation="security_scan",
                    system_prompt="test",
                    user_message="test",
                )


class TestScannerIntegrationWithBackend:
    """Verify Scanner constructs correctly with a ModelBackend."""

    def test_scanner_with_backend_layers_1_2_3(self, tmp_path: Path) -> None:
        from open_workspace_builder.security.scanner import Scanner

        mock_backend = MagicMock()
        mock_backend.completion.return_value = '{"verdict": "clean", "flags": []}'

        f = tmp_path / "test.md"
        f.write_text("# Safe content", encoding="utf-8")

        scanner = Scanner(layers=(1, 2, 3), backend=mock_backend)
        verdict = scanner.scan_file(f)

        assert verdict.verdict == "clean"
        mock_backend.completion.assert_called_once()

    def test_scanner_layers_1_2_no_backend(self, tmp_path: Path) -> None:
        """Layers 1+2 work without any backend."""
        from open_workspace_builder.security.scanner import Scanner

        f = tmp_path / "test.md"
        f.write_text("# Safe content", encoding="utf-8")

        scanner = Scanner(layers=(1, 2))
        verdict = scanner.scan_file(f)

        assert verdict.verdict == "clean"

    def test_scanner_layer3_skipped_without_backend(self, tmp_path: Path) -> None:
        """Layer 3 requested but no backend — gracefully skipped."""
        from open_workspace_builder.security.scanner import Scanner

        f = tmp_path / "test.md"
        f.write_text("# Safe content", encoding="utf-8")

        scanner = Scanner(layers=(1, 2, 3))
        verdict = scanner.scan_file(f)

        assert verdict.verdict == "clean"
        # No semantic error flag added — layer was just skipped
        assert all(f.layer != 3 for f in verdict.flags)


class TestEmptyResponse:
    """Verify ModelBackendError when model returns None content."""

    def test_none_content_raises(self) -> None:
        mock_litellm = MagicMock()
        mock_litellm.exceptions.RateLimitError = type("RateLimitError", (Exception,), {})
        mock_litellm.exceptions.ServiceUnavailableError = type(
            "ServiceUnavailableError", (Exception,), {}
        )
        mock_litellm.exceptions.Timeout = type("Timeout", (Exception,), {})

        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        mock_litellm.completion.return_value = mock_response

        config = ModelsConfig(security_scan="anthropic/claude-sonnet-4-6")
        backend = ModelBackend(models_config=config)

        with patch.dict(
            "sys.modules", {"litellm": mock_litellm, "litellm.exceptions": mock_litellm.exceptions}
        ):
            with pytest.raises(ModelBackendError, match="empty response"):
                backend.completion(
                    operation="security_scan",
                    system_prompt="test",
                    user_message="test",
                )
