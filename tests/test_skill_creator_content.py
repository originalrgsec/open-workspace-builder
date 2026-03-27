"""Tests for the skill-creator SKILL.md content and spec compliance."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml


SKILL_DIR = Path(__file__).resolve().parent.parent / "content" / "skills" / "skill-creator"
SKILL_MD = SKILL_DIR / "SKILL.md"


@pytest.fixture()
def skill_text() -> str:
    """Read the skill-creator SKILL.md content."""
    if not SKILL_MD.exists():
        pytest.fail(f"SKILL.md not found at {SKILL_MD}")
    return SKILL_MD.read_text(encoding="utf-8")


@pytest.fixture()
def frontmatter(skill_text: str) -> dict:
    """Parse YAML frontmatter from SKILL.md."""
    if not skill_text.startswith("---"):
        pytest.fail("SKILL.md does not start with YAML frontmatter delimiter")
    end = skill_text.index("---", 3)
    raw = skill_text[3:end].strip()
    return yaml.safe_load(raw)


# ---------------------------------------------------------------------------
# Existence
# ---------------------------------------------------------------------------


class TestSkillCreatorExists:
    def test_skill_dir_exists(self) -> None:
        assert SKILL_DIR.is_dir(), f"Skill directory not found at {SKILL_DIR}"

    def test_skill_md_exists(self) -> None:
        assert SKILL_MD.is_file(), f"SKILL.md not found at {SKILL_MD}"


# ---------------------------------------------------------------------------
# Frontmatter validation
# ---------------------------------------------------------------------------


class TestFrontmatter:
    def test_has_name(self, frontmatter: dict) -> None:
        assert "name" in frontmatter
        assert frontmatter["name"] == "skill-creator"

    def test_has_description(self, frontmatter: dict) -> None:
        assert "description" in frontmatter
        desc = frontmatter["description"]
        assert isinstance(desc, str)
        assert len(desc) > 0
        assert len(desc) <= 1024

    def test_description_has_trigger_keywords(self, frontmatter: dict) -> None:
        desc = frontmatter["description"].lower()
        has_trigger = any(
            kw in desc for kw in ["when", "use this", "should be used", "trigger"]
        )
        assert has_trigger, "Description should include trigger keywords"


# ---------------------------------------------------------------------------
# Spec compliance section
# ---------------------------------------------------------------------------


class TestSpecComplianceSection:
    def test_contains_spec_compliance_heading(self, skill_text: str) -> None:
        assert "Spec Compliance" in skill_text

    def test_references_agentskills_spec(self, skill_text: str) -> None:
        assert "agentskills.io/specification" in skill_text

    def test_documents_name_constraints(self, skill_text: str) -> None:
        assert "1-64" in skill_text
        assert "lowercase" in skill_text
        assert "consecutive hyphens" in skill_text

    def test_documents_description_limit(self, skill_text: str) -> None:
        assert "1-1024" in skill_text

    def test_documents_metadata_fields(self, skill_text: str) -> None:
        assert "metadata" in skill_text.lower()
        assert "author" in skill_text
        assert "version" in skill_text

    def test_documents_license_field(self, skill_text: str) -> None:
        assert "license" in skill_text.lower()


# ---------------------------------------------------------------------------
# owb validate reference
# ---------------------------------------------------------------------------


class TestOwbValidateReference:
    def test_references_owb_validate(self, skill_text: str) -> None:
        assert "owb validate" in skill_text

    def test_validate_in_iteration_step(self, skill_text: str) -> None:
        """owb validate should appear in the iteration/testing step."""
        iterate_idx = skill_text.index("Iterate")
        after_iterate = skill_text[iterate_idx:]
        assert "owb validate" in after_iterate


# ---------------------------------------------------------------------------
# No plugin-specific content
# ---------------------------------------------------------------------------


class TestNoPluginContent:
    def test_no_plugin_dir_flag(self, skill_text: str) -> None:
        assert "--plugin-dir" not in skill_text

    def test_no_plugin_json(self, skill_text: str) -> None:
        assert "plugin.json" not in skill_text

    def test_no_plugin_dev_reference(self, skill_text: str) -> None:
        assert "plugin-dev" not in skill_text

    def test_no_init_skill_script(self, skill_text: str) -> None:
        assert "init_skill.py" not in skill_text

    def test_no_package_skill_script(self, skill_text: str) -> None:
        assert "package_skill.py" not in skill_text


# ---------------------------------------------------------------------------
# Integration: passes OWB spec validation
# ---------------------------------------------------------------------------


class TestSpecValidation:
    def test_passes_spec_validation(self) -> None:
        from open_workspace_builder.evaluator.spec_validator import validate_skill

        result = validate_skill(str(SKILL_DIR))
        assert result.valid, f"Spec validation failed: {result.errors}"
