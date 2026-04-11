#!/usr/bin/env python3
"""Generate a CycloneDX SBOM for OWB's own Python dependency tree.

Used by the GitHub Releases workflow (AD-17) to produce the project SBOM
attached as a Release asset. The SBOM describes OWB's installed Python
dependency tree so downstream consumers can audit OWB's supply chain
independently of PyPI metadata scraping.

Implementation strategy (per AD-17, revised 2026-04-11):

1. Create an isolated venv so the SBOM reflects `open-workspace-builder`'s
   declared dependencies and their transitive closure, not whatever
   happened to be preinstalled on the GitHub Actions runner.
2. Install the wheel into the isolated venv. **Only the wheel** — no
   supplementary tooling, so the venv's package set contains exactly
   OWB plus its transitive deps.
3. Invoke the isolated venv's Python to enumerate installed
   distributions via `importlib.metadata`. The enumeration runs inside
   the measured venv and emits JSON to stdout.
4. Back in the host environment, construct a CycloneDX 1.6 BOM via
   `cyclonedx-python-lib` (already an OWB dependency via the `[sbom]`
   extra). OWB itself is placed in `metadata.component` as an
   APPLICATION; its dependencies populate `components` as LIBRARY
   entries, each with a canonical PEP 503 `pkg:pypi/...` purl.
5. Serialize with `JsonV1Dot6` for byte-stable CycloneDX 1.6 output
   consistent with the workspace SBOM path (`owb sbom generate`).

The prior scaffold used `pip-audit --format cyclonedx-json` as the SBOM
emitter. Dry-run exercise on 2026-04-11 revealed three defects:
pip-audit (1) silently skipped OWB itself because it could not match
the local wheel against its vulnerability database, (2) produced a BOM
with no `metadata.component` pointer, and (3) polluted the component
list with pip-audit's own transitive dependencies (pip, msgpack,
CacheControl, filelock, and others). The direct construction approach
here produces a correct and consistent SBOM without introducing any
new third-party tooling beyond what OWB already depends on.

Usage:
    python scripts/generate_sbom.py \\
        --wheel dist/open_workspace_builder-1.9.0-py3-none-any.whl \\
        --version 1.9.0 \\
        --output dist/open-workspace-builder-1.9.0.cdx.json

Exit codes:
    0 — SBOM generated and validated
    1 — any failure (missing wheel, venv setup, enumeration error, etc.)
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess  # nosec B404 — controlled invocation, no shell, pinned argv
import sys
import tempfile
from pathlib import Path

from cyclonedx.model.bom import Bom
from cyclonedx.model.component import Component as CdxComponent
from cyclonedx.model.component import ComponentType
from cyclonedx.output.json import JsonV1Dot6
from packageurl import PackageURL


OWB_CANONICAL_NAME = "open-workspace-builder"

# Packages installed by `python -m venv` itself, not declared dependencies
# of the wheel under inspection. Filtering these out keeps the SBOM
# focused on OWB's actual dependency closure rather than the venv
# bootstrap layer. Names are compared after PEP 503 canonicalization.
VENV_BOOTSTRAP_PACKAGES = frozenset(
    {
        "pip",
        "setuptools",
        "wheel",
        "distribute",
        "pkg-resources",
    }
)


_ENUMERATE_DISTS = """
import importlib.metadata, json, sys
out = []
for d in importlib.metadata.distributions():
    name = d.metadata['Name']
    if not name:
        continue
    out.append({'name': name, 'version': d.version or ''})
json.dump(out, sys.stdout)
"""


def _venv_bin(venv_path: Path, name: str) -> Path:
    """Return the path to a venv binary, handling Windows layout."""
    if sys.platform == "win32":
        return venv_path / "Scripts" / f"{name}.exe"
    return venv_path / "bin" / name


def _canonical_pypi_name(name: str) -> str:
    """PEP 503 canonical name for purl construction."""
    return re.sub(r"[-_.]+", "-", name).lower()


def _enumerate_distributions(venv_python: Path) -> list[dict[str, str]]:
    """Return [{name, version}, ...] for every distribution in the venv."""
    result = subprocess.run(  # nosec B603 — argv is pinned, no shell
        [str(venv_python), "-c", _ENUMERATE_DISTS],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"dist enumeration failed (rc={result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    try:
        parsed = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"dist enumeration output is not valid JSON: {exc}") from exc
    if not isinstance(parsed, list):
        raise RuntimeError(f"dist enumeration output is not a list: {type(parsed).__name__}")
    return parsed


def _build_component(name: str, version: str, component_type: ComponentType) -> CdxComponent:
    canonical = _canonical_pypi_name(name)
    purl = PackageURL(type="pypi", name=canonical, version=version)
    return CdxComponent(
        type=component_type,
        name=name,
        version=version,
        purl=purl,
        bom_ref=str(purl),
    )


def build_bom(owb_name: str, owb_version: str, dists: list[dict[str, str]]) -> Bom:
    """Construct a CycloneDX Bom with OWB as metadata.component.

    Dependencies are added under `components`. The subject package
    itself is excluded from `components` to avoid a self-edge — it is
    already described by `metadata.component`.
    """
    bom = Bom()
    subject = _build_component(owb_name, owb_version, ComponentType.APPLICATION)
    if bom.metadata is not None:
        bom.metadata.component = subject

    owb_canonical = _canonical_pypi_name(owb_name)
    for dist in dists:
        name = dist.get("name", "")
        version = dist.get("version", "")
        if not name:
            continue
        canonical = _canonical_pypi_name(name)
        if canonical == owb_canonical:
            continue
        if canonical in VENV_BOOTSTRAP_PACKAGES:
            continue
        bom.components.add(_build_component(name, version, ComponentType.LIBRARY))

    return bom


def generate_sbom(wheel_path: Path, version: str, output_path: Path) -> None:
    """Generate a CycloneDX JSON SBOM for the given wheel.

    Raises FileNotFoundError if the wheel does not exist.
    Raises RuntimeError on any tooling failure or invalid output.
    """
    if not wheel_path.is_file():
        raise FileNotFoundError(f"wheel not found: {wheel_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="owb-sbom-") as tmpdir:
        venv_path = Path(tmpdir) / "venv"
        _run([sys.executable, "-m", "venv", str(venv_path)], "venv creation")

        pip = _venv_bin(venv_path, "pip")
        _run(
            [str(pip), "install", "--quiet", "--upgrade", "pip"],
            "pip upgrade",
        )
        _run(
            [str(pip), "install", "--quiet", str(wheel_path)],
            "wheel install",
        )

        venv_python = _venv_bin(venv_path, "python")
        dists = _enumerate_distributions(venv_python)

    bom = build_bom(OWB_CANONICAL_NAME, version, dists)
    serialized = JsonV1Dot6(bom).output_as_string(indent=2)

    parsed = json.loads(serialized)
    if parsed.get("bomFormat") != "CycloneDX":
        raise RuntimeError(
            f"generated BOM is not a CycloneDX document (bomFormat={parsed.get('bomFormat')})"
        )
    if parsed.get("metadata", {}).get("component", {}).get("name") != OWB_CANONICAL_NAME:
        raise RuntimeError("generated BOM does not identify OWB as metadata.component")

    output_path.write_text(serialized, encoding="utf-8")


def _run(argv: list[str], label: str) -> None:
    result = subprocess.run(  # nosec B603 — argv is pinned, no shell
        argv,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{label} failed (rc={result.returncode}): "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Generate a CycloneDX SBOM for a built OWB wheel (AD-17).",
    )
    parser.add_argument("--wheel", required=True, type=Path, help="Path to the built wheel.")
    parser.add_argument("--version", required=True, help="Release version string.")
    parser.add_argument("--output", required=True, type=Path, help="Output SBOM path.")
    args = parser.parse_args(argv[1:])

    try:
        generate_sbom(args.wheel, args.version, args.output)
    except (FileNotFoundError, RuntimeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"SBOM written to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
