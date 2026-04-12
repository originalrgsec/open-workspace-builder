"""Tests for OWB-S126: Conventional Commit Hook.

Tests the commit-msg-check.py script's validation logic.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

# Load the script module despite its hyphenated filename.
_script_path = Path(__file__).resolve().parent.parent / "scripts" / "commit-msg-check.py"
_spec = importlib.util.spec_from_file_location("commit_msg_check", _script_path)
assert _spec is not None and _spec.loader is not None
_mod = importlib.util.module_from_spec(_spec)
sys.modules["commit_msg_check"] = _mod
_spec.loader.exec_module(_mod)
validate_commit_message = _mod.validate_commit_message


class TestValidMessages:
    """AC-2: Valid messages pass."""

    @pytest.mark.parametrize(
        "msg",
        [
            "feat: add new SBOM command",
            "fix: resolve SBOM drift on SSH alias",
            "refactor: extract normalization module",
            "docs: update howto for SBOM verify",
            "test: add workflow-level AC tests",
            "chore: bump ruff to v0.11.4",
            "perf: cache component discovery results",
            "ci: add coverage gate to workflow",
        ],
        ids=lambda m: m.split(":")[0],
    )
    def test_valid_types(self, msg: str) -> None:
        is_valid, error = validate_commit_message(msg)
        assert is_valid, f"Should accept valid message: {error}"

    def test_message_with_body(self) -> None:
        msg = "feat: add SBOM verify command\n\nThis adds the verify subcommand."
        is_valid, _ = validate_commit_message(msg)
        assert is_valid

    def test_message_with_multiline_body(self) -> None:
        msg = (
            "fix: normalize SSH host aliases in SBOM provenance\n"
            "\n"
            "Collapse SSH host aliases (github.com-personal → github.com)\n"
            "to prevent SBOM drift between local and CI environments."
        )
        is_valid, _ = validate_commit_message(msg)
        assert is_valid


class TestInvalidMessages:
    """AC-1: Invalid messages are rejected."""

    def test_no_type(self) -> None:
        is_valid, error = validate_commit_message("fixed the bug")
        assert not is_valid
        assert "Expected" in error

    def test_unknown_type(self) -> None:
        is_valid, error = validate_commit_message("bugfix: fix the thing")
        assert not is_valid
        assert "Unknown commit type" in error

    def test_missing_colon_space(self) -> None:
        is_valid, error = validate_commit_message("feat add new feature")
        assert not is_valid

    def test_empty_message(self) -> None:
        is_valid, error = validate_commit_message("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_only_whitespace(self) -> None:
        is_valid, error = validate_commit_message("   \n\n  ")
        assert not is_valid


class TestExemptions:
    """EC-1 and EC-2: Merge and revert commits are exempted."""

    def test_merge_commit(self) -> None:
        is_valid, _ = validate_commit_message("Merge branch 'feature' into main")
        assert is_valid

    def test_merge_pull_request(self) -> None:
        is_valid, _ = validate_commit_message("Merge pull request #42 from user/branch")
        assert is_valid

    def test_revert_commit(self) -> None:
        is_valid, _ = validate_commit_message('Revert "feat: add SBOM command"')
        assert is_valid


class TestTrailers:
    """AC-3: Co-authored-by trailers are allowed."""

    def test_co_authored_by(self) -> None:
        msg = "feat: add dependency gate hook\n\nCo-Authored-By: Claude <noreply@anthropic.com>"
        is_valid, _ = validate_commit_message(msg)
        assert is_valid

    def test_signed_off_by(self) -> None:
        msg = "fix: resolve drift\n\nSigned-off-by: Developer <dev@example.com>"
        is_valid, _ = validate_commit_message(msg)
        assert is_valid


class TestVendoredCopy:
    """AC-4: Vendored hook exists for distribution."""

    def test_vendored_hook_exists(self) -> None:
        from pathlib import Path

        vendored = (
            Path(__file__).resolve().parent.parent
            / "src"
            / "open_workspace_builder"
            / "vendor"
            / "ecc"
            / "hooks"
            / "commit-msg-check.py"
        )
        assert vendored.is_file(), f"Vendored hook not found at {vendored}"
