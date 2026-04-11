#!/usr/bin/env python3
"""Extract a single version section from a Keep-a-Changelog CHANGELOG.md.

Used by the GitHub Releases workflow (AD-17) to source the Release body
from the CHANGELOG section matching the tag being released.

Usage:
    python scripts/extract_changelog.py <changelog_path> <version>

Example:
    python scripts/extract_changelog.py CHANGELOG.md 1.9.0

The version argument must match the section header exactly (without the
leading "v" used in git tags). Pre-release versions (e.g. 1.9.0-rc.1)
must have their own matching section; there is no implicit fallback to
[Unreleased]. Fail-loud-on-missing is intentional per AD-17 consequences:
a release must not proceed with an empty or wrong Release body.

Exit codes:
    0 — section found and written to stdout
    1 — section missing, empty, or arguments invalid
"""

from __future__ import annotations

import re
import sys
from pathlib import Path


SECTION_HEADER = re.compile(r"^##\s+\[([^\]]+)\](?:\s+-\s+.+)?\s*$")


def extract_section(changelog_text: str, version: str) -> str:
    """Return the body of the `## [version]` section, without the header.

    Raises ValueError if the section is missing or empty.
    """
    lines = changelog_text.splitlines()
    start_idx: int | None = None
    for idx, line in enumerate(lines):
        match = SECTION_HEADER.match(line)
        if match and match.group(1) == version:
            start_idx = idx + 1
            break
    if start_idx is None:
        raise ValueError(f"CHANGELOG section [{version}] not found")

    body_lines: list[str] = []
    for line in lines[start_idx:]:
        if SECTION_HEADER.match(line):
            break
        body_lines.append(line)

    first = next((i for i, line in enumerate(body_lines) if line.strip()), None)
    if first is None:
        raise ValueError(f"CHANGELOG section [{version}] is empty")
    last = len(body_lines) - next(i for i, line in enumerate(reversed(body_lines)) if line.strip())
    trimmed = body_lines[first:last]

    return "\n".join(trimmed) + "\n"


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(
            "usage: extract_changelog.py <changelog_path> <version>",
            file=sys.stderr,
        )
        return 1

    changelog_path = Path(argv[1])
    version = argv[2]

    if not changelog_path.is_file():
        print(f"error: changelog not found: {changelog_path}", file=sys.stderr)
        return 1

    try:
        body = extract_section(changelog_path.read_text(encoding="utf-8"), version)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    sys.stdout.write(body)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
