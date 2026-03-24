"""Environment variable secrets backend."""

from __future__ import annotations

import os

_KNOWN_KEYS = (
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "OWB_API_KEY",
    "LITELLM_API_KEY",
)


class EnvVarBackend:
    """Reads secrets from environment variables."""

    def get(self, key: str) -> str | None:
        """Read key from os.environ. Returns None if not set."""
        return os.environ.get(key)

    def set(self, key: str, value: str) -> None:
        """Set key in os.environ (ephemeral — only persists for this process)."""
        os.environ[key] = value

    def delete(self, key: str) -> None:
        """Remove key from os.environ. No-op if not set."""
        os.environ.pop(key, None)

    def list_keys(self) -> list[str]:
        """Return known OWB key names that are currently set in the environment."""
        return [k for k in _KNOWN_KEYS if k in os.environ]

    def backend_name(self) -> str:
        """Return backend identifier."""
        return "env"
