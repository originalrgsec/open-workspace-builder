"""Tests for pre-commit hook framework (OWB-S088).

Covers: HookEntry dataclass, default_hooks(), generate_precommit_config(),
merge_precommit_config(), builder integration, CLI commands, and --all flag.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml
from click.testing import CliRunner

from open_workspace_builder.cli import owb
from open_workspace_builder.security.hooks import (
    HookEntry,
    default_hooks,
    generate_precommit_config,
    merge_precommit_config,
)


# ── Unit tests: hooks module ────────────────────────────────────────────


class TestDefaultHooks:
    """AC-1: default_hooks returns correct hook entries for gitleaks and ruff."""

    def test_returns_tuple(self) -> None:
        hooks = default_hooks()
        assert isinstance(hooks, tuple)

    def test_contains_gitleaks(self) -> None:
        hooks = default_hooks()
        ids = [h.hook_id for h in hooks]
        assert "gitleaks" in ids

    def test_contains_ruff(self) -> None:
        hooks = default_hooks()
        ids = [h.hook_id for h in hooks]
        assert "ruff" in ids

    def test_contains_ruff_format(self) -> None:
        hooks = default_hooks()
        ids = [h.hook_id for h in hooks]
        assert "ruff-format" in ids

    def test_contains_trivy(self) -> None:
        hooks = default_hooks()
        ids = [h.hook_id for h in hooks]
        assert "trivy" in ids

    def test_contains_semgrep(self) -> None:
        hooks = default_hooks()
        ids = [h.hook_id for h in hooks]
        assert "semgrep" in ids

    def test_trivy_uses_local_repo(self) -> None:
        hooks = default_hooks()
        trivy = [h for h in hooks if h.hook_id == "trivy"][0]
        assert trivy.repo == "local"
        assert trivy.rev is None

    def test_semgrep_uses_official_repo(self) -> None:
        hooks = default_hooks()
        semgrep = [h for h in hooks if h.hook_id == "semgrep"][0]
        assert "semgrep/pre-commit" in semgrep.repo

    def test_gitleaks_uses_official_repo(self) -> None:
        hooks = default_hooks()
        gitleaks = [h for h in hooks if h.hook_id == "gitleaks"][0]
        assert "gitleaks/gitleaks" in gitleaks.repo

    def test_ruff_uses_official_repo(self) -> None:
        hooks = default_hooks()
        ruff = [h for h in hooks if h.hook_id == "ruff"][0]
        assert "astral-sh/ruff-pre-commit" in ruff.repo

    def test_hook_entry_is_frozen(self) -> None:
        hook = default_hooks()[0]
        with pytest.raises(AttributeError):
            hook.hook_id = "changed"  # type: ignore[misc]

    def test_all_remote_hooks_have_pinned_revs(self) -> None:
        for hook in default_hooks():
            if hook.repo != "local":
                assert hook.rev is not None, f"Hook {hook.hook_id} has no pinned rev"


class TestGeneratePrecommitConfig:
    """AC-1: generates valid YAML with correct structure."""

    def test_generates_valid_yaml(self) -> None:
        content = generate_precommit_config()
        parsed = yaml.safe_load(content)
        assert "repos" in parsed

    def test_default_has_four_repos(self) -> None:
        content = generate_precommit_config()
        parsed = yaml.safe_load(content)
        # gitleaks + ruff + trivy + semgrep
        assert len(parsed["repos"]) == 4

    def test_gitleaks_repo_structure(self) -> None:
        content = generate_precommit_config()
        parsed = yaml.safe_load(content)
        gitleaks_repo = [r for r in parsed["repos"] if "gitleaks" in r["repo"]][0]
        assert "rev" in gitleaks_repo
        assert "hooks" in gitleaks_repo
        assert gitleaks_repo["hooks"][0]["id"] == "gitleaks"

    def test_ruff_repo_has_two_hooks(self) -> None:
        content = generate_precommit_config()
        parsed = yaml.safe_load(content)
        ruff_repo = [r for r in parsed["repos"] if "ruff" in r["repo"]][0]
        hook_ids = [h["id"] for h in ruff_repo["hooks"]]
        assert "ruff" in hook_ids
        assert "ruff-format" in hook_ids

    def test_ruff_hook_has_fix_arg(self) -> None:
        content = generate_precommit_config()
        parsed = yaml.safe_load(content)
        ruff_repo = [r for r in parsed["repos"] if "ruff" in r["repo"]][0]
        ruff_hook = [h for h in ruff_repo["hooks"] if h["id"] == "ruff"][0]
        assert "--fix" in ruff_hook.get("args", [])

    def test_accepts_custom_hooks(self) -> None:
        custom = (
            HookEntry(
                repo="https://example.com/custom",
                rev="v1.0.0",
                hook_id="custom-hook",
                name="Custom Hook",
                entry="custom-cmd",
                language="system",
            ),
        )
        content = generate_precommit_config(hooks=custom)
        parsed = yaml.safe_load(content)
        assert len(parsed["repos"]) == 1
        assert parsed["repos"][0]["hooks"][0]["id"] == "custom-hook"


class TestMergePrecommitConfig:
    """Merges new hooks into existing config without overwriting user hooks."""

    def test_merges_new_repo(self) -> None:
        existing = yaml.dump(
            {
                "repos": [
                    {
                        "repo": "https://github.com/user/custom",
                        "rev": "v1.0",
                        "hooks": [{"id": "custom-lint"}],
                    }
                ]
            }
        )
        new_hooks = default_hooks()
        result = merge_precommit_config(existing, new_hooks)
        parsed = yaml.safe_load(result)
        repo_urls = [r["repo"] for r in parsed["repos"]]
        assert "https://github.com/user/custom" in repo_urls
        assert any("gitleaks" in u for u in repo_urls)

    def test_no_duplicates(self) -> None:
        """Does not add duplicate hooks when repo already has the hook."""
        existing_config = generate_precommit_config()
        new_hooks = default_hooks()
        result = merge_precommit_config(existing_config, new_hooks)
        parsed = yaml.safe_load(result)
        gitleaks_repos = [r for r in parsed["repos"] if "gitleaks" in r["repo"]]
        assert len(gitleaks_repos) == 1

    def test_preserves_user_hooks_in_same_repo(self) -> None:
        """If user already has a repo with extra hooks, preserve them."""
        existing = yaml.dump(
            {
                "repos": [
                    {
                        "repo": "https://github.com/astral-sh/ruff-pre-commit",
                        "rev": "v0.10.0",
                        "hooks": [
                            {"id": "ruff", "args": ["--select", "E"]},
                        ],
                    }
                ]
            }
        )
        new_hooks = default_hooks()
        result = merge_precommit_config(existing, new_hooks)
        parsed = yaml.safe_load(result)
        ruff_repo = [r for r in parsed["repos"] if "ruff" in r["repo"]][0]
        # User's existing ruff hook config should be preserved (not overwritten)
        ruff_hook = [h for h in ruff_repo["hooks"] if h["id"] == "ruff"][0]
        assert "--select" in ruff_hook.get("args", [])

    def test_handles_empty_existing(self) -> None:
        result = merge_precommit_config("", default_hooks())
        parsed = yaml.safe_load(result)
        assert "repos" in parsed
        assert len(parsed["repos"]) >= 2


# ── Builder integration ─────────────────────────────────────────────────


class TestBuilderDeploysPrecommitConfig:
    """AC-1: WorkspaceBuilder generates .pre-commit-config.yaml during init."""

    def test_generates_precommit_config(self, tmp_target: Path, content_root: Path) -> None:
        from open_workspace_builder.config import Config
        from open_workspace_builder.engine.builder import WorkspaceBuilder

        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(tmp_target)
        precommit_path = tmp_target / ".pre-commit-config.yaml"
        assert precommit_path.is_file()
        parsed = yaml.safe_load(precommit_path.read_text(encoding="utf-8"))
        assert "repos" in parsed

    def test_skips_existing_precommit_config(self, tmp_target: Path, content_root: Path) -> None:
        from open_workspace_builder.config import Config
        from open_workspace_builder.engine.builder import WorkspaceBuilder

        tmp_target.mkdir(parents=True, exist_ok=True)
        precommit_path = tmp_target / ".pre-commit-config.yaml"
        precommit_path.write_text("# user config\nrepos: []\n", encoding="utf-8")

        config = Config()
        builder = WorkspaceBuilder(config, content_root)
        builder.build(tmp_target)
        # Should NOT overwrite user's file
        assert precommit_path.read_text(encoding="utf-8").startswith("# user config")


# ── CLI: scan --all flag ────────────────────────────────────────────────


class TestScanAllFlag:
    """AC-3: --all enables SCA and SAST."""

    def test_all_flag_exists(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["security", "scan", "--help"])
        assert "--all" in result.output

    @patch("open_workspace_builder.cli._run_sast_scan")
    @patch("open_workspace_builder.cli._run_sca_scan")
    def test_all_enables_sca_and_sast(
        self,
        mock_sca: MagicMock,
        mock_sast: MagicMock,
        tmp_path: Path,
    ) -> None:
        mock_sca.return_value = {
            "vulnerabilities": [],
            "guarddog_flagged": [],
            "packages_scanned": [],
        }
        mock_sast.return_value = {"findings": [], "errors": [], "rules_run": 0}

        # Create a scannable file
        test_file = tmp_path / "test.md"
        test_file.write_text("Hello world", encoding="utf-8")

        runner = CliRunner()
        runner.invoke(owb, ["security", "scan", "--all", str(test_file)])
        # Both SCA and SAST should have been called
        mock_sca.assert_called_once()
        mock_sast.assert_called_once()


# ── CLI: hooks subgroup ─────────────────────────────────────────────────


class TestHooksCli:
    """AC-4: hooks install and hooks status commands work."""

    def test_hooks_group_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["security", "hooks", "--help"])
        assert result.exit_code == 0
        assert "install" in result.output
        assert "status" in result.output

    def test_hooks_install_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["security", "hooks", "install", "--help"])
        assert result.exit_code == 0

    def test_hooks_status_help(self) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["security", "hooks", "status", "--help"])
        assert result.exit_code == 0

    @patch("subprocess.run")
    def test_hooks_install_generates_config(self, mock_run: MagicMock, tmp_path: Path) -> None:
        # Mock pre-commit availability and execution
        mock_run.return_value = MagicMock(returncode=0, stdout="pre-commit 3.0.0\n")

        runner = CliRunner()
        runner.invoke(owb, ["security", "hooks", "install", str(tmp_path)])
        precommit_path = tmp_path / ".pre-commit-config.yaml"
        assert precommit_path.is_file()

    @patch("subprocess.run")
    def test_hooks_install_runs_precommit_install(
        self, mock_run: MagicMock, tmp_path: Path
    ) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="pre-commit 3.0.0\n")

        runner = CliRunner()
        runner.invoke(owb, ["security", "hooks", "install", str(tmp_path)])
        # Should have called pre-commit --version, pre-commit install, pre-commit run
        commands = [call.args[0] for call in mock_run.call_args_list]
        assert any("install" in cmd for cmd in commands)

    def test_hooks_status_shows_config(self, tmp_path: Path) -> None:
        # Create a pre-commit config
        config_path = tmp_path / ".pre-commit-config.yaml"
        config_path.write_text(generate_precommit_config(), encoding="utf-8")

        runner = CliRunner()
        result = runner.invoke(owb, ["security", "hooks", "status", str(tmp_path)])
        assert result.exit_code == 0
        assert "gitleaks" in result.output

    def test_hooks_status_no_config(self, tmp_path: Path) -> None:
        runner = CliRunner()
        result = runner.invoke(owb, ["security", "hooks", "status", str(tmp_path)])
        assert result.exit_code == 0
        assert "No .pre-commit-config.yaml" in result.output


# ── Init: prompt for existing projects ─────────────────────────────────


class TestInitHooksPrompt:
    """owb init prompts to install hooks on sibling projects."""

    def test_prompt_hooks_creates_config_for_siblings(self, tmp_path: Path) -> None:
        from open_workspace_builder.cli import _prompt_hooks_for_existing_projects

        # Create a workspace and a sibling git repo without hooks
        workspace = tmp_path / "my-project"
        workspace.mkdir()
        sibling = tmp_path / "other-project"
        (sibling / ".git").mkdir(parents=True)

        # Simulate user answering "yes"
        with patch("click.confirm", return_value=True):
            _prompt_hooks_for_existing_projects(workspace)

        assert (sibling / ".pre-commit-config.yaml").is_file()

    def test_prompt_hooks_skips_projects_with_existing_config(self, tmp_path: Path) -> None:
        from open_workspace_builder.cli import _prompt_hooks_for_existing_projects

        workspace = tmp_path / "my-project"
        workspace.mkdir()
        sibling = tmp_path / "other-project"
        (sibling / ".git").mkdir(parents=True)
        (sibling / ".pre-commit-config.yaml").write_text("# existing\n")

        with patch("click.confirm", return_value=True) as mock_confirm:
            _prompt_hooks_for_existing_projects(workspace)

        # Should not prompt since no candidates
        mock_confirm.assert_not_called()

    def test_prompt_hooks_respects_user_decline(self, tmp_path: Path) -> None:
        from open_workspace_builder.cli import _prompt_hooks_for_existing_projects

        workspace = tmp_path / "my-project"
        workspace.mkdir()
        sibling = tmp_path / "other-project"
        (sibling / ".git").mkdir(parents=True)

        with patch("click.confirm", return_value=False):
            _prompt_hooks_for_existing_projects(workspace)

        assert not (sibling / ".pre-commit-config.yaml").is_file()
