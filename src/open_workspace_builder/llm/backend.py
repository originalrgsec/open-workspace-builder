"""Model-agnostic LLM backend using LiteLLM for provider routing."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.config import ModelsConfig


class ModelBackendError(Exception):
    """Raised when the model backend cannot complete a request."""


_VALID_OPERATIONS = frozenset({"classify", "generate", "judge", "security_scan"})


def _load_retryable_exceptions() -> tuple[type[Exception], ...]:
    """Load retryable exception types from litellm, if available.

    Called once per ``completion()``; litellm is already imported earlier
    in the function so the exceptions import is a fast no-op. Not cached
    because tests mock ``litellm.exceptions`` via ``sys.modules`` patches
    and rely on a fresh import each call.
    """
    try:
        from litellm.exceptions import (  # type: ignore[import-untyped]
            RateLimitError,
            ServiceUnavailableError,
            Timeout,
        )

        return (RateLimitError, ServiceUnavailableError, Timeout)
    except ImportError:
        return ()


class ModelBackend:
    """Model-agnostic LLM backend using LiteLLM for provider routing."""

    def __init__(
        self,
        models_config: ModelsConfig | None = None,
        api_key: str | None = None,
    ) -> None:
        if models_config is None:
            from open_workspace_builder.config import ModelsConfig as _MC

            models_config = _MC()
        self._models_config = models_config
        self._api_key = api_key

    def _resolve_model(self, operation: str) -> str:
        """Resolve the model string for a given operation."""
        if operation not in _VALID_OPERATIONS:
            raise ModelBackendError(
                f"Unknown operation '{operation}'. "
                f"Valid operations: {', '.join(sorted(_VALID_OPERATIONS))}"
            )
        model = getattr(self._models_config, operation, "")
        if not model:
            raise ModelBackendError(
                f"No model configured for operation '{operation}'. "
                f"Set models.{operation} in your config file."
            )
        return model

    def completion(
        self,
        operation: str,
        system_prompt: str,
        user_message: str,
        max_tokens: int = 1024,
        response_format: str = "json",
    ) -> str:
        """Send a completion request, return the response text.

        Resolves model string from config based on operation name.
        Raises ModelBackendError if the model string is empty or provider is unreachable.
        """
        model = self._resolve_model(operation)

        try:
            import litellm  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "litellm package is required for LLM operations. "
                "Install with: pip install 'open-workspace-builder[llm]'"
            ) from exc

        retryable = _load_retryable_exceptions()
        backoff_delays = (1.0, 2.0, 4.0)
        last_error: Exception | None = None

        for attempt in range(3):
            try:
                kwargs: dict = {
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    "max_tokens": max_tokens,
                }
                if self._api_key:
                    kwargs["api_key"] = self._api_key

                response = litellm.completion(**kwargs)
                content = response.choices[0].message.content
                if content is None:
                    raise ModelBackendError("Model returned empty response.")
                return content

            except retryable as exc:  # type: ignore[misc]
                last_error = exc
                if attempt < 2:
                    time.sleep(backoff_delays[attempt])
                continue

            except ImportError:
                raise

            except ModelBackendError:
                raise

            except Exception as exc:
                raise ModelBackendError(
                    f"LLM completion failed for operation '{operation}' with model '{model}': {exc}"
                ) from exc

        raise ModelBackendError(
            f"LLM completion failed after 3 retries for operation '{operation}' "
            f"with model '{model}': {last_error}"
        ) from last_error
