"""Tests for agent config policy compliance preamble (Story S066, Deliverable 2)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from open_workspace_builder.config import Config
from open_workspace_builder.engine.builder import WorkspaceBuilder


PREAMBLE_MARKER = "## Policy Compliance"
PREAMBLE_FRAGMENT = "enforceable policy"


@pytest.fixture
def config_with_policies(tmp_path: Path, content_root: Path) -> tuple[Path, Config]:
    """Content root with policy files and a Config pointing to it."""
    root = tmp_path / "with-policies"
    root.mkdir()
    shutil.copytree(content_root / "content", root / "content")
    shutil.copytree(content_root / "vendor", root / "vendor")
    if (content_root / "ecc-curated").is_dir():
        shutil.copytree(content_root / "ecc-curated", root / "ecc-curated")

    # Ensure at least one policy file exists
    policies_dir = root / "content" / "policies"
    policies_dir.mkdir(parents=True, exist_ok=True)
    (policies_dir / "test-policy.md").write_text(
        "# Test Policy\n\nEnforceable content.\n", encoding="utf-8"
    )
    config = Config()
    return root, config


@pytest.fixture
def config_without_policies(tmp_path: Path, content_root: Path) -> tuple[Path, Config]:
    """Content root with no policy files."""
    root = tmp_path / "no-policies"
    root.mkdir()
    shutil.copytree(content_root / "content", root / "content")
    shutil.copytree(content_root / "vendor", root / "vendor")
    if (content_root / "ecc-curated").is_dir():
        shutil.copytree(content_root / "ecc-curated", root / "ecc-curated")

    # Remove all policies
    policies_dir = root / "content" / "policies"
    if policies_dir.exists():
        shutil.rmtree(policies_dir)
    config = Config()
    return root, config


class TestPolicyPreambleInjection:
    """AC-3: Agent config includes policy compliance preamble when policies exist."""

    def test_policy_preamble_injected_when_policies_exist(
        self, tmp_path: Path, config_with_policies: tuple[Path, Config]
    ) -> None:
        content_root, config = config_with_policies
        target = tmp_path / "workspace"
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        agent_config_path = target / config.agent_config.directory / config.agent_config.filename
        assert agent_config_path.is_file()
        content = agent_config_path.read_text(encoding="utf-8")
        assert PREAMBLE_MARKER in content
        assert PREAMBLE_FRAGMENT in content

    def test_preamble_contains_escalation_instruction(
        self, tmp_path: Path, config_with_policies: tuple[Path, Config]
    ) -> None:
        content_root, config = config_with_policies
        target = tmp_path / "workspace"
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        agent_config_path = target / config.agent_config.directory / config.agent_config.filename
        content = agent_config_path.read_text(encoding="utf-8")
        assert "Escalate to the owner" in content


class TestNoPreambleWithoutPolicies:
    """AC-4: No preamble when content/policies/ is empty or missing."""

    def test_no_preamble_when_no_policies(
        self, tmp_path: Path, config_without_policies: tuple[Path, Config]
    ) -> None:
        content_root, config = config_without_policies
        target = tmp_path / "workspace"
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        agent_config_path = target / config.agent_config.directory / config.agent_config.filename
        assert agent_config_path.is_file()
        content = agent_config_path.read_text(encoding="utf-8")
        assert PREAMBLE_MARKER not in content

    def test_no_preamble_when_policies_dir_empty(
        self, tmp_path: Path, config_without_policies: tuple[Path, Config]
    ) -> None:
        content_root, config = config_without_policies
        # Create empty policies directory
        (content_root / "content" / "policies").mkdir(parents=True, exist_ok=True)

        target = tmp_path / "workspace"
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        agent_config_path = target / config.agent_config.directory / config.agent_config.filename
        content = agent_config_path.read_text(encoding="utf-8")
        assert PREAMBLE_MARKER not in content


class TestPreamblePrivacyScrubbing:
    """AC-6 (preamble portion): No private references in preamble text."""

    BLOCKLIST = [
        "Volcanix",
        "ingest-pipeline",
        "shekel-stacker",
        "Claude Code",
        "Cowork",
        "Claude Desktop",
        "iOS Shortcut",
        "Obsidian Sync",
        "launchd",
    ]

    def test_no_private_references_in_preamble(
        self, tmp_path: Path, config_with_policies: tuple[Path, Config]
    ) -> None:
        content_root, config = config_with_policies
        target = tmp_path / "workspace"
        builder = WorkspaceBuilder(config, content_root)
        builder.build(target)

        agent_config_path = target / config.agent_config.directory / config.agent_config.filename
        content = agent_config_path.read_text(encoding="utf-8")

        # Extract preamble section
        if PREAMBLE_MARKER in content:
            preamble_start = content.index(PREAMBLE_MARKER)
            # Find next ## heading or end of file
            rest = content[preamble_start + len(PREAMBLE_MARKER):]
            next_heading = rest.find("\n## ")
            preamble = rest[:next_heading] if next_heading != -1 else rest

            for term in self.BLOCKLIST:
                assert term not in preamble, (
                    f"Private reference '{term}' found in preamble"
                )
