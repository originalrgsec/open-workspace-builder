"""Tests for init safety: scaffold skip (S060) and vault nesting prevention (S063)."""

from __future__ import annotations

from pathlib import Path

import pytest

from open_workspace_builder.config import Config
from open_workspace_builder.engine.builder import WorkspaceBuilder
from open_workspace_builder.engine.vault import VaultBuilder


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _build_workspace(tmp_target: Path, content_root: Path, **kwargs: object) -> Path:
    config = Config()
    builder = WorkspaceBuilder(config, content_root, **kwargs)
    builder.build(tmp_target)
    return tmp_target


def _vault_root(target: Path) -> Path:
    return target / "Obsidian"


# ---------------------------------------------------------------------------
# S060: Init detect-and-skip existing scaffold files
# ---------------------------------------------------------------------------

class TestScaffoldSkipExistingFiles:
    """owb init must not overwrite existing vault scaffold files."""

    def test_existing_bootstrap_preserved(
        self, tmp_target: Path, content_root: Path
    ) -> None:
        """AC-1: Existing _bootstrap.md is skipped, not overwritten."""
        vault = _vault_root(tmp_target)
        vault.mkdir(parents=True)
        bootstrap = vault / "_bootstrap.md"
        custom_content = "# My Custom Bootstrap\n\nReal project data here.\n"
        bootstrap.write_text(custom_content, encoding="utf-8")

        _build_workspace(tmp_target, content_root)

        assert bootstrap.read_text(encoding="utf-8") == custom_content

    def test_existing_index_preserved(
        self, tmp_target: Path, content_root: Path
    ) -> None:
        """AC-2: Existing _index.md is skipped."""
        vault = _vault_root(tmp_target)
        vault.mkdir(parents=True)
        index = vault / "_index.md"
        custom_content = "# My Custom Index\n"
        index.write_text(custom_content, encoding="utf-8")

        _build_workspace(tmp_target, content_root)

        assert index.read_text(encoding="utf-8") == custom_content

    def test_existing_sub_index_preserved(
        self, tmp_target: Path, content_root: Path
    ) -> None:
        """AC-2: Existing sub-area index files are also skipped."""
        vault = _vault_root(tmp_target)
        (vault / "self").mkdir(parents=True)
        self_index = vault / "self" / "_index.md"
        custom_content = "# My Custom Self Index\n"
        self_index.write_text(custom_content, encoding="utf-8")

        _build_workspace(tmp_target, content_root)

        assert self_index.read_text(encoding="utf-8") == custom_content

    def test_existing_status_preserved(
        self, tmp_target: Path, content_root: Path
    ) -> None:
        """AC-2: Existing status.md per tier is skipped."""
        vault = _vault_root(tmp_target)
        (vault / "projects" / "Work").mkdir(parents=True)
        status = vault / "projects" / "Work" / "status.md"
        custom_content = "# Custom Status\n"
        status.write_text(custom_content, encoding="utf-8")

        _build_workspace(tmp_target, content_root)

        assert status.read_text(encoding="utf-8") == custom_content

    def test_existing_template_readme_preserved(
        self, tmp_target: Path, content_root: Path
    ) -> None:
        """AC-2: Existing _templates/readme.md is skipped."""
        vault = _vault_root(tmp_target)
        (vault / "_templates").mkdir(parents=True)
        readme = vault / "_templates" / "readme.md"
        custom_content = "# My Templates\n"
        readme.write_text(custom_content, encoding="utf-8")

        _build_workspace(tmp_target, content_root)

        assert readme.read_text(encoding="utf-8") == custom_content

    def test_missing_files_still_created(
        self, tmp_target: Path, content_root: Path
    ) -> None:
        """Files that don't exist are still created normally."""
        vault = _vault_root(tmp_target)
        vault.mkdir(parents=True)
        # Pre-create only bootstrap — everything else should be created
        bootstrap = vault / "_bootstrap.md"
        bootstrap.write_text("# Custom\n", encoding="utf-8")

        _build_workspace(tmp_target, content_root)

        assert (vault / "_index.md").is_file()
        assert (vault / "self" / "_index.md").is_file()
        assert (vault / "decisions" / "_index.md").is_file()

    def test_dry_run_reports_skip(
        self, tmp_target: Path, content_root: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """AC-4: Dry-run output shows [skip] for existing scaffold files."""
        vault = _vault_root(tmp_target)
        vault.mkdir(parents=True)
        bootstrap = vault / "_bootstrap.md"
        bootstrap.write_text("# Custom\n", encoding="utf-8")

        _build_workspace(tmp_target, content_root, dry_run=True)

        output = capsys.readouterr().out
        assert "[skip]" in output
        assert "_bootstrap.md" in output

    def test_existing_policy_preserved(
        self, tmp_target: Path, content_root: Path
    ) -> None:
        """AC-2: Existing policy files in code/ are skipped."""
        vault = _vault_root(tmp_target)
        (vault / "code").mkdir(parents=True)
        # Find a policy file name that ships with OWB
        policies_dir = content_root / "content" / "policies"
        if policies_dir.is_dir():
            policy_files = [f for f in policies_dir.iterdir() if f.suffix == ".md"]
            if policy_files:
                policy_name = policy_files[0].name
                dest = vault / "code" / policy_name
                custom_content = "# My Custom Policy\n"
                dest.write_text(custom_content, encoding="utf-8")

                _build_workspace(tmp_target, content_root)

                assert dest.read_text(encoding="utf-8") == custom_content


# ---------------------------------------------------------------------------
# S063: Init prevents vault nesting
# ---------------------------------------------------------------------------

class TestVaultNestingPrevention:
    """owb init must detect when target is already a vault and abort."""

    def test_target_with_bootstrap_is_detected_as_vault(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        """AC-1/AC-2: Target containing _bootstrap.md triggers an error."""
        vault_dir = tmp_path / "my_vault"
        vault_dir.mkdir()
        (vault_dir / "_bootstrap.md").write_text("# Bootstrap\n", encoding="utf-8")

        with pytest.raises(ValueError, match="appears to be a vault directory"):
            _build_workspace(vault_dir, content_root)

    def test_target_with_templates_dir_is_detected_as_vault(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        """AC-1: Target containing _templates/ triggers an error."""
        vault_dir = tmp_path / "my_vault"
        vault_dir.mkdir()
        (vault_dir / "_templates").mkdir()

        with pytest.raises(ValueError, match="appears to be a vault directory"):
            _build_workspace(vault_dir, content_root)

    def test_normal_target_proceeds(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        """Normal empty target works fine."""
        target = tmp_path / "workspace"
        _build_workspace(target, content_root)
        assert (_vault_root(target)).is_dir()

    def test_target_with_unrelated_files_proceeds(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        """Target with non-vault files is not a false positive."""
        target = tmp_path / "workspace"
        target.mkdir()
        (target / "README.md").write_text("# Readme\n", encoding="utf-8")

        _build_workspace(target, content_root)
        assert (_vault_root(target)).is_dir()

    def test_vault_nesting_does_not_create_nested_obsidian(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        """AC-2: No nested Obsidian/ directory should be created inside a vault."""
        vault_dir = tmp_path / "my_vault"
        vault_dir.mkdir()
        (vault_dir / "_bootstrap.md").write_text("# Bootstrap\n", encoding="utf-8")

        with pytest.raises(ValueError, match="appears to be a vault directory"):
            _build_workspace(vault_dir, content_root)

        # Verify no nested Obsidian/ was created
        assert not (vault_dir / "Obsidian").exists()
