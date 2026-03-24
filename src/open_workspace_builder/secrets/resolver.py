"""Runtime key resolution with fallback chain."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from open_workspace_builder.secrets.base import SecretsBackend


def resolve_key(
    key_name: str,
    backend: SecretsBackend | None,
    cli_override: str | None = None,
    env_var: str | None = None,
) -> str:
    """Resolve an API key through the fallback chain.

    Order: CLI flag -> configured backend -> environment variable -> raise error.

    Args:
        key_name: Logical name of the key (e.g., "anthropic_api_key").
        backend: Secrets backend to check, or None to skip.
        cli_override: Value provided directly via CLI flag.
        env_var: Environment variable name to check. If None, derived from key_name.upper().

    Returns:
        The resolved key value.

    Raises:
        ValueError: If the key cannot be found in any source.
    """
    # Step 1: CLI override
    if cli_override is not None and cli_override.strip():
        return cli_override.strip()

    # Step 2: Configured backend
    if backend is not None:
        value = backend.get(key_name)
        if value is not None and value.strip():
            return value.strip()

    # Step 3: Environment variable
    import os

    resolved_env = env_var if env_var is not None else key_name.upper()
    env_value = os.environ.get(resolved_env)
    if env_value is not None and env_value.strip():
        return env_value.strip()

    # Step 4: Error
    sources = ["CLI flag"]
    if backend is not None:
        sources.append(f"{backend.backend_name()} backend")
    sources.append(f"${resolved_env} environment variable")

    raise ValueError(
        f"Could not resolve key '{key_name}'. "
        f"Checked: {', '.join(sources)}. "
        f"Set the key via one of these sources."
    )
