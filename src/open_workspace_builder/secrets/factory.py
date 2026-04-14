"""Backend factory — routes to himitsubako backends.

.. deprecated:: 1.11.0
    Use ``himitsubako`` directly. This module will be removed in v1.12.0.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from himitsubako.backends.protocol import SecretBackend


def _resolve_optional_path(raw: str | None, field_name: str) -> str | None:
    """Expand ``~`` in a configured path and fail loudly if it is missing.

    Args:
        raw: The raw path from config (may be ``None``, relative, absolute,
             or start with ``~``).
        field_name: The ``SecretsConfig`` field name, used in error messages
             so operators can trace the bad value back to their
             ``workspace.yaml``.

    Returns:
        The expanded absolute-or-relative path, or ``None`` if ``raw`` was
        ``None`` (preserving upstream defaults + env-var fallback).

    Raises:
        FileNotFoundError: If ``raw`` is set but the resolved path does not
            exist on disk. Silent fallback to the default location would
            mask operator misconfiguration (EC-3).
    """
    if raw is None:
        return None
    expanded = os.path.expanduser(raw)
    if not Path(expanded).exists():
        raise FileNotFoundError(
            f"{field_name} points at '{expanded}' but that path does not exist. "
            "Fix the path in workspace.yaml or unset the field to use the default."
        )
    return expanded


def get_backend(config: object) -> SecretBackend:
    """Instantiate the configured secrets backend via himitsubako.

    Args:
        config: A SecretsConfig object with a ``backend`` field and
                backend-specific options.

    Raises:
        ValueError: If the backend name is not recognized.
        FileNotFoundError: If ``sops_age_identity`` or ``sops_config_file``
            is configured but points at a non-existent path.
    """
    backend_name = getattr(config, "backend", "env")

    if backend_name == "env":
        from himitsubako.backends.env import EnvBackend

        return EnvBackend()

    if backend_name == "sops":
        from himitsubako.backends.sops import SopsBackend

        secrets_file = getattr(config, "sops_secrets_file", ".secrets.enc.yaml")
        age_identity = _resolve_optional_path(
            getattr(config, "sops_age_identity", None),
            "sops_age_identity",
        )
        sops_config_file = _resolve_optional_path(
            getattr(config, "sops_config_file", None),
            "sops_config_file",
        )
        return SopsBackend(
            secrets_file=secrets_file,
            age_identity=age_identity,
            sops_config_file=sops_config_file,
        )

    if backend_name == "keyring" or backend_name == "keychain":
        from himitsubako.backends.keychain import KeychainBackend

        service = getattr(config, "keyring_service", "open-workspace-builder")
        return KeychainBackend(service=service)

    if backend_name == "bitwarden":
        from himitsubako.backends.bitwarden import BitwardenBackend

        folder = getattr(config, "bitwarden_item", "himitsubako")
        return BitwardenBackend(folder=folder)

    raise ValueError(
        f"Unknown secrets backend '{backend_name}'. "
        f"Valid backends: env, sops, keyring, keychain, bitwarden"
    )
