"""OWB-S107a / S120 — Deterministic example SBOM generator.

Used by the CI drift check (``tests/sbom/test_example_fixture.py``) to
regenerate the committed example SBOM byte-identically so that drift
against the committed copy is detectable.

S120 moved the fixture workspace and example SBOM into package data
(``sbom/_data/``) so that path resolution works in both source-tree
and installed-wheel layouts via ``importlib.resources``.
"""

from __future__ import annotations

from importlib.resources import files
from pathlib import Path

from open_workspace_builder.sbom.builder import BomOptions, build_bom, serialize_bom
from open_workspace_builder.sbom.discover import discover_components

EXAMPLE_SERIAL = "urn:uuid:00000000-0000-4107-a000-000000000107"
EXAMPLE_TIMESTAMP = "2026-04-10T00:00:00+00:00"

_DATA = files("open_workspace_builder.sbom") / "_data"
FIXTURE_WORKSPACE = Path(str(_DATA / "fixture"))
EXAMPLE_SBOM_PATH = Path(str(_DATA / "example.cdx.json"))


def regenerate_example_sbom() -> str:
    """Produce the byte-stable example SBOM JSON string."""
    components = discover_components(FIXTURE_WORKSPACE)
    options = BomOptions(serial=EXAMPLE_SERIAL, timestamp=EXAMPLE_TIMESTAMP)
    bom = build_bom(components, options=options)
    return serialize_bom(bom) + "\n"


def write_example_sbom() -> Path:
    """Regenerate and write the example SBOM to its canonical location."""
    content = regenerate_example_sbom()
    EXAMPLE_SBOM_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXAMPLE_SBOM_PATH.write_text(content, encoding="utf-8")
    return EXAMPLE_SBOM_PATH


if __name__ == "__main__":  # pragma: no cover
    path = write_example_sbom()
    print(f"Example SBOM written to {path}")
