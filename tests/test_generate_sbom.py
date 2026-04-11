"""Tests for scripts/generate_sbom.py (AD-17, OWB-S118).

These tests stub the subprocess calls so they exercise the script logic
without actually building a venv or running pip-audit. Full end-to-end
exercise happens via the RC rehearsal against a scratch branch per the
Sprint 23 execution plan.
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


VALID_CYCLONEDX = {
    "bomFormat": "CycloneDX",
    "specVersion": "1.6",
    "version": 1,
    "components": [
        {"type": "library", "name": "click", "version": "8.1.0"},
    ],
}


@pytest.fixture
def fake_wheel(tmp_path: Path) -> Path:
    wheel = tmp_path / "open_workspace_builder-1.9.0-py3-none-any.whl"
    wheel.write_bytes(b"not a real wheel")
    return wheel


@pytest.fixture
def stub_subprocess(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> dict[str, Any]:
    """Replace subprocess.run with a stub that writes a fake SBOM on pip-audit."""
    calls: list[list[str]] = []
    config: dict[str, Any] = {
        "pip_audit_rc": 0,
        "pip_audit_writes_file": True,
        "pip_audit_content": json.dumps(VALID_CYCLONEDX),
        "install_rc": 0,
        "venv_rc": 0,
        "pip_upgrade_rc": 0,
    }

    def fake_run(argv, capture_output=False, text=False, check=False):  # noqa: ARG001
        calls.append(list(argv))
        argv_str = " ".join(str(a) for a in argv)

        if "venv" in argv_str and "-m venv" in " ".join(argv):
            venv_path = Path(argv[-1])
            bin_dir = venv_path / ("Scripts" if sys.platform == "win32" else "bin")
            bin_dir.mkdir(parents=True, exist_ok=True)
            for tool in ("pip", "pip-audit"):
                exe = bin_dir / (f"{tool}.exe" if sys.platform == "win32" else tool)
                exe.write_text("#!/bin/sh\nexit 0\n")
                exe.chmod(0o755)
            return SimpleNamespace(returncode=config["venv_rc"], stdout="", stderr="")

        if "pip-audit" in str(argv[0]):
            if config["pip_audit_writes_file"]:
                output_idx = argv.index("--output") + 1
                output = Path(argv[output_idx])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text(config["pip_audit_content"])
            return SimpleNamespace(
                returncode=config["pip_audit_rc"], stdout="", stderr="vulns maybe"
            )

        if "pip" in str(argv[0]):
            if "--upgrade" in argv:
                return SimpleNamespace(returncode=config["pip_upgrade_rc"], stdout="", stderr="")
            return SimpleNamespace(returncode=config["install_rc"], stdout="", stderr="install err")

        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(generate_sbom_mod.subprocess, "run", fake_run)
    config["calls"] = calls
    return config


class TestGenerateSbom:
    def test_happy_path(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        output = tmp_path / "dist" / "sbom.cdx.json"
        generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)
        assert output.is_file()
        parsed = json.loads(output.read_text())
        assert parsed["bomFormat"] == "CycloneDX"

    def test_missing_wheel_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError, match="wheel not found"):
            generate_sbom_mod.generate_sbom(tmp_path / "nope.whl", "1.9.0", tmp_path / "sbom.json")

    def test_pip_audit_vulns_found_is_success(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["pip_audit_rc"] = 1  # vulns found
        output = tmp_path / "sbom.json"
        generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)
        assert output.is_file()

    def test_pip_audit_hard_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["pip_audit_rc"] = 2  # hard failure
        output = tmp_path / "sbom.json"
        with pytest.raises(RuntimeError, match="pip-audit failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)

    def test_pip_audit_missing_output_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["pip_audit_writes_file"] = False
        output = tmp_path / "sbom.json"
        with pytest.raises(RuntimeError, match="did not produce output"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)

    def test_pip_audit_invalid_json_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["pip_audit_content"] = "{not json"
        output = tmp_path / "sbom.json"
        with pytest.raises(RuntimeError, match="not valid JSON"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)

    def test_pip_audit_wrong_format_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["pip_audit_content"] = json.dumps({"bomFormat": "SPDX"})
        output = tmp_path / "sbom.json"
        with pytest.raises(RuntimeError, match="not a CycloneDX document"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)

    def test_venv_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["venv_rc"] = 1
        output = tmp_path / "sbom.json"
        with pytest.raises(RuntimeError, match="venv creation failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)

    def test_install_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["install_rc"] = 1
        output = tmp_path / "sbom.json"
        with pytest.raises(RuntimeError, match="install failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)

    def test_pip_upgrade_failure_raises(
        self, fake_wheel: Path, tmp_path: Path, stub_subprocess: dict[str, Any]
    ) -> None:
        stub_subprocess["pip_upgrade_rc"] = 1
        output = tmp_path / "sbom.json"
        with pytest.raises(RuntimeError, match="pip upgrade failed"):
            generate_sbom_mod.generate_sbom(fake_wheel, "1.9.0", output)

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
        self,
        tmp_path: Path,
        capsys: pytest.CaptureFixture[str],
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
