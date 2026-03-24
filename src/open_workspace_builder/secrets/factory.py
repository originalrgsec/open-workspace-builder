"""Backend factory — instantiates the configured secrets backend."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.secrets.base import SecretsBackend


def get_backend(config: object) -> SecretsBackend:
    """Instantiate the configured secrets backend.

    Args:
        config: A SecretsConfig object with backend, age_identity, age_secrets_dir,
                and keyring_service fields.

    Raises:
        ValueError: If the backend name is not recognized.
    """
    backend_name = getattr(config, "backend", "env")

    if backend_name == "env":
        from open_workspace_builder.secrets.env_backend import EnvVarBackend

        return EnvVarBackend()

    if backend_name == "keyring":
        from open_workspace_builder.secrets.keyring_backend import KeyringBackend

        service = getattr(config, "keyring_service", "open-workspace-builder")
        return KeyringBackend(service=service)

    if backend_name == "age":
        from open_workspace_builder.secrets.age_backend import AgeBackend

        identity = getattr(config, "age_identity", "~/.config/owb/key.txt")
        secrets_dir = getattr(config, "age_secrets_dir", "") or "~/.owb/secrets"
        return AgeBackend(identity_path=identity, secrets_dir=secrets_dir)

    raise ValueError(
        f"Unknown secrets backend '{backend_name}'. "
        f"Valid backends: env, keyring, age"
    )
