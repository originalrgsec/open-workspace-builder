"""Bitwarden CLI secrets backend."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


_DEFAULT_ITEM_NAME = "OWB API Keys"


@dataclass(frozen=True)
class _BwItem:
    """Immutable snapshot of a Bitwarden item."""

    item_id: str
    fields: tuple[tuple[str, str], ...]

    def field_value(self, name: str) -> str | None:
        for k, v in self.fields:
            if k == name:
                return v
        return None

    def field_names(self) -> list[str]:
        return [k for k, _ in self.fields]

    def with_field(self, name: str, value: str) -> _BwItem:
        """Return a new item with the field added or updated."""
        new_fields = [(k, v) for k, v in self.fields if k != name]
        new_fields.append((name, value))
        return _BwItem(item_id=self.item_id, fields=tuple(new_fields))

    def without_field(self, name: str) -> _BwItem:
        """Return a new item with the named field removed."""
        new_fields = [(k, v) for k, v in self.fields if k != name]
        return _BwItem(item_id=self.item_id, fields=tuple(new_fields))

    def to_fields_json(self) -> list[dict[str, Any]]:
        """Serialize fields to the Bitwarden JSON format."""
        return [{"name": k, "value": v, "type": 0} for k, v in self.fields]


class BitwardenBackend:
    """Stores secrets as custom fields on a Bitwarden vault item."""

    def __init__(self, item_name: str = _DEFAULT_ITEM_NAME) -> None:
        self._item_name = item_name

    def get(self, key: str) -> str | None:
        """Retrieve a secret by custom field name."""
        item = self._fetch_item()
        if item is None:
            return None
        return item.field_value(key)

    def set(self, key: str, value: str) -> None:
        """Store a secret as a custom field, creating the item if needed."""
        item = self._fetch_item()
        if item is None:
            self._create_item_with_field(key, value)
            return
        updated = item.with_field(key, value)
        self._save_item(updated)

    def delete(self, key: str) -> None:
        """Remove a custom field. No-op if the item or field does not exist."""
        item = self._fetch_item()
        if item is None:
            return
        if item.field_value(key) is None:
            return
        updated = item.without_field(key)
        self._save_item(updated)

    def list_keys(self) -> list[str]:
        """List all custom field names on the item."""
        item = self._fetch_item()
        if item is None:
            return []
        return item.field_names()

    def backend_name(self) -> str:
        return "bitwarden"

    @classmethod
    def is_available(cls) -> bool:
        """Check if the bw CLI is on PATH and returns valid status JSON."""
        if shutil.which("bw") is None:
            return False
        try:
            result = subprocess.run(
                ["bw", "status"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            json.loads(result.stdout)
            return True
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return False

    def _get_session(self) -> list[str]:
        """Return --session flag if BW_SESSION is set."""
        import os

        session = os.environ.get("BW_SESSION", "")
        if session:
            return ["--session", session]
        return []

    def _run_bw(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run a bw CLI command with optional session token."""
        cmd = ["bw"] + args + self._get_session()
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )

    def _fetch_item(self) -> _BwItem | None:
        """Fetch the named item from Bitwarden. Returns None if not found."""
        result = self._run_bw(["get", "item", self._item_name])
        if result.returncode != 0:
            return None
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return None
        return _parse_bw_item(data)

    def _save_item(self, item: _BwItem) -> None:
        """Update an existing item's custom fields via bw edit item."""
        import base64

        current = self._run_bw(["get", "item", self._item_name])
        if current.returncode != 0:
            raise RuntimeError(f"Failed to fetch item for update: {current.stderr}")
        data = json.loads(current.stdout)
        data["fields"] = item.to_fields_json()
        encoded = base64.b64encode(json.dumps(data).encode()).decode()
        result = self._run_bw(["edit", "item", item.item_id, encoded])
        if result.returncode != 0:
            raise RuntimeError(f"bw edit item failed: {result.stderr}")

    def _create_item_with_field(self, key: str, value: str) -> None:
        """Create a new Bitwarden item with a single custom field."""
        import base64

        template = {
            "organizationId": None,
            "folderId": None,
            "type": 2,
            "name": self._item_name,
            "notes": None,
            "secureNote": {"type": 0},
            "fields": [{"name": key, "value": value, "type": 0}],
        }
        encoded = base64.b64encode(json.dumps(template).encode()).decode()
        result = self._run_bw(["create", "item", encoded])
        if result.returncode != 0:
            raise RuntimeError(f"bw create item failed: {result.stderr}")


def _parse_bw_item(data: dict[str, Any]) -> _BwItem:
    """Parse Bitwarden JSON into an immutable _BwItem."""
    item_id = data.get("id", "")
    raw_fields = data.get("fields") or []
    fields = tuple(
        (f.get("name", ""), f.get("value", ""))
        for f in raw_fields
        if isinstance(f, dict)
    )
    return _BwItem(item_id=item_id, fields=fields)
