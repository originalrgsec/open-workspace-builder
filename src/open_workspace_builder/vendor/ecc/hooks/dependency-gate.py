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
import shlex
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
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

# --- Install command parsing (OWB-S133) ---
#
# The parser uses shlex.split for shell-aware tokenization, then walks the
# token stream to find install subcommand prefixes and collect package
# tokens up to the first shell operator (|, &&, ;, >, 2>&1, etc.).
#
# Why not regex-on-the-whole-string? Because regex greedily captures
# trailing shell operators and emits them as bogus package names
# (Sprint 29 regression: `uv pip install pkg 2>&1 | tail` yielded `2`
# and `|` as packages).
#
# uv sync / uv lock: explicitly out of scope. Those commands move the
# installed set to match the existing lock; packages were already gated
# when added. Gating sync/lock would re-check approved packages on every
# environment refresh, which is noisy without improving safety.

# (ecosystem, token_prefix) — the verb sequence that signals an install.
INSTALL_VERBS: list[tuple[str, tuple[str, ...]]] = [
    ("python", ("uv", "pip", "install")),
    ("python", ("uv", "add")),
    ("python", ("pip", "install")),
    ("python", ("pip3", "install")),
    ("python", ("python", "-m", "pip", "install")),
    ("python", ("python3", "-m", "pip", "install")),
    ("node", ("npm", "install")),
    ("node", ("npm", "i")),
    ("node", ("yarn", "add")),
    ("node", ("pnpm", "add")),
    ("rust", ("cargo", "add")),
    ("go", ("go", "get")),
    ("brew", ("brew", "install")),
]

# Tokens that terminate parsing — anything after these is a different
# command or a redirection, not packages being installed.
SHELL_TERMINATORS: frozenset[str] = frozenset(
    {
        "|",
        "||",
        "&&",
        "&",
        ";",
        ">",
        ">>",
        "<",
        "<<",
        "<<<",
        "2>",
        "2>>",
        "&>",
        "&>>",
        ">&",
        "2>&1",
        ">&2",
        "1>&2",
    }
)

# Flags that take a value argument (the next token is the value, not a package).
FLAGS_WITH_VALUE: frozenset[str] = frozenset(
    {
        "-r",
        "--requirement",
        "-c",
        "--constraint",
        "-i",
        "--index-url",
        "--extra-index-url",
        "-f",
        "--find-links",
        "--target",
        "-t",
        "--prefix",
        "--root",
        "--python",
        "-p",
        "--index",
    }
)

# Exact-pin extractor: captures the version string from `pkg==X.Y.Z`.
# Intentionally only matches the `==` operator; range/compat specs
# (>=, <=, ~=, !=) produce pinned_version=None per AC-3.
_EXACT_PIN_RE = re.compile(r"^([A-Za-z0-9_.\-]+)(?:\[[^\]]+\])?==([A-Za-z0-9_.\-+]+)$")
# Name-only extractor: first A-Za-z chunk (may contain _, ., -).
_NAME_RE = re.compile(r"^([A-Za-z0-9_.\-]+)")


@dataclass(frozen=True)
class PackageSpec:
    """A single package referenced by an install command.

    Attributes:
        ecosystem: "python", "node", "rust", "go", or "brew".
        name: Package name as it should be queried against the registry.
        pinned_version: Exact version if the token used ``==X.Y.Z``, else
            ``None``. Range specifiers (``>=``, ``<=``, ``~=``, ``!=``)
            produce ``None`` because the installed version cannot be
            determined from the token alone.
    """

    ecosystem: str
    name: str
    pinned_version: str | None = None


def _is_shell_terminator(token: str) -> bool:
    """True if the token ends one shell command and begins another."""
    if token in SHELL_TERMINATORS:
        return True
    # Redirection tokens like `2>file`, `>out.log` — start with > or end with >.
    if token.startswith((">", "<", "2>", "&>")):
        return True
    return False


def _is_skippable(token: str) -> bool:
    """True if the token is not a package name (flag, path, URL, etc.)."""
    if not token:
        return True
    # Flags.
    if token.startswith("-"):
        return True
    # Paths.
    if token in (".", "..") or token.startswith(("/", "./", "../")):
        return True
    # VCS or URL refs.
    if token.startswith(("git+", "hg+", "svn+", "bzr+", "http://", "https://", "file://")):
        return True
    # Command substitution — cannot parse safely.
    if token.startswith(("$(", "${", "`")) or token.endswith("`") or token.endswith(")"):
        return True
    # Environment variable assignment.
    if "=" in token and not _looks_like_requirement(token):
        return True
    return False


def _looks_like_requirement(token: str) -> bool:
    """True if the token plausibly matches PEP 508 syntax (pkg==X, pkg>=X)."""
    # Any PEP 440 spec operator marks this as a requirement.
    return any(op in token for op in ("==", ">=", "<=", "~=", "!=", ">", "<"))


def _match_install_verb(tokens: list[str], start: int) -> tuple[str, int] | None:
    """Try to match an install verb starting at ``tokens[start]``.

    Returns (ecosystem, index_after_verb) on match, else None.
    """
    for ecosystem, verb in INSTALL_VERBS:
        end = start + len(verb)
        if end <= len(tokens) and tuple(tokens[start:end]) == verb:
            return ecosystem, end
    return None


def _parse_requirement(token: str) -> tuple[str, str | None] | None:
    """Parse a PEP 508-ish requirement token into (name, pinned_version).

    Returns None if the token does not look like a package requirement at
    all (e.g., it's a word like "install" that slipped through earlier
    filters).
    """
    # Drop surrounding quotes if shlex left any (defensive).
    token = token.strip().strip("'\"")
    # Strip extras: pkg[extra1,extra2] → pkg
    base = re.sub(r"\[[^\]]+\]", "", token)

    exact = _EXACT_PIN_RE.match(token)
    if exact:
        return exact.group(1), exact.group(2)

    # Range/compat specs: keep the name, drop the version.
    name_match = _NAME_RE.match(base)
    if not name_match:
        return None
    name = name_match.group(1)
    # Filter out obvious non-package words that slipped through.
    if name.lower() in {"install", "add", "get", "sync", "lock", "pip", "uv"}:
        return None
    return name, None


def extract_packages(command: str) -> list[PackageSpec]:
    """Return a list of PackageSpec parsed from a shell command string.

    Parses the command using ``shlex.split`` to respect quoting, then
    walks the token stream. For each run of tokens matching an install
    verb prefix (e.g., ``uv pip install``), collects subsequent tokens
    up to the next shell operator (``|``, ``&&``, ``>``, etc.),
    filtering out flags, paths, URLs, and substitutions.

    ``uv sync`` and ``uv lock`` are intentionally not listed in
    ``INSTALL_VERBS``; they return an empty list. See module docstring.

    Safe to call on any string: non-install commands return ``[]``.
    """
    try:
        tokens = shlex.split(command, comments=False, posix=True)
    except ValueError:
        # Unbalanced quotes or other shlex failure — refuse to guess.
        return []

    results: list[PackageSpec] = []
    i = 0
    while i < len(tokens):
        # Skip over leading tokens until we find an install verb.
        matched = _match_install_verb(tokens, i)
        if matched is None:
            i += 1
            continue
        ecosystem, i = matched

        # Collect packages until a shell terminator or end of tokens.
        skip_next = False
        while i < len(tokens):
            tok = tokens[i]
            if _is_shell_terminator(tok):
                break
            if skip_next:
                skip_next = False
                i += 1
                continue
            if tok in FLAGS_WITH_VALUE:
                skip_next = True
                i += 1
                continue
            if _is_skippable(tok):
                i += 1
                continue
            parsed = _parse_requirement(tok)
            if parsed is not None:
                name, pinned = parsed
                results.append(PackageSpec(ecosystem=ecosystem, name=name, pinned_version=pinned))
            i += 1
        # Continue outer loop in case another install verb appears after ;
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


def check_pypi(pkg_name: str, pinned_version: str | None = None) -> dict[str, Any]:
    """Check a Python package against PyPI for license and publication date.

    Args:
        pkg_name: The package name to query.
        pinned_version: If set (from ``pkg==X.Y.Z`` in the install
            command), the quarantine check uses the upload_time of
            *that* version rather than PyPI's "latest". Range specs
            (``>=``, ``<=``, ``~=``, ``!=``) pass ``None`` — the check
            falls back to latest and accepts a small rate of false
            positives rather than mis-resolving the range.
    """
    result: dict[str, Any] = {
        "package": pkg_name,
        "ecosystem": "python",
        "license": None,
        "license_allowed": False,
        "license_conditional": False,
        "quarantine_ok": True,
        "publication_date": None,
        "checked_version": None,
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

    # Quarantine check: prefer the exact pinned version when provided
    # (OWB-S133 AC-2), else fall back to the latest release on PyPI.
    releases = data.get("releases", {})
    target_version = pinned_version if pinned_version in releases else info.get("version", "")
    if pinned_version and pinned_version not in releases:
        # Operator asked for a version PyPI doesn't have — block loudly.
        result["error"] = (
            f"Package '{pkg_name}' has no release '{pinned_version}' on PyPI. "
            "Fix the pin or wait for publication."
        )
        return result
    result["checked_version"] = target_version
    version_files = releases.get(target_version, [])
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

    for spec in packages:
        ecosystem = spec.ecosystem
        pkg_name = spec.name
        # First-party exemption.
        if ecosystem == "python" and is_first_party(pkg_name, ecosystem):
            print(
                f"dependency-gate: {pkg_name} — first-party exemption, skipping checks.",
                file=sys.stderr,
            )
            continue

        if ecosystem == "python":
            result = check_pypi(pkg_name, pinned_version=spec.pinned_version)

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
