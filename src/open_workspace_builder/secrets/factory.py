"""Backend factory — routes to himitsubako backends.

.. deprecated:: 1.11.0
    Use ``himitsubako`` directly. This module will be removed in v1.12.0.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from himitsubako.backends.protocol import SecretBackend


def get_backend(config: object) -> SecretBackend:
    """Instantiate the configured secrets backend via himitsubako.

    Args:
        config: A SecretsConfig object with a ``backend`` field and
                backend-specific options.

    Raises:
        ValueError: If the backend name is not recognized.
    """
    backend_name = getattr(config, "backend", "env")

    if backend_name == "env":
        from himitsubako.backends.env import EnvBackend

        return EnvBackend()

    if backend_name == "sops":
        from himitsubako.backends.sops import SopsBackend

        secrets_file = getattr(config, "sops_secrets_file", ".secrets.enc.yaml")
        return SopsBackend(secrets_file=secrets_file)

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
