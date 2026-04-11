"""Tests for scripts/generate_sbom.py (AD-17, OWB-S118).

The script invokes `python -m venv`, `pip install`, and a subprocess
call to enumerate installed distributions via `importlib.metadata`.
These tests stub subprocess.run so the script logic can be exercised
without actually building a venv or installing wheels. A full
end-to-end exercise happens via local dry-run against a real wheel and
via RC rehearsal against a scratch branch per the Sprint 23 execution
plan.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from tests.conftest import load_script

generate_sbom_mod = load_script("generate_sbom")


# Representative dist set: OWB itself plus a few representative Python
# dependencies. OWB must be filtered out of `components` by build_bom.
FAKE_DISTS = [
    {"name": "open-workspace-builder", "version": "1.9.0"},
    {"name": "click", "version": "8.1.0"},
    {"name": "PyYAML", "version": "6.0"},
    {"name": "cyclonedx-python-lib", "version": "11.0.0"},
]


@pytest.fixture
def fake_wheel(tmp_path: Path) -> Path:
    wheel = tmp_path / "open_workspace_builder-1.9.0-py3-none-any.whl"
    wheel.write_bytes(b"not a real wheel")
    return wheel


@pytest.fixture
def stub_subprocess(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    """Stub subprocess.run for venv creation, pip ops, and dist enumeration."""
    config: dict[str, Any] = {
        "venv_rc": 0,
        "pip_upgrade_rc": 0,
        "install_rc": 0,
        "enumerate_rc": 0,
        "enumerate_stdout": json.dumps(FAKE_DISTS),
        "calls": [],
    }

    def fake_run(argv, capture_output=False, text=False, check=False):  # noqa: ARG001
        config["calls"].append(list(argv))
        joined = " ".join(str(a) for a in argv)

        if "-m" in argv and "venv" in argv:
            venv_path = Path(argv[-1])
            bin_dir = venv_path / ("Scripts" if sys.platform == "win32" else "bin")
            bin_dir.mkdir(parents=True, exist_ok=True)
            for tool in ("pip", "python"):
                exe = bin_dir / (f"{tool}.exe" if sys.platform == "win32" else tool)
                exe.write_text("")
                exe.chmod(0o755)
            return SimpleNamespace(returncode=config["venv_rc"], stdout="", stderr="")

        argv0 = str(argv[0])

        if argv0.endswith("pip") or argv0.endswith("pip.exe"):
            if "--upgrade" in argv:
                return SimpleNamespace(returncode=config["pip_upgrade_rc"], stdout="", stderr="")
            return SimpleNamespace(returncode=config["install_rc"], stdout="", stderr="install err")

        if (argv0.endswith("python") or argv0.endswith("python.exe")) and "-c" in argv:
            return SimpleNamespace(
                returncode=config["enumerate_rc"],
                stdout=config["enumerate_stdout"],
                stderr="enumerate err",
            )

        if "venv" in joined:
            return SimpleNamespace(returncode=0, stdout="", stderr="")

        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(generate_sbom_mod.subprocess, "run", fake_run)
    return config


class TestCanonicalPypiName:
    @pytest.mark.parametrize(
        ("raw", "canonical"),
        [
            ("open-workspace-builder", "open-workspace-builder"),
            ("open_workspace_builder", "open-workspace-builder"),
            ("PyYAML", "pyyaml"),
            ("cyclonedx-python-lib", "cyclonedx-python-lib"),
            ("cyclonedx.python.lib", "cyclonedx-python-lib"),
            ("Some___Weird--Name", "some-weird-name"),
        ],
    )
    def test_pep503_normalization(self, raw: str, canonical: str) -> None:
        assert generate_sbom_mod._canonical_pypi_name(raw) == canonical


class TestBuildBom:
    def test_owb_goes_to_metadata_component(self) -> None:
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", FAKE_DISTS)
        assert bom.metadata is not None
        assert bom.metadata.component is not None
        assert bom.metadata.component.name == "open-workspace-builder"
        assert str(bom.metadata.component.version) == "1.9.0"

    def test_owb_excluded_from_components(self) -> None:
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", FAKE_DISTS)
        names = {c.name for c in bom.components}
        assert "open-workspace-builder" not in names
        assert names == {"click", "PyYAML", "cyclonedx-python-lib"}

    def test_owb_excluded_via_canonical_name_match(self) -> None:
        dists = [
            {"name": "Open_Workspace_Builder", "version": "1.9.0"},
            {"name": "click", "version": "8.1.0"},
        ]
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", dists)
        names = {c.name for c in bom.components}
        assert names == {"click"}

    def test_empty_name_skipped(self) -> None:
        dists = [
            {"name": "", "version": "0.0.0"},
            {"name": "click", "version": "8.1.0"},
        ]
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", dists)
        assert {c.name for c in bom.components} == {"click"}

    def test_venv_bootstrap_packages_excluded(self) -> None:
        dists = [
            {"name": "pip", "version": "24.0"},
            {"name": "setuptools", "version": "70.0"},
            {"name": "wheel", "version": "0.43"},
            {"name": "click", "version": "8.1.0"},
        ]
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", dists)
        assert {c.name for c in bom.components} == {"click"}

    def test_venv_bootstrap_filter_uses_canonical_name(self) -> None:
        # pkg_resources → pkg-resources after PEP 503
        dists = [
            {"name": "pkg_resources", "version": "0.0.0"},
            {"name": "PyYAML", "version": "6.0"},
        ]
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", dists)
        assert {c.name for c in bom.components} == {"PyYAML"}

    def test_component_has_pypi_purl(self) -> None:
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", FAKE_DISTS)
        for c in bom.components:
            assert c.purl is not None
            assert c.purl.type == "pypi"
            assert c.purl.version == c.version

    def test_metadata_component_is_application(self) -> None:
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", FAKE_DISTS)
        assert bom.metadata.component.type == generate_sbom_mod.ComponentType.APPLICATION

    def test_library_components_are_library_type(self) -> None:
        bom = generate_sbom_mod.build_bom("open-workspace-builder", "1.9.0", FAKE_DISTS)
        for c in bom.components:
            assert c.type == generate_sbom_mod.ComponentType.LIBRARY


class TestGenerateSbom:
    def test_happy_path_writes_valid_cyclonedx(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        output = tmp_path / "dist" / "sbom.cdx.json"
        generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)
        assert output.is_file()
        parsed = json.loads(output.read_text())
        assert parsed["bomFormat"] == "CycloneDX"
        assert parsed["metadata"]["component"]["name"] == "open-workspace-builder"
        assert parsed["metadata"]["component"]["version"] == "1.9.0"
        component_names = {c["name"] for c in parsed.get("components", [])}
        assert "open-workspace-builder" not in component_names
        assert "click" in component_names

    def test_missing_wheel_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="wheel not found"):
            generate_sbom_mod.generate_sbom(tmp_path / "nope.whl", "1.9.0", tmp_path / "sbom.json")

    def test_venv_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["venv_rc"] = 1
        with pytest.raises(RuntimeError, match="venv creation failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", tmp_path / "sbom.json")

    def test_pip_upgrade_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["pip_upgrade_rc"] = 1
        with pytest.raises(RuntimeError, match="pip upgrade failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", tmp_path / "sbom.json")

    def test_install_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["install_rc"] = 1
        with pytest.raises(RuntimeError, match="wheel install failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", tmp_path / "sbom.json")

    def test_enumerate_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["enumerate_rc"] = 1
        with pytest.raises(RuntimeError, match="dist enumeration failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", tmp_path / "sbom.json")

    def test_enumerate_invalid_json_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["enumerate_stdout"] = "{not json"
        with pytest.raises(RuntimeError, match="not valid JSON"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", tmp_path / "sbom.json")

    def test_enumerate_non_list_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["enumerate_stdout"] = json.dumps({"not": "a list"})
        with pytest.raises(RuntimeError, match="not a list"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", tmp_path / "sbom.json")

    def test_creates_output_parent_directory(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        output = tmp_path / "nested" / "dir" / "sbom.json"
        generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)
        assert output.is_file()


class TestMainCli:
    def test_main_happy_path(
        self,
        fake_wheel: Path,
        tmp_path: Path,
        stub_subprocess: dict[str, Any],
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        output = tmp_path / "sbom.json"
        rc = generate_sbom_mod.main(
            [
                "generate_sbom.py",
                "--wheel",
                str(fake_wheel),
                "--version",
                "1.9.0",
                "--output",
                str(output),
            ]
        )
        assert rc == 0
        captured = capsys.readouterr()
        assert "SBOM written" in captured.out

    def test_main_missing_wheel_returns_1(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        rc = generate_sbom_mod.main(
            [
                "generate_sbom.py",
                "--wheel",
                str(tmp_path / "nope.whl"),
                "--version",
                "1.9.0",
                "--output",
                str(tmp_path / "sbom.json"),
            ]
        )
        assert rc == 1
        captured = capsys.readouterr()
        assert "wheel not found" in captured.err
