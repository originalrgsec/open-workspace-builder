"""OWB-S107c — Tests for `owb sbom verify`."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.sbom.builder import build_bom, serialize_bom
from open_workspace_builder.sbom.discover import discover_components
from open_workspace_builder.sbom.verify import (
    default_canonical_path,
    verify_workspace,
)


def _make_workspace_with_skill(tmp_path: Path, body: str = "hello body\n") -> Path:
    workspace = tmp_path / "ws"
    skill_dir = workspace / ".claude" / "skills" / "demo"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text(f"---\nname: demo\nversion: 1.0.0\n---\n{body}")
    return workspace


def _write_canonical(workspace: Path) -> Path:
    components = discover_components(workspace)
    bom = build_bom(components)
    canonical = default_canonical_path(workspace)
    canonical.parent.mkdir(parents=True, exist_ok=True)
    canonical.write_text(serialize_bom(bom) + "\n", encoding="utf-8")
    return canonical


class TestVerifyWorkspace:
    def test_match_returns_ok(self, tmp_path: Path) -> None:
        workspace = _make_workspace_with_skill(tmp_path)
        _write_canonical(workspace)

        outcome = verify_workspace(workspace=workspace)
        assert outcome.ok is True
        assert not outcome.diff.has_differences

    def test_drift_returns_not_ok(self, tmp_path: Path) -> None:
        workspace = _make_workspace_with_skill(tmp_path)
        _write_canonical(workspace)

        # Mutate the skill body so the content hash changes.
        skill_path = workspace / ".claude" / "skills" / "demo" / "SKILL.md"
        skill_path.write_text("---\nname: demo\nversion: 1.0.0\n---\nMUTATED\n")

        outcome = verify_workspace(workspace=workspace)
        assert outcome.ok is False
        assert outcome.diff.has_differences

    def test_explicit_canonical_path(self, tmp_path: Path) -> None:
        workspace = _make_workspace_with_skill(tmp_path)
        # Write canonical to a custom location.
        components = discover_components(workspace)
        bom = build_bom(components)
        custom_path = tmp_path / "custom-sbom.json"
        custom_path.write_text(serialize_bom(bom) + "\n", encoding="utf-8")

        outcome = verify_workspace(workspace=workspace, canonical=custom_path)
        assert outcome.ok is True

    def test_missing_workspace_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            verify_workspace(workspace=tmp_path / "nope")

    def test_missing_canonical_raises(self, tmp_path: Path) -> None:
        workspace = _make_workspace_with_skill(tmp_path)
        with pytest.raises(FileNotFoundError):
            verify_workspace(workspace=workspace)

    def test_malformed_canonical_raises(self, tmp_path: Path) -> None:
        workspace = _make_workspace_with_skill(tmp_path)
        canonical = default_canonical_path(workspace)
        canonical.parent.mkdir(parents=True, exist_ok=True)
        canonical.write_text("garbage", encoding="utf-8")
        with pytest.raises(ValueError):
            verify_workspace(workspace=workspace)

    def test_added_at_drift_does_not_count(self, tmp_path: Path) -> None:
        """Regression: cosmetic mtime drift on added_at must not fail verify."""
        workspace = _make_workspace_with_skill(tmp_path)
        _write_canonical(workspace)
        # Touch mtime to a different date — added_at would change but it is
        # not in the comparable surface.
        skill = workspace / ".claude" / "skills" / "demo" / "SKILL.md"
        # Re-write same content; mtime updates.
        skill.write_text(skill.read_text())

        outcome = verify_workspace(workspace=workspace)
        assert outcome.ok is True
