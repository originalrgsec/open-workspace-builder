"""OWB-S107b — Tests for SBOM provenance detection.

Provenance answers the question "where did this component come from?" via
four sources, in priority order:

1. Explicit ``source:`` frontmatter field on the component itself.
2. Git history: the commit that added the file, with remote URL if known.
3. Install record: a future ``owb skill install`` may write these.
4. Local fallback.

Each detected provenance entry carries a confidence score (high/medium/low)
so downstream consumers can decide how much to trust it.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from open_workspace_builder.sbom.provenance import (
    ProvenanceConfidence,
    ProvenanceType,
    detect_provenance,
    read_install_record,
)


# ---------------------------------------------------------------------------
# Frontmatter source: highest priority
# ---------------------------------------------------------------------------


class TestFrontmatterProvenance:
    def test_explicit_source_field(self, tmp_path: Path) -> None:
        skill = tmp_path / "SKILL.md"
        skill.write_text("---\nsource: https://github.com/foo/bar\n---\nbody\n")

        prov = detect_provenance(
            component_path=skill,
            workspace=tmp_path,
            frontmatter={"source": "https://github.com/foo/bar"},
        )
        assert prov.type == ProvenanceType.FRONTMATTER
        assert prov.source == "https://github.com/foo/bar"
        assert prov.confidence == ProvenanceConfidence.HIGH

    def test_explicit_source_with_local_value(self, tmp_path: Path) -> None:
        # `source: local` is still an explicit declaration, just one that
        # carries no upstream URL.
        skill = tmp_path / "SKILL.md"
        skill.write_text("---\nsource: local\n---\nbody\n")

        prov = detect_provenance(
            component_path=skill,
            workspace=tmp_path,
            frontmatter={"source": "local"},
        )
        assert prov.type == ProvenanceType.FRONTMATTER
        assert prov.source == "local"
        assert prov.confidence == ProvenanceConfidence.HIGH


# ---------------------------------------------------------------------------
# Git history detection
# ---------------------------------------------------------------------------


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout.strip()


@pytest.fixture
def git_repo_with_skill(tmp_path: Path) -> tuple[Path, Path]:
    """Create a tiny git repo with one committed skill file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    _git(repo, "config", "user.email", "test@example.com")
    _git(repo, "config", "user.name", "Test")
    # Disable commit signing locally so the fixture works on machines that
    # have global signing enabled.
    _git(repo, "config", "commit.gpgsign", "false")
    _git(repo, "config", "tag.gpgsign", "false")

    skill_dir = repo / ".claude" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    skill = skill_dir / "SKILL.md"
    skill.write_text("---\nname: demo\n---\nbody\n")
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", "add demo skill")
    return repo, skill


class TestGitHistoryProvenance:
    def test_finds_commit_in_local_repo(self, git_repo_with_skill: tuple[Path, Path]) -> None:
        repo, skill = git_repo_with_skill
        prov = detect_provenance(
            component_path=skill,
            workspace=repo,
            frontmatter={},
        )
        assert prov.type == ProvenanceType.GIT_HISTORY
        # Commit SHA should be present (40-char hex)
        assert prov.commit is not None
        assert len(prov.commit) == 40

    def test_no_remote_yields_medium_confidence(
        self, git_repo_with_skill: tuple[Path, Path]
    ) -> None:
        # Local repo with no `origin` remote: we know git tracked the file but
        # have no upstream URL. Confidence is medium.
        repo, skill = git_repo_with_skill
        prov = detect_provenance(
            component_path=skill,
            workspace=repo,
            frontmatter={},
        )
        assert prov.type == ProvenanceType.GIT_HISTORY
        assert prov.confidence == ProvenanceConfidence.MEDIUM
        assert prov.source is None or prov.source == "local-git"

    def test_with_origin_remote_yields_high_confidence(
        self, git_repo_with_skill: tuple[Path, Path]
    ) -> None:
        repo, skill = git_repo_with_skill
        _git(repo, "remote", "add", "origin", "https://github.com/example/test.git")
        prov = detect_provenance(
            component_path=skill,
            workspace=repo,
            frontmatter={},
        )
        assert prov.type == ProvenanceType.GIT_HISTORY
        assert prov.confidence == ProvenanceConfidence.HIGH
        assert prov.source == "https://github.com/example/test.git"

    def test_remote_url_normalized(self, git_repo_with_skill: tuple[Path, Path]) -> None:
        repo, skill = git_repo_with_skill
        _git(repo, "remote", "add", "origin", "git@github.com:example/test.git")
        prov = detect_provenance(
            component_path=skill,
            workspace=repo,
            frontmatter={},
        )
        # SSH URL should be normalized to https form for stable identification.
        assert prov.source == "https://github.com/example/test.git"


# ---------------------------------------------------------------------------
# Local fallback when no git, no install record, no frontmatter
# ---------------------------------------------------------------------------


class TestLocalFallback:
    def test_non_git_directory_returns_local(self, tmp_path: Path) -> None:
        skill = tmp_path / "SKILL.md"
        skill.write_text("---\nname: demo\n---\nbody\n")
        prov = detect_provenance(
            component_path=skill,
            workspace=tmp_path,
            frontmatter={},
        )
        assert prov.type == ProvenanceType.LOCAL
        assert prov.confidence == ProvenanceConfidence.LOW

    def test_missing_file_returns_local(self, tmp_path: Path) -> None:
        prov = detect_provenance(
            component_path=tmp_path / "nope.md",
            workspace=tmp_path,
            frontmatter={},
        )
        assert prov.type == ProvenanceType.LOCAL


# ---------------------------------------------------------------------------
# Install record reader (stub for S107b — no install command yet exists)
# ---------------------------------------------------------------------------


class TestInstallRecord:
    def test_no_install_record_returns_none(self, tmp_path: Path) -> None:
        # No install record file exists yet — function must handle gracefully.
        result = read_install_record(workspace=tmp_path, component_relpath="x/y.md")
        assert result is None

    def test_install_record_parsed_when_present(self, tmp_path: Path) -> None:
        # When a future install command writes records to a known location,
        # the reader picks them up. Test the wire format now so the install
        # command can rely on it.
        records_dir = tmp_path / ".owb" / "install-records"
        records_dir.mkdir(parents=True)
        record_file = records_dir / "skills.json"
        record_file.write_text(
            '{"records": ['
            '{"path": ".claude/skills/demo/SKILL.md",'
            ' "package": "demo-skill", "version": "1.0.0",'
            ' "installed_at": "2026-04-11T00:00:00Z",'
            ' "source": "https://example.com/registry/demo"}'
            "]}"
        )

        result = read_install_record(
            workspace=tmp_path,
            component_relpath=".claude/skills/demo/SKILL.md",
        )
        assert result is not None
        assert result.package == "demo-skill"
        assert result.version == "1.0.0"
        assert result.source == "https://example.com/registry/demo"

    def test_install_record_used_in_detection(self, tmp_path: Path) -> None:
        records_dir = tmp_path / ".owb" / "install-records"
        records_dir.mkdir(parents=True)
        (records_dir / "skills.json").write_text(
            '{"records": ['
            '{"path": ".claude/skills/demo/SKILL.md",'
            ' "package": "demo-skill", "version": "1.0.0",'
            ' "installed_at": "2026-04-11T00:00:00Z",'
            ' "source": "https://example.com/registry/demo"}'
            "]}"
        )

        skill = tmp_path / ".claude" / "skills" / "demo" / "SKILL.md"
        skill.parent.mkdir(parents=True)
        skill.write_text("---\nname: demo\n---\nbody\n")

        prov = detect_provenance(
            component_path=skill,
            workspace=tmp_path,
            frontmatter={},
        )
        assert prov.type == ProvenanceType.INSTALL_RECORD
        assert prov.source == "https://example.com/registry/demo"
        assert prov.confidence == ProvenanceConfidence.HIGH


# ---------------------------------------------------------------------------
# Priority ordering — higher-priority sources beat lower-priority ones
# ---------------------------------------------------------------------------


class TestPriorityOrdering:
    def test_frontmatter_beats_git(self, git_repo_with_skill: tuple[Path, Path]) -> None:
        repo, skill = git_repo_with_skill
        _git(repo, "remote", "add", "origin", "https://github.com/example/test.git")
        prov = detect_provenance(
            component_path=skill,
            workspace=repo,
            frontmatter={"source": "https://explicit.example.com/foo"},
        )
        assert prov.type == ProvenanceType.FRONTMATTER
        assert prov.source == "https://explicit.example.com/foo"

    def test_install_record_beats_git(self, git_repo_with_skill: tuple[Path, Path]) -> None:
        repo, skill = git_repo_with_skill
        _git(repo, "remote", "add", "origin", "https://github.com/example/test.git")

        records_dir = repo / ".owb" / "install-records"
        records_dir.mkdir(parents=True)
        (records_dir / "skills.json").write_text(
            '{"records": ['
            '{"path": ".claude/skills/demo/SKILL.md",'
            ' "package": "p", "version": "1.0.0",'
            ' "installed_at": "2026-04-11T00:00:00Z",'
            ' "source": "https://registry.example.com/p"}'
            "]}"
        )

        prov = detect_provenance(
            component_path=skill,
            workspace=repo,
            frontmatter={},
        )
        assert prov.type == ProvenanceType.INSTALL_RECORD
