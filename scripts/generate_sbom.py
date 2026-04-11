#!/usr/bin/env python3
"""Generate a CycloneDX SBOM for OWB's own Python dependency tree.

Used by the GitHub Releases workflow (AD-17) to produce the project SBOM
attached as a Release asset. The SBOM describes OWB's installed Python
dependency tree, giving downstream consumers a canonical audit artifact
independent of PyPI metadata scraping.

Implementation strategy (per AD-17):

1. Create an isolated venv so the SBOM reflects `open-workspace-builder`'s
   declared dependencies and their transitive closure, not whatever
   happened to be preinstalled on the GitHub Actions runner.
2. Install the wheel plus `pip-audit` into the isolated venv.
3. Run `pip-audit --local --format cyclonedx-json` from the isolated venv.
   pip-audit is already a project dependency (`[sbom]` extra) so no new
   third-party tooling is introduced per AD-17 alternatives rejection.
4. Accept pip-audit exit codes 0 (clean) and 1 (vulnerabilities found) as
   success for SBOM generation — both produce a valid CycloneDX document.
   Any other exit code is a hard failure.
5. Validate the output is parseable JSON before declaring success.

Usage:
    python scripts/generate_sbom.py \\
        --wheel dist/open_workspace_builder-1.9.0-py3-none-any.whl \\
        --version 1.9.0 \\
        --output dist/open-workspace-builder-1.9.0.cdx.json

Exit codes:
    0 — SBOM generated and validated
    1 — any failure (missing wheel, venv setup, pip-audit error, invalid JSON)
"""

from __future__ import annotations

import argparse
import json
import subprocess  # nosec B404 — controlled invocation, no shell, pinned argv
import sys
import tempfile
from pathlib import Path


def _venv_bin(venv_path: Path, name: str) -> Path:
    """Return the path to a venv binary, handling Windows layout."""
    if sys.platform == "win32":
        return venv_path / "Scripts" / f"{name}.exe"
    return venv_path / "bin" / name


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
            [str(pip), "install", "--quiet", str(wheel_path), "pip-audit"],
            "wheel + pip-audit install",
        )

        pip_audit = _venv_bin(venv_path, "pip-audit")
        result = subprocess.run(  # nosec B603 — argv is pinned, no shell
            [
                str(pip_audit),
                "--local",
                "--format",
                "cyclonedx-json",
                "--output",
                str(output_path),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        # pip-audit: 0 = clean, 1 = vulnerabilities found. Both produce a
        # valid CycloneDX document. Any other exit code is a hard failure.
        if result.returncode not in (0, 1):
            raise RuntimeError(
                f"pip-audit failed (rc={result.returncode}): "
                f"{result.stderr.strip() or result.stdout.strip()}"
            )

    if not output_path.is_file():
        raise RuntimeError(f"pip-audit did not produce output at {output_path}")

    try:
        parsed = json.loads(output_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"pip-audit output is not valid JSON: {exc}") from exc

    if not isinstance(parsed, dict) or parsed.get("bomFormat") != "CycloneDX":
        raise RuntimeError(
            f"pip-audit output is not a CycloneDX document "
            f"(bomFormat={parsed.get('bomFormat') if isinstance(parsed, dict) else type(parsed).__name__})"
        )


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
        description="Generate a CycloneDX SBOM for a built OWB wheel (AD-17)."
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
