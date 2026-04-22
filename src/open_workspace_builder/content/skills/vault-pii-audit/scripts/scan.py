#!/usr/bin/env python3
"""Vault PII and secrets scanner.

Scans files for PII and secret patterns defined in the OWB-bundled
``pii-handling-policy.md``. Outputs findings as JSON (for consumption by
the ``vault-pii-audit`` skill) or as a human-readable table.

Usage:
    python scan.py --mode full [--vault-root PATH] [--memory-root PATH]
    python scan.py --mode session --files file1.md file2.md
    python scan.py --mode full --pii-profile <vault_root>/.owb/pii-profile.yaml
    python scan.py --mode full --json

Vault root resolution (first match wins):
    1. ``--vault-root`` CLI flag
    2. ``OWB_VAULT_ROOT`` environment variable
    3. current working directory, if it contains ``_bootstrap.md``

If none resolve, the script exits non-zero and asks the operator to set
``OWB_VAULT_ROOT`` or pass ``--vault-root``.

PII profile is optional. When present, ``exclusions.emails`` additions
are merged with the pre-seeded set, and disabled ``categories:`` skip
their patterns entirely.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path

# --- Pre-seeded exclusions ---
# These are generic-public strings that look like PII to regex but are not
# sensitive for any operator. Operator-specific exclusions land in the PII
# profile at ``<vault_root>/.owb/pii-profile.yaml`` and are merged at load.

PRE_SEEDED_EXCLUDED_EMAILS: frozenset[str] = frozenset(
    {
        "noreply@anthropic.com",  # Claude / Anthropic SDK attribution
    }
)

# RFC 2606 reserved domains used in documentation and examples
EXCLUDED_EMAIL_DOMAINS: frozenset[str] = frozenset(
    {
        "example.com",
        "example.org",
        "example.net",
        "example.edu",
    }
)

# Git SSH URLs look like emails but are not PII
EXCLUDED_EMAIL_PATTERNS: tuple[re.Pattern[str], ...] = (re.compile(r"^git@"),)

# Matches URLs in a line so we can check whether a numeric match falls inside one.
# Covers http(s) URLs and common shortlink patterns.
_URL_RE: re.Pattern[str] = re.compile(r"https?://\S+")

# Numeric-pattern names that should be suppressed when they overlap a URL span.
_NUMERIC_PATTERNS: frozenset[str] = frozenset({"phone_number", "ssn", "tax_id", "credit_card"})

# Paths that contain detection patterns as documentation (self-reference)
EXCLUDED_FILE_PATTERNS: tuple[str, ...] = (
    "pii-handling-policy.md",
    "vault-pii-audit",
)

EXCLUDED_DIRS: frozenset[str] = frozenset(
    {
        ".obsidian",
        ".smart-env",
        ".secure",
        ".git",
        ".trash",
        ".owb",
        "__pycache__",
        "node_modules",
    }
)

EXCLUDED_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".age",
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".svg",
        ".pdf",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".ico",
        ".zip",
        ".tar",
        ".gz",
        ".bz2",
        ".pyc",
        ".so",
        ".dylib",
    }
)

# --- Pattern Definitions ---


@dataclass(frozen=True)
class Pattern:
    name: str
    category: str  # "secret" or "pii"
    regex: re.Pattern[str]
    context_required: bool = False
    context_words: tuple[str, ...] = ()
    # When set, the pattern only runs if this category appears in the
    # profile's ``categories:`` list. Secrets are always scanned.
    profile_category: str | None = None


CONTEXT_WORDS = ("api", "key", "token", "secret", "auth", "password", "credential")

PATTERNS: tuple[Pattern, ...] = (
    # Secrets — always scanned
    Pattern("openai_api_key", "secret", re.compile(r"sk-[a-zA-Z0-9]{20,}")),
    Pattern(
        "github_token",
        "secret",
        re.compile(r"(ghp_[a-zA-Z0-9]{36}|gho_[a-zA-Z0-9]{36}|github_pat_[a-zA-Z0-9_]{80,})"),
    ),
    Pattern("slack_token", "secret", re.compile(r"xox[bpras]-[a-zA-Z0-9\-]+")),
    Pattern("aws_access_key", "secret", re.compile(r"AKIA[A-Z0-9]{16}")),
    Pattern("anthropic_api_key", "secret", re.compile(r"sk-ant-[a-zA-Z0-9\-]+")),
    Pattern("bearer_token", "secret", re.compile(r"Bearer\s+[a-zA-Z0-9._\-]{20,}")),
    Pattern("age_private_key", "secret", re.compile(r"AGE-SECRET-KEY-[A-Z0-9]+")),
    Pattern(
        "private_key_pem",
        "secret",
        re.compile(r"-----BEGIN[A-Z ]*PRIVATE KEY-----"),
    ),
    Pattern(
        "connection_string_password",
        "secret",
        re.compile(r"(password|passwd|pwd)\s*[:=]\s*\S+", re.IGNORECASE),
    ),
    Pattern(
        "url_with_credentials",
        "secret",
        re.compile(r"://[^@\s]{3,}@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
    ),
    Pattern(
        "hex_api_key",
        "secret",
        re.compile(r"\b[a-f0-9]{32,}\b"),
        context_required=True,
        context_words=CONTEXT_WORDS,
    ),
    # PII — gated by profile categories
    Pattern(
        "email_address",
        "pii",
        re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}"),
        profile_category="email",
    ),
    Pattern(
        "phone_number",
        "pii",
        re.compile(r"\+?1?[-.\s]?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}"),
        context_required=True,
        context_words=(
            "phone",
            "cell",
            "mobile",
            "fax",
            "tel",
            "call",
            "contact",
            "sms",
            "text",
        ),
        profile_category="phone",
    ),
    Pattern("ssn", "pii", re.compile(r"\b\d{3}-\d{2}-\d{4}\b"), profile_category="ssn"),
    Pattern("tax_id", "pii", re.compile(r"\b\d{2}-\d{7}\b"), profile_category="tax_id"),
    Pattern(
        "credit_card",
        "pii",
        re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{1,4}\b"),
        context_required=True,
        context_words=(
            "card",
            "credit",
            "debit",
            "visa",
            "mastercard",
            "amex",
            "payment",
            "billing",
        ),
        profile_category="credit_card",
    ),
    Pattern(
        "terminal_prompt",
        "pii",
        re.compile(r"[a-z]+@[A-Z][a-zA-Z]*-[A-Z][a-zA-Z0-9\-]*"),
        profile_category="terminal_prompt",
    ),
)


@dataclass(frozen=True)
class Profile:
    categories: frozenset[str]
    excluded_emails: frozenset[str]

    @classmethod
    def default(cls) -> "Profile":
        return cls(
            categories=frozenset(
                {
                    "email",
                    "phone",
                    "address",
                    "ssn",
                    "tax_id",
                    "credit_card",
                    "terminal_prompt",
                }
            ),
            excluded_emails=PRE_SEEDED_EXCLUDED_EMAILS,
        )

    @classmethod
    def load(cls, path: Path) -> "Profile":
        if not path.exists():
            return cls.default()
        try:
            import yaml  # type: ignore[import-not-found]
        except ImportError:
            print(
                "scan.py: PyYAML is required to load the PII profile; using defaults",
                file=sys.stderr,
            )
            return cls.default()
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except (OSError, yaml.YAMLError) as exc:
            print(f"scan.py: failed to load PII profile: {exc}", file=sys.stderr)
            return cls.default()
        cats_in = data.get("categories") or []
        excl_in = (data.get("exclusions") or {}).get("emails") or []
        return cls(
            categories=frozenset(str(c) for c in cats_in) if cats_in else cls.default().categories,
            excluded_emails=PRE_SEEDED_EXCLUDED_EMAILS | frozenset(str(e).lower() for e in excl_in),
        )


@dataclass(frozen=True)
class Finding:
    file: str
    line_number: int
    pattern_name: str
    category: str
    matched_text: str
    context_line: str

    def masked_text(self) -> str:
        text = self.matched_text
        if len(text) <= 8:
            return text[:2] + "***"
        return text[:4] + "***" + text[-3:]

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "line": self.line_number,
            "pattern": self.pattern_name,
            "category": self.category,
            "masked": self.masked_text(),
            "context": self.context_line.strip()[:120],
        }


def should_skip_dir(dirpath: Path) -> bool:
    return any(part in EXCLUDED_DIRS for part in dirpath.parts)


def should_skip_file(filepath: Path) -> bool:
    return filepath.suffix.lower() in EXCLUDED_EXTENSIONS


def is_excluded_match(
    pattern: Pattern,
    matched_text: str,
    line: str,
    match: re.Match[str],
    profile: Profile,
) -> bool:
    if pattern.name == "email_address":
        if matched_text.lower() in profile.excluded_emails:
            return True
        if "@users.noreply.github.com" in matched_text:
            return True
        if any(p.match(matched_text) for p in EXCLUDED_EMAIL_PATTERNS):
            return True
        # RFC 2606 reserved domains used in documentation examples
        domain = matched_text.split("@", 1)[1].lower() if "@" in matched_text else ""
        if domain in EXCLUDED_EMAIL_DOMAINS:
            return True

    # Numeric patterns inside URLs are almost always IDs (tweet IDs, DOIs, etc.)
    if pattern.name in _NUMERIC_PATTERNS and _match_inside_url(line, match):
        return True

    # git+ssh://git@host is not embedded credentials
    if pattern.name == "url_with_credentials" and "://git@" in matched_text:
        return True

    # Sudoers NOPASSWD directive is not an exposed password
    if pattern.name == "connection_string_password" and "nopasswd" in line.lower():
        return True

    # Placeholder keys ending with "..." are documentation examples
    if pattern.category == "secret" and matched_text.rstrip().endswith("..."):
        return True

    return False


def is_excluded_file(filepath: Path) -> bool:
    filepath_str = str(filepath)
    return any(pat in filepath_str for pat in EXCLUDED_FILE_PATTERNS)


def check_context(line: str, context_words: tuple[str, ...]) -> bool:
    """Return True if any context word appears as a whole word in the line."""
    line_lower = line.lower()
    return any(re.search(rf"\b{re.escape(word)}\b", line_lower) for word in context_words)


def _match_inside_url(line: str, match: re.Match[str]) -> bool:
    """Return True if the match span falls entirely within a URL on this line."""
    start, end = match.start(), match.end()
    for url_match in _URL_RE.finditer(line):
        if url_match.start() <= start and end <= url_match.end():
            return True
    return False


def scan_file(filepath: Path, profile: Profile) -> list[Finding]:
    findings: list[Finding] = []
    if is_excluded_file(filepath):
        return findings
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except (OSError, PermissionError):
        return findings

    for line_number, line in enumerate(content.splitlines(), start=1):
        for pattern in PATTERNS:
            # Skip PII patterns whose category is disabled in the profile.
            if pattern.profile_category and pattern.profile_category not in profile.categories:
                continue

            for match in pattern.regex.finditer(line):
                matched_text = match.group(0)

                if is_excluded_match(pattern, matched_text, line, match, profile):
                    continue

                if pattern.context_required and not check_context(line, pattern.context_words):
                    continue

                findings.append(
                    Finding(
                        file=str(filepath),
                        line_number=line_number,
                        pattern_name=pattern.name,
                        category=pattern.category,
                        matched_text=matched_text,
                        context_line=line,
                    )
                )

    return findings


def scan_directory(dirpath: Path, profile: Profile) -> list[Finding]:
    findings: list[Finding] = []
    if not dirpath.exists():
        return findings

    for filepath in sorted(dirpath.rglob("*")):
        if not filepath.is_file():
            continue
        if should_skip_dir(filepath.parent):
            continue
        if should_skip_file(filepath):
            continue
        findings.extend(scan_file(filepath, profile))

    return findings


def resolve_vault_root(flag: str | None) -> Path:
    if flag:
        return Path(flag).expanduser()
    env_val = os.environ.get("OWB_VAULT_ROOT")
    if env_val:
        return Path(env_val).expanduser()
    cwd = Path.cwd()
    if (cwd / "_bootstrap.md").exists():
        return cwd
    raise SystemExit(
        "scan.py: vault root not resolved. "
        "Set OWB_VAULT_ROOT in the environment or pass --vault-root <path>."
    )


def resolve_memory_root(flag: str | None) -> Path:
    if flag:
        return Path(flag).expanduser()
    return Path.home() / ".claude" / "projects"


def scan_full(vault_root: Path, memory_root: Path, profile: Profile) -> list[Finding]:
    findings: list[Finding] = []

    findings.extend(scan_directory(vault_root, profile))

    if memory_root.exists():
        for project_dir in sorted(memory_root.iterdir()):
            memory_dir = project_dir / "memory"
            if memory_dir.exists():
                findings.extend(scan_directory(memory_dir, profile))
            memory_index = project_dir / "MEMORY.md"
            if memory_index.exists():
                findings.extend(scan_file(memory_index, profile))

    return findings


def scan_session(files: list[str], profile: Profile) -> list[Finding]:
    findings: list[Finding] = []
    for filepath_str in files:
        filepath = Path(filepath_str)
        if filepath.exists() and filepath.is_file() and not should_skip_file(filepath):
            findings.extend(scan_file(filepath, profile))
    return findings


def main() -> None:
    parser = argparse.ArgumentParser(description="Vault PII and secrets scanner")
    parser.add_argument("--mode", choices=["full", "session"], required=True)
    parser.add_argument("--files", nargs="*", default=[], help="Files to scan (session mode)")
    parser.add_argument("--vault-root", default=None, help="Override vault root path")
    parser.add_argument("--memory-root", default=None, help="Override agent memory root path")
    parser.add_argument(
        "--pii-profile",
        default=None,
        help="Path to pii-profile.yaml (defaults to <vault_root>/.owb/pii-profile.yaml)",
    )
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    vault_root = resolve_vault_root(args.vault_root)
    memory_root = resolve_memory_root(args.memory_root)

    profile_path = (
        Path(args.pii_profile).expanduser()
        if args.pii_profile
        else vault_root / ".owb" / "pii-profile.yaml"
    )
    profile = Profile.load(profile_path)

    if args.mode == "full":
        findings = scan_full(vault_root, memory_root, profile)
    else:
        findings = scan_session(args.files, profile)

    if args.json:
        print(json.dumps([f.to_dict() for f in findings], indent=2))
    else:
        if not findings:
            print("No PII or secrets found.")
            return

        print(f"\nFound {len(findings)} potential finding(s):\n")
        print(f"{'#':<4} {'Type':<28} {'Cat':<8} {'File':<60} {'Line':<6} {'Preview'}")
        print("-" * 140)
        for i, f in enumerate(findings, 1):
            rel_file = f.file
            for prefix in [str(vault_root) + "/", str(Path.home()) + "/"]:
                if rel_file.startswith(prefix):
                    rel_file = rel_file[len(prefix) :]
                    break
            print(
                f"{i:<4} {f.pattern_name:<28} {f.category:<8} {rel_file:<60} "
                f"{f.line_number:<6} {f.masked_text()}"
            )

        secrets = [f for f in findings if f.category == "secret"]
        pii = [f for f in findings if f.category == "pii"]
        print(f"\nSummary: {len(secrets)} secret(s), {len(pii)} PII finding(s)")


if __name__ == "__main__":
    main()
