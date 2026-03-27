"""1Password CLI secrets backend."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any


_DEFAULT_VAULT = "Development"
_DEFAULT_ITEM_NAME = "OWB API Keys"


@dataclass(frozen=True)
class _OpItem:
    """Immutable snapshot of a 1Password item's fields."""

    fields: tuple[tuple[str, str], ...]

    def field_value(self, label: str) -> str | None:
        for k, v in self.fields:
            if k == label:
                return v
        return None

    def field_labels(self) -> list[str]:
        return [k for k, _ in self.fields]


class OnePasswordBackend:
    """Stores secrets as fields on a 1Password vault item."""

    def __init__(self, vault_name: str = _DEFAULT_VAULT) -> None:
        self._vault = vault_name
        self._item_name = _DEFAULT_ITEM_NAME

    def get(self, key: str) -> str | None:
        """Retrieve a field value from the 1Password item.

        Returns None if the item or field does not exist. Raises RuntimeError
        if the CLI is not installed or not authenticated.
        """
        if shutil.which("op") is None:
            raise RuntimeError(
                "1Password CLI (op) is not installed. "
                "Install it from https://1password.com/downloads/command-line/"
            )
        result = self._run_op([
            "item", "get", self._item_name,
            "--fields", f"label={key}",
            "--vault", self._vault,
        ])
        if result.returncode != 0:
            stderr = result.stderr.lower()
            if "not found" in stderr or "doesn't exist" in stderr or "no item" in stderr:
                return None
            if "sign in" in stderr or "not signed in" in stderr or "unauthorized" in stderr:
                raise RuntimeError(
                    f"1Password is not authenticated. "
                    f"Run 'op signin' first. Detail: {result.stderr.strip()}"
                )
            raise RuntimeError(
                f"op item get failed: {result.stderr.strip()}"
            )
        value = result.stdout.strip()
        return value if value else None

    def set(self, key: str, value: str) -> None:
        """Set a field on the 1Password item, creating the item if needed."""
        result = self._run_op([
            "item", "edit", self._item_name,
            f"{key}={value}",
            "--vault", self._vault,
        ])
        if result.returncode != 0:
            if "not found" in result.stderr.lower() or "doesn't exist" in result.stderr.lower():
                self._create_item_with_field(key, value)
            else:
                raise RuntimeError(f"op item edit failed: {result.stderr}")

    def delete(self, key: str) -> None:
        """Remove a field from the item. No-op if not found."""
        result = self._run_op([
            "item", "edit", self._item_name,
            f"{key}[delete]",
            "--vault", self._vault,
        ])
        if result.returncode != 0:
            return

    def list_keys(self) -> list[str]:
        """List all field labels on the item."""
        result = self._run_op([
            "item", "get", self._item_name,
            "--format", "json",
            "--vault", self._vault,
        ])
        if result.returncode != 0:
            return []
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []
        return _extract_field_labels(data)

    def backend_name(self) -> str:
        return "onepassword"

    @classmethod
    def is_available(cls) -> bool:
        """Check if the op CLI is on PATH and authenticated."""
        if shutil.which("op") is None:
            return False
        try:
            result = subprocess.run(
                ["op", "account", "list", "--format", "json"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                return False
            accounts = json.loads(result.stdout)
            return isinstance(accounts, list) and len(accounts) > 0
        except (subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
            return False

    def _run_op(self, args: list[str]) -> subprocess.CompletedProcess[str]:
        """Run an op CLI command with environment for headless auth."""
        env = dict(os.environ)
        return subprocess.run(
            ["op"] + args,
            capture_output=True,
            text=True,
            timeout=30,
            env=env,
        )

    def _create_item_with_field(self, key: str, value: str) -> None:
        """Create a new Secure Note item with one field."""
        result = self._run_op([
            "item", "create",
            "--category", "Secure Note",
            "--title", self._item_name,
            "--vault", self._vault,
            f"{key}={value}",
        ])
        if result.returncode != 0:
            raise RuntimeError(f"op item create failed: {result.stderr}")


def _extract_field_labels(data: dict[str, Any]) -> list[str]:
    """Extract user-defined field labels from 1Password item JSON."""
    raw_fields = data.get("fields") or []
    labels: list[str] = []
    for f in raw_fields:
        if not isinstance(f, dict):
            continue
        label = f.get("label", "")
        purpose = f.get("purpose", "")
        if label and not purpose:
            labels.append(label)
    return labels
