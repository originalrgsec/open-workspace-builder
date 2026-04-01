"""Tests for vault-audit script bug fixes."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

AUDIT_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "src"
    / "open_workspace_builder"
    / "content"
    / "skills"
    / "vault-audit"
    / "scripts"
    / "audit.sh"
)


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    """Create a minimal valid vault structure for audit testing."""
    vault_root = tmp_path / "vault"
    vault_root.mkdir()

    # Required structural files
    (vault_root / "_bootstrap.md").write_text("# Bootstrap\n| **Foo** | phase | action |\n")
    (vault_root / "_index.md").write_text("# Vault Index\n")
    (vault_root / "projects").mkdir()
    (vault_root / "projects" / "_index.md").write_text("# Projects\nFoo\n")
    (vault_root / "decisions").mkdir()
    (vault_root / "decisions" / "_index.md").write_text("# Decisions\n")
    (vault_root / "research").mkdir()
    (vault_root / "research" / "_index.md").write_text("# Research\n")
    (vault_root / "code").mkdir()
    (vault_root / "code" / "_index.md").write_text("# Code\n")
    (vault_root / "business").mkdir()
    (vault_root / "business" / "_index.md").write_text("# Business\n")
    (vault_root / "self").mkdir()
    (vault_root / "self" / "_index.md").write_text("# Self\n")

    return vault_root


def _run_audit(vault_path: Path) -> subprocess.CompletedProcess[str]:
    """Run audit.sh against the given vault path."""
    return subprocess.run(
        ["bash", str(AUDIT_SCRIPT), str(vault_path)],
        capture_output=True,
        text=True,
        timeout=30,
    )


class TestBug1DynamicTierDetection:
    """Bug 1: Hardcoded tier names replaced with dynamic glob."""

    def test_custom_tier_detected(self, vault: Path) -> None:
        """A non-default tier name should be picked up by the audit."""
        # Create a custom tier with proper structure
        custom_tier = vault / "projects" / "CustomTier"
        custom_tier.mkdir()
        (custom_tier / "_index.md").write_text("# CustomTier\n")
        (custom_tier / "status.md").write_text("---\nlast-updated: 2026-01-01\n---\n")

        result = _run_audit(vault)
        # Should not report missing tier index for CustomTier
        assert "Missing tier index: projects/CustomTier/_index.md" not in result.stdout

    def test_missing_index_for_custom_tier_flagged(self, vault: Path) -> None:
        """A custom tier without _index.md should be flagged."""
        custom_tier = vault / "projects" / "MyTier"
        custom_tier.mkdir()

        result = _run_audit(vault)
        assert "Missing tier index: projects/MyTier/_index.md" in result.stdout

    def test_no_hardcoded_tiers(self) -> None:
        """Verify the hardcoded tier loop is gone from the script."""
        script_content = AUDIT_SCRIPT.read_text(encoding="utf-8")
        assert "for tier in Personal Volcanix Claude" not in script_content
        assert 'for tier_dir in "$VAULT_PATH"/projects/*/' in script_content


class TestBug2NestedPathFallback:
    """Bug 2: Fallback to Claude Context/Obsidian/ for bootstrap and index."""

    def test_nested_bootstrap_detected(self, vault: Path) -> None:
        """When _bootstrap.md is at Claude Context/Obsidian/, it should be found."""
        # Remove root-level bootstrap
        (vault / "_bootstrap.md").unlink()

        # Place it nested
        nested = vault / "Claude Context" / "Obsidian"
        nested.mkdir(parents=True)
        (nested / "_bootstrap.md").write_text("# Bootstrap\n")

        result = _run_audit(vault)
        assert "_bootstrap.md is missing" not in result.stdout

    def test_nested_projects_index_detected(self, vault: Path) -> None:
        """When projects/_index.md is nested, bootstrap check still works."""
        # Remove root-level bootstrap to test the elif branch
        # Keep bootstrap at root, move projects index nested
        (vault / "projects" / "_index.md").unlink()

        nested = vault / "Claude Context" / "Obsidian" / "projects"
        nested.mkdir(parents=True)
        (nested / "_index.md").write_text("# Projects\n")

        result = _run_audit(vault)
        # The check-3 bootstrap consistency should not report missing projects/_index.md
        assert "projects/_index.md is missing" not in result.stdout

    def test_required_files_nested_fallback(self, vault: Path) -> None:
        """Check 6 should find required files at nested location."""
        # Move _bootstrap.md to nested location
        (vault / "_bootstrap.md").unlink()
        nested = vault / "Claude Context" / "Obsidian"
        nested.mkdir(parents=True)
        (nested / "_bootstrap.md").write_text("# Bootstrap\n")

        result = _run_audit(vault)
        assert "Missing required file: _bootstrap.md" not in result.stdout


class TestBug3IndexNamingDrift:
    """Bug 3: index.md (without underscore) detected as naming convention issue."""

    def test_index_without_underscore_flagged(self, vault: Path) -> None:
        """index.md in a project dir should be warned about."""
        project_dir = vault / "projects" / "SomeTier" / "my-project"
        project_dir.mkdir(parents=True)
        (project_dir / "index.md").write_text("# My Project\n")
        # Also add tier _index.md so tier check doesn't mask it
        (vault / "projects" / "SomeTier" / "_index.md").write_text("# SomeTier\nmy-project\n")
        (project_dir / "status.md").write_text("---\nlast-updated: 2026-01-01\n---\n")

        result = _run_audit(vault)
        assert "Naming convention" in result.stdout
        assert "index.md" in result.stdout
        assert "_index.md" in result.stdout

    def test_underscore_index_not_flagged(self, vault: Path) -> None:
        """_index.md should not trigger the naming drift warning."""
        project_dir = vault / "projects" / "TestTier" / "good-project"
        project_dir.mkdir(parents=True)
        (project_dir / "_index.md").write_text("# Good Project\n")
        (vault / "projects" / "TestTier" / "_index.md").write_text("# TestTier\ngood-project\n")
        (project_dir / "status.md").write_text("---\nlast-updated: 2026-01-01\n---\n")

        result = _run_audit(vault)
        assert "Naming convention" not in result.stdout
