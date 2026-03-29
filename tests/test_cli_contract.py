"""CLI contract verification test.

Mandatory per integration-verification-policy §4. Asserts every documented
CLI command exists and responds to --help with exit code 0.

This test must be updated whenever new commands are added to the CLI.
"""

from __future__ import annotations

import pytest
from click.testing import CliRunner

from open_workspace_builder.cli import owb

# ── Complete command tree ────────────────────────────────────────────────
# Each entry is a list of CLI tokens that should resolve to a valid command.

TOP_LEVEL_COMMANDS = [
    ["init"],
    ["diff"],
    ["migrate"],
    ["update"],
    ["validate"],
]

GROUP_COMMANDS = [
    ["ecc"],
    ["security"],
    ["auth"],
    ["audit"],
    ["context"],
    ["metrics"],
    ["stage"],
    ["mcp"],
]

SUBCOMMANDS = [
    # ecc
    ["ecc", "update"],
    ["ecc", "status"],
    # security
    ["security", "scan"],
    ["security", "sast"],
    # auth
    ["auth", "store-key"],
    ["auth", "get-key"],
    ["auth", "status"],
    ["auth", "backends"],
    # audit
    ["audit", "deps"],
    ["audit", "package"],
    ["audit", "check-suppressions"],
    ["audit", "licenses"],
    # context
    ["context", "migrate"],
    ["context", "status"],
    # metrics
    ["metrics", "tokens"],
    ["metrics", "export"],
    ["metrics", "record"],
    ["metrics", "forecast"],
    ["metrics", "budget-check"],
    ["metrics", "sync"],
    ["metrics", "by-story"],
    # stage
    ["stage", "status"],
    ["stage", "promote"],
    # mcp
    ["mcp", "serve"],
]

ALL_COMMANDS = TOP_LEVEL_COMMANDS + GROUP_COMMANDS + SUBCOMMANDS


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ── Contract tests ───────────────────────────────────────────────────────


class TestCliContract:
    """Every registered command responds to --help with exit code 0."""

    @pytest.mark.parametrize("cmd_tokens", ALL_COMMANDS, ids=[" ".join(c) for c in ALL_COMMANDS])
    def test_command_responds_to_help(self, runner: CliRunner, cmd_tokens: list[str]) -> None:
        result = runner.invoke(owb, [*cmd_tokens, "--help"])
        assert result.exit_code == 0, (
            f"'owb {' '.join(cmd_tokens)} --help' failed with exit code {result.exit_code}.\n"
            f"Output:\n{result.output}"
        )

    def test_root_group_responds_to_help(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["--help"])
        assert result.exit_code == 0

    def test_root_group_lists_all_top_level_entries(self, runner: CliRunner) -> None:
        """The root --help output must mention every top-level command and group."""
        result = runner.invoke(owb, ["--help"])
        assert result.exit_code == 0
        help_text = result.output.lower()
        expected_names = [cmd[0] for cmd in TOP_LEVEL_COMMANDS + GROUP_COMMANDS]
        missing = [name for name in expected_names if name not in help_text]
        assert not missing, f"Root --help is missing commands: {missing}"

    def test_version_flag(self, runner: CliRunner) -> None:
        result = runner.invoke(owb, ["--version"])
        assert result.exit_code == 0
        assert "version" in result.output.lower()
