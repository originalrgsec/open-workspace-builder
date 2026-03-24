"""Pluggable secrets backend for API key storage and retrieval."""

from open_workspace_builder.secrets.base import SecretsBackend
from open_workspace_builder.secrets.factory import get_backend
from open_workspace_builder.secrets.resolver import resolve_key

__all__ = ["SecretsBackend", "get_backend", "resolve_key"]
