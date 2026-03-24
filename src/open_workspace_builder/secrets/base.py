"""SecretsBackend protocol — common interface for all secrets implementations."""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
class SecretsBackend(Protocol):
    """Protocol for pluggable secrets storage backends."""

    def get(self, key: str) -> str | None:
        """Retrieve a secret by key. Returns None if not found."""
        ...

    def set(self, key: str, value: str) -> None:
        """Store a secret under the given key."""
        ...

    def delete(self, key: str) -> None:
        """Remove a secret by key. No-op if key does not exist."""
        ...

    def list_keys(self) -> list[str]:
        """List all known secret key names."""
        ...

    def backend_name(self) -> str:
        """Return the name of this backend (e.g., 'env', 'keyring', 'age')."""
        ...
