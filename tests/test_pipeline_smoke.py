"""Pipeline smoke test.

Mandatory per integration-verification-policy §2. Exercises the primary owb
CLI workflows end-to-end through the Click CliRunner, verifying that data
flows through the complete chain: config → builder → output on disk.

These tests use --no-wizard and --dry-run where appropriate to avoid
interactive prompts and external side effects.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner(mix_stderr=False)


@pytest.fixture()
def content_root() -> Path:
    root = Path(__file__).resolve().parent.parent
    assert (root / "content").is_dir(), f"content/ not found at {root}"
    return root


@pytest.fixture()
def minimal_config(tmp_path: Path) -> Path:
    """Write a minimal YAML config and return its path."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(
        "target: output\n"
        "vault:\n"
        "  name: SmokeTestVault\n"
        "  create_templates: true\n",
        encoding="utf-8",
    )
    return config_file


class TestInitPipeline:
    """owb init builds a workspace from config to disk."""

    VAULT_NAME = "SmokeTestVault"

    def test_init_creates_workspace(
        self, runner: CliRunner, tmp_path: Path, minimal_config: Path
    ) -> None:
        target = tmp_path / "workspace"
        result = runner.invoke(
            owb, ["init", "--target", str(target), "--config", str(minimal_config), "--no-wizard"]
        )
        assert result.exit_code == 0, f"init failed:\n{result.output}"
        vault = target / self.VAULT_NAME
        assert vault.is_dir(), f"Vault directory '{self.VAULT_NAME}' not created"
        assert (vault / "_templates").is_dir(), "Templates directory not created"

    def test_init_creates_vault_bootstrap(
        self, runner: CliRunner, tmp_path: Path, minimal_config: Path
    ) -> None:
        target = tmp_path / "workspace"
        result = runner.invoke(
            owb, ["init", "--target", str(target), "--config", str(minimal_config), "--no-wizard"]
        )
        assert result.exit_code == 0
        bootstrap = target / self.VAULT_NAME / "_bootstrap.md"
        assert bootstrap.exists(), "_bootstrap.md not created in vault"

    def test_init_creates_agent_config(
        self, runner: CliRunner, tmp_path: Path, minimal_config: Path
    ) -> None:
        target = tmp_path / "workspace"
        result = runner.invoke(
            owb, ["init", "--target", str(target), "--config", str(minimal_config), "--no-wizard"]
        )
        assert result.exit_code == 0
        workspace_md = target / ".ai" / "WORKSPACE.md"
        assert workspace_md.exists(), "WORKSPACE.md not created"

    def test_init_dry_run_creates_nothing(
        self, runner: CliRunner, tmp_path: Path, minimal_config: Path
    ) -> None:
        target = tmp_path / "workspace"
        result = runner.invoke(
            owb,
            ["init", "--target", str(target), "--config", str(minimal_config), "--no-wizard", "--dry-run"],
        )
        assert result.exit_code == 0
        assert not target.exists(), "Dry run should not create target directory"


class TestDiffPipeline:
    """owb diff detects drift between a built workspace and reference state."""

    VAULT_NAME = "SmokeTestVault"

    def test_diff_runs_and_produces_summary(
        self, runner: CliRunner, tmp_path: Path, minimal_config: Path
    ) -> None:
        target = tmp_path / "workspace"
        # Build first
        init_result = runner.invoke(
            owb, ["init", "--target", str(target), "--config", str(minimal_config), "--no-wizard"]
        )
        assert init_result.exit_code == 0, f"init failed:\n{init_result.output}"
        vault_path = target / self.VAULT_NAME
        assert vault_path.is_dir()
        # Diff should run without crashing and produce a summary line
        result = runner.invoke(owb, ["diff", str(vault_path), "--config", str(minimal_config)])
        assert result.exit_code in (0, 1), f"diff crashed:\n{result.output}"
        assert "Summary" in result.output or "summary" in result.output.lower()

    def test_diff_detects_modified_file(
        self, runner: CliRunner, tmp_path: Path, minimal_config: Path
    ) -> None:
        target = tmp_path / "workspace"
        runner.invoke(
            owb, ["init", "--target", str(target), "--config", str(minimal_config), "--no-wizard"]
        )
        vault_path = target / self.VAULT_NAME
        # Modify a template to create drift
        templates = list((vault_path / "_templates").glob("*.md"))
        if templates:
            templates[0].write_text("# modified by smoke test\n", encoding="utf-8")
            result = runner.invoke(owb, ["diff", str(vault_path), "--config", str(minimal_config)])
            # exit 1 indicates drift detected
            assert result.exit_code == 1, f"diff should detect drift:\n{result.output}"


class TestAuthPipeline:
    """owb auth commands work through the CLI without crashing."""

    def test_auth_status_runs(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "status"])
        # May succeed or fail depending on env, but should not crash (exit 2 = Click usage error)
        assert result.exit_code != 2, f"auth status is not a valid command:\n{result.output}"

    def test_auth_backends_lists(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["auth", "backends"])
        assert result.exit_code == 0
        assert "env" in result.output.lower(), "env backend should always be listed"


class TestEccPipeline:
    """owb ecc status runs without error."""

    def test_ecc_status_runs(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["ecc", "status"])
        # Exit code 0 or 1 both acceptable (1 = no ECC installed), but not 2 (usage error)
        assert result.exit_code != 2, f"ecc status is not a valid command:\n{result.output}"
