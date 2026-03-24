"""OS keyring secrets backend."""

from __future__ import annotations

import json

_METADATA_KEY = "_owb_keys"


class KeyringBackend:
    """Stores secrets in the OS keyring via the keyring package."""

    def __init__(self, service: str = "open-workspace-builder") -> None:
        self._service = service
        self._keyring = _import_keyring()

    def get(self, key: str) -> str | None:
        """Retrieve secret from keyring. Returns None if not found."""
        return self._keyring.get_password(self._service, key)

    def set(self, key: str, value: str) -> None:
        """Store secret in keyring and update the metadata key list."""
        self._keyring.set_password(self._service, key, value)
        self._add_to_metadata(key)

    def delete(self, key: str) -> None:
        """Remove secret from keyring and update the metadata key list."""
        try:
            self._keyring.delete_password(self._service, key)
        except Exception:
            pass
        self._remove_from_metadata(key)

    def list_keys(self) -> list[str]:
        """Return stored key names from the metadata key."""
        raw = self._keyring.get_password(self._service, _METADATA_KEY)
        if raw is None:
            return []
        try:
            keys = json.loads(raw)
            return keys if isinstance(keys, list) else []
        except (json.JSONDecodeError, TypeError):
            return []

    def backend_name(self) -> str:
        """Return backend identifier."""
        return "keyring"

    @classmethod
    def is_available(cls) -> bool:
        """Check if keyring is importable and the active backend is usable."""
        try:
            import keyring as kr  # type: ignore[import-untyped]

            backend = kr.get_keyring()
            return "fail" not in type(backend).__module__.lower()
        except ImportError:
            return False

    def _add_to_metadata(self, key: str) -> None:
        """Add a key name to the persisted metadata list."""
        keys = self.list_keys()
        if key not in keys:
            keys.append(key)
            self._keyring.set_password(self._service, _METADATA_KEY, json.dumps(keys))

    def _remove_from_metadata(self, key: str) -> None:
        """Remove a key name from the persisted metadata list."""
        keys = self.list_keys()
        if key in keys:
            keys.remove(key)
            self._keyring.set_password(self._service, _METADATA_KEY, json.dumps(keys))


def _import_keyring():  # type: ignore[no-untyped-def]
    """Import keyring or raise ImportError with install instructions."""
    try:
        import keyring  # type: ignore[import-untyped]

        return keyring
    except ImportError as exc:
        raise ImportError(
            "keyring package is required for the keyring secrets backend. "
            "Install with: pip install 'open-workspace-builder[keyring]'"
        ) from exc
