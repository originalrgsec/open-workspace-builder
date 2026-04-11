"""OWB-S107c — Workspace SBOM drift verification.

Regenerates a workspace's SBOM in-memory and compares it against a
canonical on-disk SBOM file (default ``.owb/sbom.cdx.json``). The result
is a :class:`~open_workspace_builder.sbom.diff.DiffResult` so callers can
render JSON or text and decide how to gate.

This is the pre-commit / CI surface: authors commit
``.owb/sbom.cdx.json`` alongside source, and ``owb sbom verify`` is a
fast drift check.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from open_workspace_builder.sbom.builder import build_bom, serialize_bom
from open_workspace_builder.sbom.diff import DiffResult, diff_boms, load_bom
from open_workspace_builder.sbom.discover import discover_components

DEFAULT_CANONICAL_RELPATH = (".owb", "sbom.cdx.json")


@dataclass(frozen=True)
class VerifyOutcome:
    """Result of a verify run.

    ``ok`` is True when the regenerated SBOM matches the canonical one on
    every comparable field. ``diff`` carries the per-field deltas when
    ``ok`` is False.
    """

    ok: bool
    diff: DiffResult


def default_canonical_path(workspace: Path) -> Path:
    """Return the conventional canonical SBOM location for a workspace."""
    p = workspace
    for part in DEFAULT_CANONICAL_RELPATH:
        p = p / part
    return p


def verify_workspace(
    *,
    workspace: Path,
    canonical: Path | None = None,
) -> VerifyOutcome:
    """Verify that a workspace's current state matches its canonical SBOM.

    Args:
        workspace: Workspace root to scan.
        canonical: Path to the canonical SBOM file. Defaults to
            ``<workspace>/.owb/sbom.cdx.json``.

    Returns:
        :class:`VerifyOutcome` with ``ok=True`` on a clean match.

    Raises:
        FileNotFoundError: workspace or canonical SBOM is missing.
        ValueError: canonical SBOM is malformed.
    """
    if not workspace.is_dir():
        raise FileNotFoundError(f"Workspace not found: {workspace}")

    canonical_path = canonical or default_canonical_path(workspace)
    canonical_bom = load_bom(canonical_path)

    components = discover_components(workspace)
    bom_obj = build_bom(components)
    regenerated_json = serialize_bom(bom_obj)
    regenerated_bom = json.loads(regenerated_json)

    diff = diff_boms(canonical_bom, regenerated_bom)
    return VerifyOutcome(ok=not diff.has_differences, diff=diff)
