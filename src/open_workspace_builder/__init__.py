"""Open Workspace Builder — scaffold and maintain AI coding workspaces."""

from importlib.metadata import PackageNotFoundError, version


def _get_version() -> str:
    """Derive version from installed package metadata.

    Falls back to reading pyproject.toml for editable/development installs
    where the installed metadata may be stale.
    """
    try:
        v = version("open-workspace-builder")
    except PackageNotFoundError:
        v = None

    if v is not None:
        # Validate against pyproject.toml when running from source tree.
        # This catches the case where the workspace venv has a stale install.
        import re
        from pathlib import Path

        pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
        if pyproject.is_file():
            match = re.search(
                r'^version\s*=\s*"([^"]+)"',
                pyproject.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if match and match.group(1) != v:
                return match.group(1)
        return v

    # Fallback: read pyproject.toml directly (development/editable install).
    import re
    from pathlib import Path

    pyproject = Path(__file__).resolve().parent.parent.parent / "pyproject.toml"
    if pyproject.is_file():
        match = re.search(
            r'^version\s*=\s*"([^"]+)"',
            pyproject.read_text(encoding="utf-8"),
            re.MULTILINE,
        )
        if match:
            return match.group(1)

    return "0.0.0"


__version__ = _get_version()
