"""Tests for token-analysis skill integration with OWB workflows."""

from __future__ import annotations

from pathlib import Path


class TestTokenAnalysisSkill:
    """Validate the token-analysis skill file structure."""

    def _skill_path(self) -> Path:
        """Resolve the skill directory."""
        repo_root = Path(__file__).resolve().parent.parent.parent
        return repo_root / "content" / "skills" / "token-analysis"

    def test_skill_directory_exists(self) -> None:
        assert self._skill_path().is_dir()

    def test_skill_md_exists(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        assert skill_file.exists()

    def test_skill_has_frontmatter(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert content.startswith("---")
        # Find closing frontmatter delimiter
        second_delim = content.index("---", 3)
        assert second_delim > 3

    def test_skill_has_name_field(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "name: token-analysis" in content

    def test_skill_has_description(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "description:" in content

    def test_skill_has_metadata_block(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "metadata:" in content
        assert "author:" in content
        assert "version:" in content

    def test_skill_has_license(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "license:" in content

    def test_skill_references_cli_command(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "owb metrics tokens" in content

    def test_skill_has_three_workflows(self) -> None:
        skill_file = self._skill_path() / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "Workflow 1: Sprint Close" in content
        assert "Workflow 2: Sprint Planning" in content
        assert "Workflow 3: Monthly Review" in content


class TestSprintCompleteIntegration:
    """Verify sprint-complete skill references token-analysis."""

    def test_sprint_complete_references_token_analysis(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_file = repo_root / "content" / "skills" / "sprint-complete" / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "token-analysis" in content
        assert "Token Consumption" in content or "token consumption" in content.lower()

    def test_sprint_complete_has_token_sub_item(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_file = repo_root / "content" / "skills" / "sprint-complete" / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "5a:" in content or "5a." in content
        assert "owb metrics tokens" in content


class TestSprintPlanIntegration:
    """Verify sprint-plan skill references token-analysis."""

    def test_sprint_plan_references_token_analysis(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_file = repo_root / "content" / "skills" / "sprint-plan" / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "token-analysis" in content

    def test_sprint_plan_has_cost_estimate_step(self) -> None:
        repo_root = Path(__file__).resolve().parent.parent.parent
        skill_file = repo_root / "content" / "skills" / "sprint-plan" / "SKILL.md"
        content = skill_file.read_text(encoding="utf-8")
        assert "Cost Estimate" in content
