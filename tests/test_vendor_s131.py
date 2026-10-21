"""Tests for OWB-S131: Distribute Context Window Diet Changes.

Verifies that vendored content reflects Sprint 26-27 optimizations and
contains no PII or personal references.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

VENDOR_ROOT = (
    Path(__file__).resolve().parent.parent / "src" / "open_workspace_builder" / "vendor" / "ecc"
)

# --- PII patterns that must never appear in vendored content ---

PII_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("GitHub username", re.compile(r"originalrgsec", re.IGNORECASE)),
    ("GitHub org", re.compile(r"volcanixllc", re.IGNORECASE)),
    ("Company name", re.compile(r"volcanix", re.IGNORECASE)),
    ("Email", re.compile(r"info@volcanix\.io", re.IGNORECASE)),
    ("Personal path (Code)", re.compile(r"~/projects/Code/")),
    ("Personal path (PersonalCode)", re.compile(r"~/projects/PersonalCode/")),
    ("Vault path", re.compile(r"~/projects/Obsidian/")),
    ("Vault reference", re.compile(r"Obsidian/code/")),
    ("SSH alias", re.compile(r"github\.com-personal")),
    ("SSH alias", re.compile(r"github\.com-volcanix")),
    ("SSH key path", re.compile(r"id_ed25519_")),
    ("Decision record ref", re.compile(r"DRN-\d{3}")),
    ("Project name (Home-Ops)", re.compile(r"Home-Ops", re.IGNORECASE)),
    ("Project name (Sedalia)", re.compile(r"Sedalia", re.IGNORECASE)),
    ("Sprint origin narrative", re.compile(r"2026-04-11 Home-Ops")),
]


# --- AC-1: Vendored security.md reflects S128 trim ---


class TestVendoredSecurityMd:
    """AC-1: security.md contains only LLM-judgment items."""

    @pytest.fixture()
    def content(self) -> str:
        return (VENDOR_ROOT / "rules" / "common" / "security.md").read_text()

    def test_no_hardcoded_secrets_item(self, content: str) -> None:
        """Tooling-enforced item 'hardcoded secrets' should be removed."""
        assert "hardcoded secrets" not in content.lower()

    def test_no_sql_injection_item(self, content: str) -> None:
        """Tooling-enforced item 'SQL injection' should be removed."""
        assert "sql injection" not in content.lower()

    def test_no_xss_item(self, content: str) -> None:
        """Tooling-enforced item 'XSS' should be removed."""
        assert "xss" not in content.lower()

    def test_retains_input_validation(self, content: str) -> None:
        """LLM-judgment item 'user inputs validated' should remain."""
        assert "user inputs validated" in content.lower()

    def test_retains_csrf(self, content: str) -> None:
        assert "csrf" in content.lower()

    def test_retains_auth(self, content: str) -> None:
        assert "authentication/authorization" in content.lower()

    def test_retains_rate_limiting(self, content: str) -> None:
        assert "rate limiting" in content.lower()

    def test_retains_error_messages(self, content: str) -> None:
        assert "error messages" in content.lower()

    def test_tooling_enforcement_note(self, content: str) -> None:
        """Should include a note that tooling-enforced items are omitted."""
        assert "pre-commit" in content.lower() or "tooling" in content.lower()


# --- AC-2: Vendored performance.md reflects S129 model update ---


class TestVendoredPerformanceMd:
    """AC-2: performance.md has correct model references."""

    @pytest.fixture()
    def content(self) -> str:
        return (VENDOR_ROOT / "rules" / "common" / "performance.md").read_text()

    def test_opus_4_6(self, content: str) -> None:
        """Opus should reference 4.6, not 4.5."""
        assert "Opus 4.6" in content
        assert "Opus 4.5" not in content

    def test_sonnet_4_6(self, content: str) -> None:
        assert "Sonnet 4.6" in content

    def test_haiku_4_5(self, content: str) -> None:
        """Haiku remains at 4.5 (correct current version)."""
        assert "Haiku 4.5" in content


# --- AC-3: Dependency gate hook distributed ---


class TestDependencyGateHook:
    """AC-3: dependency-gate.py exists and is genericized."""

    @pytest.fixture()
    def content(self) -> str:
        return (VENDOR_ROOT / "hooks" / "dependency-gate.py").read_text()

    def test_hook_exists(self) -> None:
        assert (VENDOR_ROOT / "hooks" / "dependency-gate.py").is_file()

    def test_intercepts_uv_add(self, content: str) -> None:
        assert "uv" in content and "add" in content

    def test_intercepts_pip_install(self, content: str) -> None:
        assert "pip" in content and "install" in content

    def test_intercepts_npm_install(self, content: str) -> None:
        assert "npm" in content

    def test_intercepts_cargo_add(self, content: str) -> None:
        assert "cargo" in content

    def test_intercepts_go_get(self, content: str) -> None:
        assert "go" in content and "get" in content

    def test_first_party_owners_empty(self, content: str) -> None:
        """First-party owners should be commented out placeholders."""
        # The frozenset should be empty (only comments inside).
        assert "FIRST_PARTY_OWNERS: frozenset[str] = frozenset(" in content
        # Should not contain actual usernames.
        assert "originalrgsec" not in content
        assert "volcanixllc" not in content

    def test_install_instructions(self, content: str) -> None:
        """Should include installation instructions for Claude Code."""
        assert "settings.json" in content or "PreToolUse" in content


# --- AC-4: Sprint-workflow rule distributed ---


class TestSprintWorkflowRule:
    """AC-4: sprint-workflow.md exists and is genericized."""

    @pytest.fixture()
    def content(self) -> str:
        return (VENDOR_ROOT / "rules" / "common" / "sprint-workflow.md").read_text()

    def test_rule_exists(self) -> None:
        assert (VENDOR_ROOT / "rules" / "common" / "sprint-workflow.md").is_file()

    def test_optional_header(self, content: str) -> None:
        """Should note that the rule is optional."""
        assert "optional" in content.lower()

    def test_execution_contract(self, content: str) -> None:
        """Should preserve the execution phase contract."""
        assert "execution phase contract" in content.lower()

    def test_gated_actions(self, content: str) -> None:
        """Should list actions that remain gated.

        The v1.18.0 refresh restructures the gated list around destructive /
        cross-account operations only. Tag creation moved to default-yes
        under the Git Ops Ownership model, but the hard-floor rules
        remain: never force-push, never cross an account boundary.
        """
        lowered = content.lower()
        assert "push --force" in lowered or "force push" in lowered
        assert "cross-account" in lowered or "account boundary" in lowered

    def test_default_yes_actions(self, content: str) -> None:
        """Should list default-yes actions."""
        assert "default-yes" in content.lower()


# --- AC-5: PII/secrets scrub ---


class TestVendorPiiScrub:
    """AC-5: No PII or personal references in any vendored file."""

    @pytest.fixture()
    def all_vendored_files(self) -> list[tuple[Path, str]]:
        """Read all files modified/added in S131."""
        files = [
            VENDOR_ROOT / "rules" / "common" / "security.md",
            VENDOR_ROOT / "rules" / "common" / "performance.md",
            VENDOR_ROOT / "hooks" / "dependency-gate.py",
            VENDOR_ROOT / "rules" / "common" / "sprint-workflow.md",
        ]
        return [(f, f.read_text()) for f in files]

    @pytest.mark.parametrize(
        "label,pattern",
        [(label, pat) for label, pat in PII_PATTERNS],
        ids=[label for label, _ in PII_PATTERNS],
    )
    def test_no_pii(
        self,
        all_vendored_files: list[tuple[Path, str]],
        label: str,
        pattern: re.Pattern[str],
    ) -> None:
        for filepath, content in all_vendored_files:
            match = pattern.search(content)
            assert match is None, f"PII found ({label}): '{match.group()}' in {filepath.name}"
