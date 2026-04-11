"""OWB-S107a — Deterministic example SBOM generator.

Used by the CI drift check (``tests/sbom/test_example_fixture.py``) to
regenerate ``examples/sbom/example.cdx.json`` byte-identically so that
drift against the committed copy is detectable.

The serial and timestamp are hard-coded so that regeneration is stable
across machines and times. Any change to the fixture workspace at
``tests/fixtures/sbom-example/`` or to the normalization algorithm will
intentionally produce drift and fail the test, prompting a manual
regenerate step.
"""

from __future__ import annotations

from pathlib import Path

from open_workspace_builder.sbom.builder import BomOptions, build_bom, serialize_bom
from open_workspace_builder.sbom.discover import discover_components

EXAMPLE_SERIAL = "urn:uuid:00000000-0000-4107-a000-000000000107"
EXAMPLE_TIMESTAMP = "2026-04-10T00:00:00+00:00"

_REPO_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_WORKSPACE = _REPO_ROOT / "tests" / "fixtures" / "sbom-example"
EXAMPLE_SBOM_PATH = _REPO_ROOT / "examples" / "sbom" / "example.cdx.json"


def regenerate_example_sbom() -> str:
    """Produce the byte-stable example SBOM JSON string.

    Returns:
        The serialized JSON string, suitable for writing to disk or for
        comparison against the committed fixture.
    """
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
