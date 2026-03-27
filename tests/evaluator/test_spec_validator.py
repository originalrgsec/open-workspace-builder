"""Tests for Agent Skills spec validation."""

from __future__ import annotations

import textwrap
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from open_workspace_builder.evaluator.spec_validator import (
    SpecValidationResult,
    validate_frontmatter,
    validate_skill,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def skill_dir(tmp_path: Path) -> Path:
    """Create a minimal valid skill directory."""
    d = tmp_path / "my-skill"
    d.mkdir()
    (d / "SKILL.md").write_text(
        textwrap.dedent("""\
            ---
            name: my-skill
            description: "Use this when the user asks for X."
            ---

            # My Skill

            Body content here.
        """),
        encoding="utf-8",
    )
    return d


@pytest.fixture()
def ecc_skill_dir(tmp_path: Path) -> Path:
    """Create a skill directory under an ECC-like path."""
    d = tmp_path / "ecc-curated" / "agents" / "test-agent"
    d.mkdir(parents=True)
    (d / "SKILL.md").write_text(
        textwrap.dedent("""\
            ---
            name: test-agent
            description: "A test agent."
            tools: ["Read", "Write"]
            model: sonnet
            ---

            Body.
        """),
        encoding="utf-8",
    )
    return d


# ---------------------------------------------------------------------------
# SKILL.md missing -> error
# ---------------------------------------------------------------------------


class TestSkillMdMissing:
    def test_missing_skill_md(self, tmp_path: Path) -> None:
        d = tmp_path / "empty-skill"
        d.mkdir()
        result = validate_skill(str(d))
        assert not result.valid
        assert any("SKILL.md not found" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Frontmatter missing -> error
# ---------------------------------------------------------------------------


class TestFrontmatterMissing:
    def test_no_frontmatter_delimiters(self, tmp_path: Path) -> None:
        d = tmp_path / "no-fm"
        d.mkdir()
        (d / "SKILL.md").write_text("# Just a heading\nNo frontmatter.", encoding="utf-8")
        result = validate_skill(str(d))
        assert not result.valid
        assert any("frontmatter not found" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Name field validation
# ---------------------------------------------------------------------------


class TestNameValidation:
    def test_valid_name(self) -> None:
        fm = {"name": "my-skill", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert result.valid
        assert not result.errors

    def test_name_too_long(self) -> None:
        fm = {"name": "a" * 65, "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("exceeds 64" in e for e in result.errors)

    def test_name_uppercase(self) -> None:
        fm = {"name": "My-Skill", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("lowercase" in e for e in result.errors)

    def test_name_leading_hyphen(self) -> None:
        fm = {"name": "-my-skill", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("start with a hyphen" in e for e in result.errors)

    def test_name_trailing_hyphen(self) -> None:
        fm = {"name": "my-skill-", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("end with a hyphen" in e for e in result.errors)

    def test_name_consecutive_hyphens(self) -> None:
        fm = {"name": "my--skill", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("consecutive hyphens" in e for e in result.errors)

    def test_name_missing(self) -> None:
        fm = {"description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("Missing required field: name" in e for e in result.errors)

    def test_name_dir_mismatch(self, tmp_path: Path) -> None:
        d = tmp_path / "wrong-name"
        d.mkdir()
        (d / "SKILL.md").write_text(
            "---\nname: different-name\ndescription: Use this when X.\n---\nBody.",
            encoding="utf-8",
        )
        result = validate_skill(str(d))
        assert not result.valid
        assert any("does not match directory" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Description field validation
# ---------------------------------------------------------------------------


class TestDescriptionValidation:
    def test_valid_description(self) -> None:
        fm = {"name": "test", "description": "Use this when you need help."}
        result = validate_frontmatter(fm)
        assert result.valid

    def test_description_empty(self) -> None:
        fm = {"name": "test", "description": ""}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("Missing required field: description" in e for e in result.errors)

    def test_description_too_long(self) -> None:
        fm = {"name": "test", "description": "x" * 1025}
        result = validate_frontmatter(fm)
        assert not result.valid
        assert any("exceeds 1024" in e for e in result.errors)


# ---------------------------------------------------------------------------
# Optional fields validation
# ---------------------------------------------------------------------------


class TestOptionalFields:
    def test_compatibility_too_long(self) -> None:
        fm = {
            "name": "test",
            "description": "Use this when needed.",
            "compatibility": "x" * 501,
        }
        result = validate_frontmatter(fm)
        assert result.valid  # compatibility issues are warnings
        assert any("Compatibility exceeds" in w for w in result.warnings)

    def test_allowed_tools_valid(self) -> None:
        fm = {
            "name": "test",
            "description": "Use this when needed.",
            "allowed-tools": "Read Write Glob",
        }
        result = validate_frontmatter(fm)
        assert result.valid
        assert not any("allowed-tools" in w for w in result.warnings)

    def test_allowed_tools_suspicious(self) -> None:
        fm = {
            "name": "test",
            "description": "Use this when needed.",
            "allowed-tools": "Read ../bad-path",
        }
        result = validate_frontmatter(fm)
        assert any("suspicious token" in w for w in result.warnings)

    def test_license_field_accepted(self) -> None:
        fm = {
            "name": "test",
            "description": "Use this when something happens.",
            "license": "MIT",
        }
        result = validate_frontmatter(fm)
        assert result.valid


# ---------------------------------------------------------------------------
# Body length warning
# ---------------------------------------------------------------------------


class TestBodyLength:
    def test_body_under_500_no_warning(self, tmp_path: Path) -> None:
        d = tmp_path / "short-body"
        d.mkdir()
        body = "\n".join(f"Line {i}" for i in range(100))
        (d / "SKILL.md").write_text(
            f"---\nname: short-body\ndescription: Use this when X.\n---\n{body}",
            encoding="utf-8",
        )
        result = validate_skill(str(d))
        assert not any("body exceeds" in w for w in result.warnings)

    def test_body_over_500_warning(self, tmp_path: Path) -> None:
        d = tmp_path / "long-body"
        d.mkdir()
        body = "\n".join(f"Line {i}" for i in range(510))
        (d / "SKILL.md").write_text(
            f"---\nname: long-body\ndescription: Use this when X.\n---\n{body}",
            encoding="utf-8",
        )
        result = validate_skill(str(d))
        assert any("body exceeds" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Missing subdirectories warning
# ---------------------------------------------------------------------------


class TestSubdirectoryWarnings:
    def test_missing_all_subdirs(self, skill_dir: Path) -> None:
        result = validate_skill(str(skill_dir))
        assert any("Missing optional subdirectories" in w for w in result.warnings)

    def test_has_all_subdirs(self, skill_dir: Path) -> None:
        for d in ("scripts", "references", "assets"):
            (skill_dir / d).mkdir()
        result = validate_skill(str(skill_dir))
        assert not any("Missing optional subdirectories" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Description trigger keyword warning
# ---------------------------------------------------------------------------


class TestTriggerKeywordWarning:
    def test_no_trigger_keyword(self) -> None:
        fm = {"name": "test", "description": "A simple skill."}
        result = validate_frontmatter(fm)
        assert any("trigger keywords" in w for w in result.warnings)

    def test_has_when_keyword(self) -> None:
        fm = {"name": "test", "description": "Use when the user asks."}
        result = validate_frontmatter(fm)
        assert not any("trigger keywords" in w for w in result.warnings)

    def test_has_use_this_keyword(self) -> None:
        fm = {"name": "test", "description": "Use this to check vault."}
        result = validate_frontmatter(fm)
        assert not any("trigger keywords" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# ECC skill exemption: non-standard frontmatter -> warning not error
# ---------------------------------------------------------------------------


class TestEccExemption:
    def test_ecc_nonstandard_fields_are_warnings(self, ecc_skill_dir: Path) -> None:
        result = validate_skill(str(ecc_skill_dir))
        assert result.valid

    def test_ecc_missing_name_is_warning(self, tmp_path: Path) -> None:
        d = tmp_path / "ecc-curated" / "agents" / "bad-agent"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\ndescription: A test.\n---\nBody.",
            encoding="utf-8",
        )
        result = validate_skill(str(d))
        assert result.valid
        assert any("Missing required field: name" in w for w in result.warnings)

    def test_ecc_missing_frontmatter_is_warning(self, tmp_path: Path) -> None:
        d = tmp_path / "vendor" / "ecc" / "agents" / "no-fm"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text("# No frontmatter\nJust body.", encoding="utf-8")
        result = validate_skill(str(d))
        assert result.valid
        assert any("frontmatter not found" in w for w in result.warnings)

    def test_ecc_name_dir_mismatch_is_warning(self, tmp_path: Path) -> None:
        d = tmp_path / "ecc-curated" / "agents" / "actual-name"
        d.mkdir(parents=True)
        (d / "SKILL.md").write_text(
            "---\nname: different-name\ndescription: Use this when testing.\n---\nBody.",
            encoding="utf-8",
        )
        result = validate_skill(str(d))
        assert result.valid
        assert any("does not match directory" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Real custom skills: all 3 pass
# ---------------------------------------------------------------------------


class TestRealCustomSkills:
    """Validate the actual custom skills in content/skills/."""

    @pytest.fixture()
    def content_skills_dir(self) -> Path:
        candidate = Path(__file__).resolve().parent.parent.parent
        skills_dir = candidate / "content" / "skills"
        if not skills_dir.exists():
            pytest.skip("content/skills/ not found in repo")
        return skills_dir

    @pytest.mark.parametrize(
        "skill_name",
        ["mobile-inbox-triage", "oss-health-check", "skill-creator", "vault-audit"],
    )
    def test_custom_skill_passes(self, content_skills_dir: Path, skill_name: str) -> None:
        skill_path = content_skills_dir / skill_name
        if not skill_path.exists():
            pytest.skip(f"{skill_name} not found")
        result = validate_skill(str(skill_path))
        assert result.valid, f"{skill_name} validation failed: {result.errors}"


# ---------------------------------------------------------------------------
# SpecValidationResult is frozen
# ---------------------------------------------------------------------------


class TestResultImmutability:
    def test_result_is_frozen(self) -> None:
        result = SpecValidationResult(valid=True, errors=[], warnings=[])
        with pytest.raises(AttributeError):
            result.valid = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_single_char_name(self) -> None:
        fm = {"name": "a", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert result.valid

    def test_name_with_numbers(self) -> None:
        fm = {"name": "skill-v2", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert result.valid

    def test_name_all_numbers(self) -> None:
        fm = {"name": "123", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert result.valid

    def test_name_with_spaces(self) -> None:
        fm = {"name": "my skill", "description": "Use this when needed."}
        result = validate_frontmatter(fm)
        assert not result.valid

    def test_empty_frontmatter(self) -> None:
        result = validate_frontmatter({})
        assert not result.valid


# ---------------------------------------------------------------------------
# CLI output: human-readable format
# ---------------------------------------------------------------------------


class TestCliValidateCommand:
    def test_cli_pass(self, skill_dir: Path) -> None:
        from open_workspace_builder.cli import owb

        runner = CliRunner()
        result = runner.invoke(owb, ["validate", str(skill_dir)])
        assert result.exit_code == 0
        assert "[PASS]" in result.output

    def test_cli_fail(self, tmp_path: Path) -> None:
        from open_workspace_builder.cli import owb

        d = tmp_path / "bad-skill"
        d.mkdir()
        (d / "SKILL.md").write_text("No frontmatter here.", encoding="utf-8")
        runner = CliRunner()
        result = runner.invoke(owb, ["validate", str(d)])
        assert result.exit_code == 1
        assert "[FAIL]" in result.output
        assert "Errors:" in result.output


# ---------------------------------------------------------------------------
# Integration: SkillsInstaller warns but still installs on validation failure
# ---------------------------------------------------------------------------


class TestSkillsInstallerIntegration:
    def test_installer_warns_but_installs(self, tmp_path: Path) -> None:
        from open_workspace_builder.engine.skills import SkillsInstaller

        content_root = tmp_path / "content"
        skills_src = content_root / "skills" / "bad-name"
        skills_src.mkdir(parents=True)
        (skills_src / "SKILL.md").write_text(
            "---\nname: wrong-name\ndescription: Use this when X.\n---\nBody.",
            encoding="utf-8",
        )

        config = MagicMock()
        config.source_dir = "skills"
        config.install = ["bad-name"]

        installer = SkillsInstaller(config, content_root, dry_run=False)
        target = tmp_path / "output"
        target.mkdir()
        installer.install(target)

        installed = target / ".skills" / "skills" / "bad-name" / "SKILL.md"
        assert installed.exists()

    def test_installer_valid_skill_no_error_output(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from open_workspace_builder.engine.skills import SkillsInstaller

        content_root = tmp_path / "content"
        skills_src = content_root / "skills" / "good-skill"
        skills_src.mkdir(parents=True)
        (skills_src / "SKILL.md").write_text(
            "---\nname: good-skill\ndescription: Use this when X.\n---\nBody.",
            encoding="utf-8",
        )

        config = MagicMock()
        config.source_dir = "skills"
        config.install = ["good-skill"]

        installer = SkillsInstaller(config, content_root, dry_run=False)
        target = tmp_path / "output"
        target.mkdir()
        installer.install(target)

        captured = capsys.readouterr()
        assert "validation errors" not in captured.out


# ---------------------------------------------------------------------------
# Integration: EvaluationManager rejects on hard errors
# ---------------------------------------------------------------------------


class TestEvaluationManagerIntegration:
    def test_evaluate_new_rejects_invalid_skill(self, tmp_path: Path) -> None:
        from open_workspace_builder.evaluator.manager import (
            EvaluationDecision,
            EvaluationManager,
        )

        skill_dir = tmp_path / "invalid-skill"
        skill_dir.mkdir()

        mock_backend = MagicMock()
        mock_persistence = MagicMock()

        manager = EvaluationManager(mock_backend, mock_persistence)
        result = manager.evaluate_new(str(skill_dir))

        assert result.decision == EvaluationDecision.REJECT
        assert "Spec validation failed" in result.reasoning
