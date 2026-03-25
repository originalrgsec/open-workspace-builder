"""Tests for cross-project policy deployment from content/policies/ (Story S064)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from open_workspace_builder.config import Config, VaultConfig
from open_workspace_builder.engine.builder import WorkspaceBuilder
from open_workspace_builder.engine.vault import VaultBuilder


def _vault_root(workspace: Path) -> Path:
    return workspace / "Obsidian"


@pytest.fixture
def policies_content_root(tmp_path: Path, content_root: Path) -> Path:
    """Content root with test policy files in content/policies/."""
    root = tmp_path / "with-policies"
    root.mkdir()
    shutil.copytree(content_root / "content", root / "content")
    shutil.copytree(content_root / "vendor", root / "vendor")
    if (content_root / "ecc-curated").is_dir():
        shutil.copytree(content_root / "ecc-curated", root / "ecc-curated")

    policies_dir = root / "content" / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    (policies_dir / "allowed-licenses.md").write_text(
        "# Allowed Licenses\n\nTest policy content.\n", encoding="utf-8"
    )
    (policies_dir / "oss-health-policy.md").write_text(
        "# OSS Health Policy\n\nTest policy content.\n", encoding="utf-8"
    )
    (policies_dir / "_index.md").write_text(
        "# Code Policies\n\nIndex file.\n", encoding="utf-8"
    )
    return root


@pytest.fixture
def no_policies_content_root(tmp_path: Path, content_root: Path) -> Path:
    """Content root with content/policies/ removed."""
    root = tmp_path / "no-policies"
    root.mkdir()
    shutil.copytree(content_root / "content", root / "content")
    shutil.copytree(content_root / "vendor", root / "vendor")
    if (content_root / "ecc-curated").is_dir():
        shutil.copytree(content_root / "ecc-curated", root / "ecc-curated")
    policies_dir = root / "content" / "policies"
    if policies_dir.exists():
        shutil.rmtree(policies_dir)
    return root


class TestPolicyDeployment:
    """Policies from content/policies/ should be deployed to Obsidian/code/."""

    def test_policy_files_deployed_to_code_dir(
        self, tmp_path: Path, policies_content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, policies_content_root)
        builder.build(target)
        code_dir = _vault_root(target) / "code"
        assert (code_dir / "allowed-licenses.md").is_file()
        assert (code_dir / "oss-health-policy.md").is_file()
        assert (code_dir / "_index.md").is_file()

    def test_policy_content_matches_source(
        self, tmp_path: Path, policies_content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, policies_content_root)
        builder.build(target)
        deployed = (_vault_root(target) / "code" / "allowed-licenses.md").read_text(
            encoding="utf-8"
        )
        assert "Test policy content." in deployed

    def test_policy_files_tracked_in_created_files(
        self, tmp_path: Path, policies_content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        vault_config = VaultConfig()
        vault_builder = VaultBuilder(vault_config, policies_content_root)
        vault_builder.build(target)
        created_names = [p.name for p in vault_builder.created_files]
        assert "allowed-licenses.md" in created_names
        assert "oss-health-policy.md" in created_names


class TestPolicyDeploymentGracefulSkip:
    """Missing or empty content/policies/ should not cause errors."""

    def test_no_error_when_policies_dir_missing(
        self, tmp_path: Path, no_policies_content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, no_policies_content_root)
        builder.build(target)
        assert _vault_root(target).is_dir()
        assert (_vault_root(target) / "code" / "_index.md").is_file()

    def test_empty_policies_dir_skipped(
        self, tmp_path: Path, no_policies_content_root: Path
    ) -> None:
        (no_policies_content_root / "content" / "policies").mkdir()
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, no_policies_content_root)
        builder.build(target)
        assert _vault_root(target).is_dir()


class TestPolicyDeploymentDryRun:
    """Dry run should report but not write policy files."""

    def test_dry_run_does_not_write_policies(
        self, tmp_path: Path, policies_content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        vault_config = VaultConfig()
        vault_builder = VaultBuilder(vault_config, policies_content_root, dry_run=True)
        vault_builder.build(target)
        code_dir = _vault_root(target) / "code"
        assert not (code_dir / "allowed-licenses.md").exists()

    def test_dry_run_still_tracks_files(
        self, tmp_path: Path, policies_content_root: Path
    ) -> None:
        target = tmp_path / "workspace"
        vault_config = VaultConfig()
        vault_builder = VaultBuilder(vault_config, policies_content_root, dry_run=True)
        vault_builder.build(target)
        created_names = [p.name for p in vault_builder.created_files]
        assert "allowed-licenses.md" in created_names


class TestPolicyDeploymentWithRealContent:
    """Integration test using the actual content/policies/ from the OWB repo."""

    def test_real_policies_deployed_if_present(
        self, tmp_path: Path, content_root: Path
    ) -> None:
        policies_dir = content_root / "content" / "policies"
        if not policies_dir.is_dir():
            pytest.skip("No content/policies/ in this repo")
        target = tmp_path / "workspace"
        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)
        code_dir = _vault_root(target) / "code"
        for policy_file in policies_dir.iterdir():
            if policy_file.is_file() and policy_file.suffix == ".md":
                assert (code_dir / policy_file.name).is_file(), (
                    f"Policy {policy_file.name} not deployed to code/"
                )
