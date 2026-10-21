"""OWB-S151: sprint-close-reminder.sh hook tests.

The hook is a small bash script that inspects Claude Code PreToolUse Bash
payloads and prints a reminder when a git commit looks like a release.
These tests exercise the script as a subprocess, feeding it the same
JSON envelope Claude Code would send.
"""

from __future__ import annotations

import json
import subprocess
from pathlib import Path


HOOK_PATH = (
    Path(__file__).parent.parent.parent
    / "src"
    / "open_workspace_builder"
    / "vendor"
    / "ecc"
    / "hooks"
    / "sprint-close-reminder.sh"
)


def _run(payload: dict) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["bash", str(HOOK_PATH)],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )


def test_hook_is_executable_script() -> None:
    assert HOOK_PATH.exists()
    assert HOOK_PATH.read_text().startswith("#!/usr/bin/env bash")


def test_empty_payload_exits_clean() -> None:
    result = subprocess.run(
        ["bash", str(HOOK_PATH)],
        input="",
        capture_output=True,
        text=True,
        check=False,
        timeout=5,
    )
    assert result.returncode == 0
    assert result.stdout == ""


def test_non_git_command_silent() -> None:
    result = _run({"tool_name": "Bash", "tool_input": {"command": "ls -la"}})
    assert result.returncode == 0
    assert result.stdout == ""


def test_git_log_silent() -> None:
    result = _run({"tool_name": "Bash", "tool_input": {"command": "git log --oneline"}})
    assert result.returncode == 0
    assert result.stdout == ""


def test_git_commit_with_version_in_message_warns() -> None:
    result = _run(
        {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "chore: bump to v1.5.0"'},
        }
    )
    assert result.returncode == 0
    assert "sprint-close" in result.stdout.lower()


def test_git_commit_with_release_keyword_warns() -> None:
    result = _run(
        {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "feat: release stage"'},
        }
    )
    assert result.returncode == 0
    assert "sprint-close" in result.stdout.lower()


def test_git_commit_with_chore_version_warns() -> None:
    result = _run(
        {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "chore(version): sync"'},
        }
    )
    assert result.returncode == 0
    assert "sprint-close" in result.stdout.lower()


def test_plain_git_commit_silent() -> None:
    result = _run(
        {
            "tool_name": "Bash",
            "tool_input": {"command": 'git commit -m "fix: off-by-one in pagination"'},
        }
    )
    assert result.returncode == 0
    assert result.stdout == ""
