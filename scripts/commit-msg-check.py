#!/usr/bin/env python3
"""
commit-msg-check.py — Conventional commit message validator.

Validates that the first line of a commit message follows the format:
    <type>: <description>

Allowed types: feat, fix, refactor, docs, test, chore, perf, ci

Merge commits and revert commits are exempted.
Co-Authored-By and other trailers are allowed.

Usage as a pre-commit hook (commit-msg stage):
    - repo: local
      hooks:
        - id: commit-msg-check
          name: conventional commit message
          entry: python3 scripts/commit-msg-check.py
          language: python
          stages: [commit-msg]
          always_run: true
"""

from __future__ import annotations

import re
import sys

ALLOWED_TYPES = frozenset({"feat", "fix", "refactor", "docs", "test", "chore", "perf", "ci"})

# First line must match: type: description (at least one char after colon+space).
COMMIT_MSG_PATTERN = re.compile(r"^(\w+): .+")

# Exemptions: merge commits and revert commits.
MERGE_PREFIX = "Merge "
REVERT_PREFIX = 'Revert "'


def validate_commit_message(message: str) -> tuple[bool, str]:
    """Validate a commit message. Returns (is_valid, error_message)."""
    first_line = message.split("\n", 1)[0].strip()

    if not first_line:
        return False, "Commit message is empty."

    # Exemptions.
    if first_line.startswith(MERGE_PREFIX):
        return True, ""
    if first_line.startswith(REVERT_PREFIX):
        return True, ""

    match = COMMIT_MSG_PATTERN.match(first_line)
    if not match:
        types_str = ", ".join(sorted(ALLOWED_TYPES))
        return False, (
            f"Invalid commit message format.\n"
            f"  Got:      {first_line}\n"
            f"  Expected: <type>: <description>\n"
            f"  Types:    {types_str}"
        )

    commit_type = match.group(1)
    if commit_type not in ALLOWED_TYPES:
        types_str = ", ".join(sorted(ALLOWED_TYPES))
        return False, (f"Unknown commit type '{commit_type}'.\n  Allowed: {types_str}")

    return True, ""


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: commit-msg-check.py <commit-msg-file>", file=sys.stderr)
        return 1

    msg_file = sys.argv[1]
    try:
        with open(msg_file) as f:
            message = f.read()
    except OSError as e:
        print(f"Cannot read commit message file: {e}", file=sys.stderr)
        return 1

    is_valid, error = validate_commit_message(message)
    if not is_valid:
        print(f"commit-msg-check: {error}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
