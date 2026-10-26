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
import os
import re
import shlex
import ssl
import sys
import urllib.error
import urllib.parse
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
        "apache 2.0 license",
        "apache-2.0 license",
        "apache license, version 2.0",
        "apache license version 2.0",
        "apache software license",
        "apache software license 2.0",
        "bsd-2-clause",
        "bsd 2-clause",
        "bsd-3-clause",
        "bsd 3-clause",
        "bsd license",
        "isc",
        "isc license",
        "isc license (iscl)",
        "cc0-1.0",
        "cc0",
        "public domain",
        "unlicense",
        "the unlicense",
        "the unlicense (unlicense)",
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
        "mozilla public license 2.0 (mpl 2.0)",
        "bsl-1.0",
        "artistic-2.0",
        "artistic license 2.0",
    }
)

# First-party packages that skip all checks, listed by exact registry name
# (PEP 503-normalized for Python, e.g. "my-package"). Matching is by name
# only: registry metadata such as project URLs is self-declared by whoever
# uploads a package and must never be used to grant an exemption.
FIRST_PARTY_PACKAGES: frozenset[str] = frozenset(
    {
        # "your-package-name",
    }
)

# CA bundles tried, in order, when the interpreter has no default trust
# store (e.g. python.org macOS builds before "Install Certificates" runs).
_FALLBACK_CA_BUNDLES: tuple[str, ...] = (
    "/etc/ssl/cert.pem",
    "/etc/ssl/certs/ca-certificates.crt",
    "/etc/pki/tls/certs/ca-bundle.crt",
)

REGISTRY_TIMEOUT_SECONDS = 10

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
    ("python", ("uv", "tool", "install")),
    ("python", ("pipx", "install")),
    ("node", ("npm", "install")),
    ("node", ("npm", "i")),
    ("node", ("npm", "add")),
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


# npm exact version: 1.2.3 or 1.2.3-pre.1 (optionally with a leading "=").
_NPM_EXACT_RE = re.compile(r"^=?(\d+\.\d+\.\d+(?:-[0-9A-Za-z.\-]+)?)$")
# npm package name, optionally scoped.
_NPM_NAME_RE = re.compile(r"^(@[a-z0-9][a-z0-9._\-]*/)?[a-z0-9][a-z0-9._\-]*$")


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


def _parse_npm_spec(token: str) -> tuple[str, str | None] | None:
    """Parse an npm install token into (name, version_or_tag_or_None).

    Handles ``name``, ``name@1.2.3``, ``name@^1``, ``name@next`` and the
    scoped forms ``@scope/name`` / ``@scope/name@1.2.3``. Returns None for
    tokens that are not registry packages (git/file/alias specs, GitHub
    ``user/repo`` shorthand).
    """
    token = token.strip().strip("'\"")
    if not token or ":" in token:
        return None
    if token.startswith("@"):
        at = token.find("@", 1)
    else:
        at = token.find("@")
    name, spec = (token, None) if at == -1 else (token[:at], token[at + 1 :] or None)
    if not _NPM_NAME_RE.match(name.lower()):
        return None
    return name, spec


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
            if ecosystem == "node":
                parsed = _parse_npm_spec(tok)
            else:
                parsed = _parse_requirement(tok)
            if parsed is not None:
                name, pinned = parsed
                results.append(PackageSpec(ecosystem=ecosystem, name=name, pinned_version=pinned))
            i += 1
        # Continue outer loop in case another install verb appears after ;
    return results


def _normalize_name(pkg_name: str, ecosystem: str) -> str:
    if ecosystem == "python":
        return re.sub(r"[-_.]+", "-", pkg_name).lower()
    return pkg_name.lower()


def is_first_party(pkg_name: str, ecosystem: str) -> bool:
    """True if the package is listed by exact name in FIRST_PARTY_PACKAGES."""
    normalized = {_normalize_name(p, ecosystem) for p in FIRST_PARTY_PACKAGES}
    return _normalize_name(pkg_name, ecosystem) in normalized


def _ssl_context() -> ssl.SSLContext:
    """Default TLS context, with a CA fallback for interpreters lacking one.

    Verification is never disabled; when no trust store can be found the
    request fails and the gate denies the install.
    """
    ctx = ssl.create_default_context()
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return ctx
    if ctx.cert_store_stats().get("x509_ca", 0) > 0:
        return ctx
    try:
        import certifi  # type: ignore[import-not-found]

        ctx.load_verify_locations(certifi.where())
        return ctx
    except ImportError:
        pass
    for bundle in _FALLBACK_CA_BUNDLES:
        if os.path.isfile(bundle):
            ctx.load_verify_locations(bundle)
            break
    return ctx


def _fetch_json(url: str) -> Any:
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(  # noqa: S310 - fixed https registry URLs
        req, timeout=REGISTRY_TIMEOUT_SECONDS, context=_ssl_context()
    ) as resp:
        return json.loads(resp.read())


def evaluate_license(expression: str | None) -> tuple[bool, bool]:
    """Evaluate a license string or SPDX expression against policy.

    Returns ``(allowed, conditional)``. Every term is compared by exact
    (case-insensitive) match against ALLOWED_LICENSES / CONDITIONAL_LICENSES;
    substring matching is deliberately avoided because it lets arbitrary
    strings (including the empty string) satisfy the check. ``A OR B``
    passes if any alternative passes; ``A AND B`` requires every term.
    Missing or unrecognized licenses are not allowed.
    """
    if not expression:
        return False, False
    text = expression.strip().lower()
    if not text or text in ("unknown", "none", "unlicensed", "see license", "see license file"):
        return False, False
    # Whole-string match first: classifier names contain parentheses,
    # e.g. "ISC License (ISCL)", which expression parsing would split.
    if text in ALLOWED_LICENSES:
        return True, False
    if text in CONDITIONAL_LICENSES:
        return True, True
    text = text.replace("(", " ").replace(")", " ")
    best: tuple[bool, bool] = (False, False)
    for alternative in re.split(r"\s+or\s+|\s*/\s*", text):
        terms = [t.strip() for t in re.split(r"\s+and\s+", alternative) if t.strip()]
        if not terms:
            continue
        conditional = False
        ok = True
        for term in terms:
            term = re.sub(r"\s+", " ", term)
            if term in ALLOWED_LICENSES:
                continue
            if term in CONDITIONAL_LICENSES:
                conditional = True
                continue
            ok = False
            break
        if ok:
            if not conditional:
                return True, False
            best = (True, True)
    return best


def _pypi_license(info: dict[str, Any]) -> str:
    """Pick the most authoritative license declaration from PyPI metadata."""
    expression = (info.get("license_expression") or "").strip()
    if expression:
        return expression
    classifiers = [
        c.split(" :: ")[-1]
        for c in (info.get("classifiers") or [])
        if c.startswith("License :: ") and c.count(" :: ") >= 2
    ]
    if classifiers:
        return " OR ".join(classifiers)
    raw = (info.get("license") or "").strip()
    # Some packages paste the full license text; its first line is the name.
    return raw.splitlines()[0].strip() if raw else ""


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
        data = _fetch_json(f"https://pypi.org/pypi/{urllib.parse.quote(pkg_name)}/json")
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

    license_raw = _pypi_license(info)
    result["license"] = license_raw
    result["license_allowed"], result["license_conditional"] = evaluate_license(license_raw)

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
    upload_times = [f.get("upload_time_iso_8601") for f in version_files]
    _apply_quarantine(result, [t for t in upload_times if t], pkg_name, target_version)
    return result


def _apply_quarantine(
    result: dict[str, Any], timestamps: list[str], pkg_name: str, version: str
) -> None:
    """Set quarantine fields from upload timestamps; fail closed if unknown.

    Uses the newest timestamp so a file added to an old release (a common
    way to slip in a malicious wheel) restarts the quarantine clock.
    """
    parsed: list[datetime] = []
    for ts in timestamps:
        try:
            parsed.append(datetime.fromisoformat(ts.replace("Z", "+00:00")))
        except (ValueError, TypeError):
            continue
    if not parsed:
        result["error"] = (
            f"Cannot determine publication date for '{pkg_name}' {version or '(latest)'}."
        )
        return
    newest = max(parsed)
    result["publication_date"] = newest.isoformat()
    if (datetime.now(timezone.utc) - newest).days < QUARANTINE_DAYS:
        result["quarantine_ok"] = False


def check_npm(pkg_name: str, spec: str | None = None) -> dict[str, Any]:
    """Check an npm package against the registry for license and publish time.

    ``spec`` may be an exact version, a dist-tag (``next``), a range, or
    None. Exact versions and dist-tags resolve precisely; ranges and None
    fall back to the ``latest`` dist-tag, matching check_pypi's behavior.
    """
    result: dict[str, Any] = {
        "package": pkg_name,
        "ecosystem": "node",
        "license": None,
        "license_allowed": False,
        "license_conditional": False,
        "quarantine_ok": True,
        "publication_date": None,
        "checked_version": None,
        "error": None,
    }
    try:
        data = _fetch_json(f"https://registry.npmjs.org/{urllib.parse.quote(pkg_name, safe='@')}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            result["error"] = f"Package '{pkg_name}' not found on the npm registry."
        else:
            result["error"] = f"npm registry returned HTTP {e.code} for '{pkg_name}'."
        return result
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        result["error"] = f"Failed to reach the npm registry: {e}"
        return result

    dist_tags = data.get("dist-tags") or {}
    versions = data.get("versions") or {}
    exact = _NPM_EXACT_RE.match(spec or "")
    if exact:
        target = exact.group(1)
        if target not in versions:
            result["error"] = f"Package '{pkg_name}' has no version '{target}' on npm."
            return result
    elif spec and spec in dist_tags:
        target = dist_tags[spec]
    else:
        target = dist_tags.get("latest", "")
    result["checked_version"] = target

    manifest = versions.get(target) or {}
    license_field = manifest.get("license", data.get("license"))
    if isinstance(license_field, dict):
        license_field = license_field.get("type")
    license_raw = license_field if isinstance(license_field, str) else ""
    result["license"] = license_raw
    result["license_allowed"], result["license_conditional"] = evaluate_license(license_raw)

    published = (data.get("time") or {}).get(target)
    _apply_quarantine(result, [published] if published else [], pkg_name, target)
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


def _result_issue(result: dict[str, Any]) -> str | None:
    """Turn a registry check result into a deny reason, or None if it passes."""
    pkg_name = result["package"]
    if result["error"]:
        return (
            f"[{pkg_name}] {result['error']} "
            "Cannot verify license or quarantine. "
            "Install manually after verification."
        )
    if not result["license_allowed"]:
        license_display = result["license"] or "UNKNOWN"
        return (
            f"[{pkg_name}] License '{license_display}' is not in the "
            "allowed-licenses list. Options:\n"
            "  1. Find a permissively-licensed alternative\n"
            "  2. File an exception in the project's decisions/ folder\n"
            "  3. Add the license to ALLOWED_LICENSES if your policy permits it"
        )
    if result["license_conditional"]:
        print(
            f"dependency-gate: {pkg_name} — conditional license "
            f"({result['license']}). Verify conditions do not apply.",
            file=sys.stderr,
        )
    if not result["quarantine_ok"]:
        return (
            f"[{pkg_name}] Published {result['publication_date']}. "
            f"Supply-chain quarantine requires packages to be >{QUARANTINE_DAYS} "
            "days old before installation. Wait or pin an older version."
        )
    return None


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
        if is_first_party(pkg_name, ecosystem):
            print(
                f"dependency-gate: {pkg_name} — first-party exemption, skipping checks.",
                file=sys.stderr,
            )
            continue

        if ecosystem == "python":
            result = check_pypi(pkg_name, pinned_version=spec.pinned_version)
        elif ecosystem == "node":
            result = check_npm(pkg_name, spec.pinned_version)
        else:
            # cargo/go/brew: no registry check implemented yet.
            print(
                f"dependency-gate: {pkg_name} ({ecosystem}) — automated license "
                "check not available for this ecosystem. Check manually before "
                "proceeding.",
                file=sys.stderr,
            )
            continue

        issue = _result_issue(result)
        if issue:
            issues.append(issue)

    if issues:
        reason = "Dependency gate blocked this install:\n\n" + "\n\n".join(issues)
        json.dump(deny(reason), sys.stdout)
        return 0

    # All packages passed. Allow the command.
    return 0


if __name__ == "__main__":
    sys.exit(main())
