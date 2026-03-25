"""Tests for combined security scanning: SCA + SAST integration (OWB-S057)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.security.dep_discovery import (
    _parse_imports,
    _parse_pyproject,
    _parse_requirements,
    discover_dependencies,
)


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── Dependency Discovery ──────────────────────────────────────────────────


class TestDependencyDiscoveryRequirements:
    def test_parse_requirements(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text(
            "click>=8.0\npyyaml\n# comment\nrequests==2.31.0\n-e .\n",
            encoding="utf-8",
        )
        result = _parse_requirements(req)
        assert "click" in result
        assert "pyyaml" in result
        assert "requests" in result

    def test_parse_requirements_empty(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("# just comments\n", encoding="utf-8")
        assert _parse_requirements(req) == set()


class TestDependencyDiscoveryPyproject:
    def test_parse_pyproject(self, tmp_path: Path) -> None:
        pp = tmp_path / "pyproject.toml"
        pp.write_text(
            '[project]\nname = "test"\ndependencies = [\n'
            '    "click>=8.0",\n    "pyyaml>=6.0",\n]\n',
            encoding="utf-8",
        )
        result = _parse_pyproject(pp)
        assert "click" in result
        assert "pyyaml" in result

    def test_parse_pyproject_no_deps(self, tmp_path: Path) -> None:
        pp = tmp_path / "pyproject.toml"
        pp.write_text('[project]\nname = "test"\n', encoding="utf-8")
        assert _parse_pyproject(pp) == set()


class TestDependencyDiscoveryImports:
    def test_parse_imports(self, tmp_path: Path) -> None:
        py = tmp_path / "app.py"
        py.write_text(
            "import os\nimport click\nfrom pathlib import Path\nfrom pyyaml import safe_load\n",
            encoding="utf-8",
        )
        result = _parse_imports(py)
        # os and pathlib are stdlib, should be excluded
        assert "os" not in result
        assert "pathlib" not in result
        # click and pyyaml are third-party
        assert "click" in result
        assert "pyyaml" in result

    def test_parse_imports_future_excluded(self, tmp_path: Path) -> None:
        py = tmp_path / "mod.py"
        py.write_text("from __future__ import annotations\nimport click\n", encoding="utf-8")
        result = _parse_imports(py)
        assert "__future__" not in result
        assert "click" in result


class TestDiscoverDependencies:
    def test_directory_scan(self, tmp_path: Path) -> None:
        (tmp_path / "requirements.txt").write_text("flask>=2.0\n", encoding="utf-8")
        (tmp_path / "app.py").write_text("import requests\n", encoding="utf-8")
        result = discover_dependencies(tmp_path)
        assert "flask" in result
        assert "requests" in result

    def test_single_file(self, tmp_path: Path) -> None:
        req = tmp_path / "requirements.txt"
        req.write_text("click\nrequests\n", encoding="utf-8")
        result = discover_dependencies(req)
        assert result == ["click", "requests"]


# ── CLI --sca flag ────────────────────────────────────────────────────────


class TestScanWithScaFlag:
    @patch("open_workspace_builder.cli._run_sca_scan")
    def test_sca_findings_in_report(
        self, mock_sca: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "src"
        target.mkdir()
        (target / "app.py").write_text("print('hello')\n", encoding="utf-8")

        mock_sca.return_value = {
            "vulnerabilities": [
                {
                    "package": "badpkg",
                    "installed_version": "1.0",
                    "vuln_id": "CVE-2026-9999",
                    "fix_version": "1.1",
                    "description": "Bad vuln",
                }
            ],
            "guarddog_flagged": [],
            "packages_scanned": ["badpkg"],
        }

        result = runner.invoke(owb, ["security", "scan", str(target), "--sca"])
        assert result.exit_code == 2  # has findings
        mock_sca.assert_called_once()

    @patch("open_workspace_builder.cli._run_sca_scan")
    def test_sca_clean(
        self, mock_sca: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "src"
        target.mkdir()
        (target / "app.py").write_text("print('hello')\n", encoding="utf-8")

        mock_sca.return_value = {
            "vulnerabilities": [],
            "guarddog_flagged": [],
            "packages_scanned": ["click"],
        }

        result = runner.invoke(owb, ["security", "scan", str(target), "--sca"])
        assert result.exit_code == 0


# ── CLI --sast flag ───────────────────────────────────────────────────────


class TestScanWithSastFlag:
    @patch("open_workspace_builder.cli._run_sast_scan")
    def test_sast_error_findings(
        self, mock_sast: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "src"
        target.mkdir()
        (target / "app.py").write_text("print('hello')\n", encoding="utf-8")

        mock_sast.return_value = {
            "findings": [
                {
                    "rule_id": "python.lang.security.eval",
                    "severity": "ERROR",
                    "message": "eval is dangerous",
                    "file": "app.py",
                    "line": 1,
                    "code": "eval(x)",
                }
            ],
            "errors": [],
            "rules_run": 10,
        }

        result = runner.invoke(owb, ["security", "scan", str(target), "--sast"])
        assert result.exit_code == 2

    @patch("open_workspace_builder.cli._run_sast_scan")
    def test_sast_clean(
        self, mock_sast: MagicMock, runner: CliRunner, tmp_path: Path
    ) -> None:
        target = tmp_path / "src"
        target.mkdir()
        (target / "app.py").write_text("print('hello')\n", encoding="utf-8")

        mock_sast.return_value = {"findings": [], "errors": [], "rules_run": 10}

        result = runner.invoke(owb, ["security", "scan", str(target), "--sast"])
        assert result.exit_code == 0


# ── CLI both flags ────────────────────────────────────────────────────────


class TestScanBothFlags:
    @patch("open_workspace_builder.cli._run_sast_scan")
    @patch("open_workspace_builder.cli._run_sca_scan")
    def test_both_sections_present(
        self,
        mock_sca: MagicMock,
        mock_sast: MagicMock,
        runner: CliRunner,
        tmp_path: Path,
    ) -> None:
        target = tmp_path / "src"
        target.mkdir()
        (target / "app.py").write_text("print('hello')\n", encoding="utf-8")

        mock_sca.return_value = {
            "vulnerabilities": [],
            "guarddog_flagged": [],
            "packages_scanned": [],
        }
        mock_sast.return_value = {"findings": [], "errors": [], "rules_run": 5}

        out = tmp_path / "report.json"
        result = runner.invoke(
            owb,
            ["security", "scan", str(target), "--sca", "--sast", "-o", str(out)],
        )
        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "sca" in data
        assert "sast" in data


# ── No extra flags (backward compat) ─────────────────────────────────────


class TestScanNoExtraFlags:
    def test_no_sca_sast_sections(self, runner: CliRunner, tmp_path: Path) -> None:
        target = tmp_path / "src"
        target.mkdir()
        (target / "clean.txt").write_text("hello\n", encoding="utf-8")

        out = tmp_path / "report.json"
        result = runner.invoke(owb, ["security", "scan", str(target), "-o", str(out)])
        assert result.exit_code == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert "sca" not in data
        assert "sast" not in data


# ── Trust Tier Integration ────────────────────────────────────────────────


class TestTrustTierScaIntegration:
    """Test that SCA/SAST findings affect trust tier assignment."""

    @pytest.fixture()
    def _registry_dir(self, tmp_path: Path) -> Path:
        policy_dir = tmp_path / "policies"
        policy_dir.mkdir()
        (policy_dir / "owb-default.yaml").write_text(
            'id: "owb-default"\nversion: "1.0.0"\ntype: "trust_policy"\n'
            'author: "Test"\ndescription: "Test"\ncompatibility: ">=0.1.0"\n\n'
            "payload:\n  tiers:\n"
            "    - level: 0\n      name: T0\n      description: Owner\n"
            "      criteria:\n        source_prefixes:\n"
            '          - "content/custom/"\n'
            "      actions:\n        auto_install: true\n"
            "    - level: 1\n      name: T1\n      description: Verified\n"
            "      criteria:\n        source_prefixes: []\n"
            "      actions:\n        auto_install: false\n"
            "    - level: 2\n      name: T2\n      description: Unverified\n"
            "      criteria:\n        source_prefixes: []\n"
            "      actions:\n        auto_install: false\n",
            encoding="utf-8",
        )
        return policy_dir

    def test_sca_critical_blocks_t0(self, _registry_dir: Path) -> None:
        from open_workspace_builder.evaluator.trust import TrustTierAssigner
        from open_workspace_builder.registry.registry import Registry

        reg = Registry(base_dirs=[_registry_dir])
        assigner = TrustTierAssigner(reg)
        result = assigner.assign(
            "content/custom/skill.md",
            source=None,
            security_passed=True,
            evaluation_passed=True,
            owner_approved=True,
            sca_critical=True,
        )
        assert result.tier == 2
        assert "critical SCA" in result.reasoning

    def test_sast_error_blocks_t0(self, _registry_dir: Path) -> None:
        from open_workspace_builder.evaluator.trust import TrustTierAssigner
        from open_workspace_builder.registry.registry import Registry

        reg = Registry(base_dirs=[_registry_dir])
        assigner = TrustTierAssigner(reg)
        result = assigner.assign(
            "content/custom/skill.md",
            source=None,
            security_passed=True,
            evaluation_passed=True,
            owner_approved=True,
            sast_error=True,
        )
        assert result.tier == 2
        assert "SAST" in result.reasoning

    def test_clean_sca_sast_allows_t0(self, _registry_dir: Path) -> None:
        from open_workspace_builder.evaluator.trust import TrustTierAssigner
        from open_workspace_builder.registry.registry import Registry

        reg = Registry(base_dirs=[_registry_dir])
        assigner = TrustTierAssigner(reg)
        result = assigner.assign(
            "content/custom/skill.md",
            source=None,
            security_passed=True,
            evaluation_passed=True,
            owner_approved=True,
            sca_critical=False,
            sast_error=False,
        )
        assert result.tier == 0
