#!/usr/bin/env python3
"""
dependency-gate.py — Claude Code PreToolUse hook

Enforces the dependency pre-install gate before any package install command.
Checks license against allowed-licenses policy and verifies the 7-day
supply-chain quarantine window.

Designed for Claude Code's PreToolUse hook system. The hook logic (license
check, quarantine enforcement) is assistant-agnostic; only the trigger
mechanism and JSON response format are Claude Code-specific. Adapt the
stdin/stdout protocol for other assistants.

Install: Add to your Claude Code settings.json under hooks.PreToolUse:

    {
      "hooks": {
        "PreToolUse": [
          {
            "matcher": "Bash",
            "command": "python3 /path/to/dependency-gate.py"
          }
        ]
      }
    }

Exit behavior:
  - Exit 0 with JSON {"hookSpecificOutput": {"permissionDecision": "deny", ...}}
    to block disallowed packages.
  - Exit 0 with no output (or "allow") to let the command proceed.
  - Non-install commands pass through immediately.
"""

from __future__ import annotations

import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import Any

# --- Configuration ---
# Customize these for your project.

QUARANTINE_DAYS = 7

# Licenses allowed without conditions (normalized to lowercase for comparison).
# Based on common permissive licenses. Edit to match your project's policy.
ALLOWED_LICENSES: frozenset[str] = frozenset(
    {
        "mit",
        "mit license",
        "apache-2.0",
        "apache 2.0",
        "apache license 2.0",
        "apache software license",
        "apache software license 2.0",
        "bsd-2-clause",
        "bsd 2-clause",
        "bsd-3-clause",
        "bsd 3-clause",
        "bsd license",
        "isc",
        "isc license",
        "cc0-1.0",
        "cc0",
        "public domain",
        "unlicense",
        "the unlicense",
        "0bsd",
        "psf-2.0",
        "python software foundation license",
        "python software foundation",
        "cnri-python",
        "zlib",
        "zlib license",
        "zlib/libpng",
    }
)

# Licenses allowed with conditions (still permitted, just flagged).
CONDITIONAL_LICENSES: frozenset[str] = frozenset(
    {
        "mpl-2.0",
        "mozilla public license 2.0",
        "bsl-1.0",
        "artistic-2.0",
        "artistic license 2.0",
    }
)

# First-party GitHub orgs/users whose packages skip all checks (lowercase).
# Add your own GitHub username or org here.
FIRST_PARTY_OWNERS: frozenset[str] = frozenset(
    {
        # "your-github-org",
        # "your-github-username",
    }
)

# --- Install command patterns ---

# Each pattern captures (package_names_string) from the command.
# We handle multi-package commands by splitting the captured group.
INSTALL_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    (
        "python",
        re.compile(
            r"(?:uv\s+add|uv\s+pip\s+install|pip\s+install)\s+(.+)",
            re.IGNORECASE,
        ),
    ),
    (
        "node",
        re.compile(
            r"npm\s+install\s+(.+)",
            re.IGNORECASE,
        ),
    ),
    (
        "rust",
        re.compile(
            r"cargo\s+add\s+(.+)",
            re.IGNORECASE,
        ),
    ),
    (
        "go",
        re.compile(
            r"go\s+get\s+(.+)",
            re.IGNORECASE,
        ),
    ),
    (
        "brew",
        re.compile(
            r"brew\s+install\s+(.+)",
            re.IGNORECASE,
        ),
    ),
]

# Flags and options to strip from the package name string.
FLAG_PATTERN = re.compile(r"(?:^|\s)--?\S+")

# Version specifiers to strip (e.g., pkg>=1.0, pkg[extra]).
VERSION_SPEC = re.compile(r"[>=<!~\[].+$")


def extract_packages(command: str) -> list[tuple[str, str]]:
    """Return list of (ecosystem, package_name) from a command string."""
    results: list[tuple[str, str]] = []
    for ecosystem, pattern in INSTALL_PATTERNS:
        match = pattern.search(command)
        if not match:
            continue
        raw = match.group(1)
        # Strip flags (e.g., --dev, -e, --no-deps).
        cleaned = FLAG_PATTERN.sub(" ", raw).strip()
        for token in cleaned.split():
            if not token or token.startswith("-"):
                continue
            # Strip version specifiers and extras.
            pkg_name = VERSION_SPEC.sub("", token).strip()
            if pkg_name and not pkg_name.startswith("/"):
                results.append((ecosystem, pkg_name))
    return results


def is_first_party(pkg_name: str, ecosystem: str) -> bool:
    """Check if a package is first-party by querying PyPI for the home page."""
    if ecosystem != "python":
        return False
    if not FIRST_PARTY_OWNERS:
        return False
    try:
        url = f"https://pypi.org/pypi/{pkg_name}/json"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
        info = data.get("info", {})
        # Check project URLs for first-party owners.
        home_page = (info.get("home_page") or "").lower()
        project_urls = info.get("project_urls") or {}
        all_urls = [home_page] + [v.lower() for v in project_urls.values()]
        for url_str in all_urls:
            for owner in FIRST_PARTY_OWNERS:
                if f"github.com/{owner}" in url_str:
                    return True
    except (urllib.error.URLError, json.JSONDecodeError, OSError):
        pass
    return False


def check_pypi(pkg_name: str) -> dict[str, Any]:
    """Check a Python package against PyPI for license and publication date."""
    result: dict[str, Any] = {
        "package": pkg_name,
        "ecosystem": "python",
        "license": None,
        "license_allowed": False,
        "license_conditional": False,
        "quarantine_ok": True,
        "publication_date": None,
        "error": None,
    }
    try:
        url = f"https://pypi.org/pypi/{pkg_name}/json"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            result["error"] = f"Package '{pkg_name}' not found on PyPI."
        else:
            result["error"] = f"PyPI returned HTTP {e.code} for '{pkg_name}'."
        return result
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        result["error"] = f"Failed to reach PyPI: {e}"
        return result

    info = data.get("info", {})

    # License detection: prefer the license field, fall back to classifiers.
    license_raw = (info.get("license") or "").strip()
    if not license_raw or license_raw.lower() in ("unknown", ""):
        classifiers = info.get("classifiers") or []
        for c in classifiers:
            if c.startswith("License :: OSI Approved :: "):
                license_raw = c.split(" :: ")[-1]
                break
            if c.startswith("License :: "):
                license_raw = c.split(" :: ")[-1]
                break

    result["license"] = license_raw
    license_lower = license_raw.lower().strip()

    if any(allowed in license_lower or license_lower in allowed for allowed in ALLOWED_LICENSES):
        result["license_allowed"] = True
    elif any(cond in license_lower or license_lower in cond for cond in CONDITIONAL_LICENSES):
        result["license_allowed"] = True
        result["license_conditional"] = True

    # Quarantine check: find the latest release upload_time.
    releases = data.get("releases", {})
    latest_version = info.get("version", "")
    version_files = releases.get(latest_version, [])
    if version_files:
        upload_time_str = version_files[0].get("upload_time_iso_8601")
        if upload_time_str:
            try:
                upload_dt = datetime.fromisoformat(upload_time_str.replace("Z", "+00:00"))
                result["publication_date"] = upload_time_str
                days_old = (datetime.now(timezone.utc) - upload_dt).days
                if days_old < QUARANTINE_DAYS:
                    result["quarantine_ok"] = False
            except (ValueError, TypeError):
                pass

    return result


def deny(reason: str) -> dict[str, Any]:
    """Build a deny response."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def allow() -> dict[str, Any]:
    """Build an allow response."""
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
        }
    }


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    tool_name = payload.get("tool_name", "")
    if tool_name != "Bash":
        return 0

    tool_input = payload.get("tool_input", {}) or {}
    command = tool_input.get("command", "")
    if not command:
        return 0

    packages = extract_packages(command)
    if not packages:
        # Not an install command; pass through.
        return 0

    issues: list[str] = []

    for ecosystem, pkg_name in packages:
        # First-party exemption.
        if ecosystem == "python" and is_first_party(pkg_name, ecosystem):
            print(
                f"dependency-gate: {pkg_name} — first-party exemption, skipping checks.",
                file=sys.stderr,
            )
            continue

        if ecosystem == "python":
            result = check_pypi(pkg_name)

            if result["error"]:
                issues.append(
                    f"[{pkg_name}] {result['error']} "
                    "Cannot verify license or quarantine. "
                    "Install manually after verification."
                )
                continue

            if not result["license_allowed"]:
                license_display = result["license"] or "UNKNOWN"
                issues.append(
                    f"[{pkg_name}] License '{license_display}' is not in the "
                    "allowed-licenses list. Options:\n"
                    "  1. Find a permissively-licensed alternative\n"
                    "  2. File an exception in the project's decisions/ folder\n"
                    "  3. Add the license to ALLOWED_LICENSES if your policy permits it"
                )
                continue

            if result["license_conditional"]:
                print(
                    f"dependency-gate: {pkg_name} — conditional license "
                    f"({result['license']}). Verify conditions do not apply.",
                    file=sys.stderr,
                )

            if not result["quarantine_ok"]:
                issues.append(
                    f"[{pkg_name}] Published {result['publication_date']}. "
                    f"Supply-chain quarantine requires packages to be >{QUARANTINE_DAYS} "
                    "days old before installation. Wait or pin an older version."
                )
                continue
        else:
            # Non-Python ecosystems: remind to check manually.
            # The hook cannot auto-check npm/cargo/go registries yet.
            print(
                f"dependency-gate: {pkg_name} ({ecosystem}) — automated license "
                "check not available for this ecosystem. Check manually before "
                "proceeding.",
                file=sys.stderr,
            )

    if issues:
        reason = "Dependency gate blocked this install:\n\n" + "\n\n".join(issues)
        json.dump(deny(reason), sys.stdout)
        return 0

    # All packages passed. Allow the command.
    return 0


if __name__ == "__main__":
    sys.exit(main())
