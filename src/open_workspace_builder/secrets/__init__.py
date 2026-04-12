"""Compatibility shim — delegates to himitsubako.

.. deprecated:: 1.11.0
    Import from ``himitsubako`` directly. This shim will be removed in 1.12.0.
"""

from __future__ import annotations

import warnings
from typing import TYPE_CHECKING

from himitsubako.backends.protocol import SecretBackend as SecretsBackend

from open_workspace_builder.secrets.factory import get_backend
from open_workspace_builder.secrets.resolver import resolve_key

if not TYPE_CHECKING:
    warnings.warn(
        "open_workspace_builder.secrets is deprecated. "
        "Import from himitsubako directly. This shim will be removed in v1.12.0.",
        DeprecationWarning,
        stacklevel=2,
    )

__all__ = ["SecretsBackend", "get_backend", "resolve_key"]
