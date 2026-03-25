"""License compliance audit: parse allowed-licenses policy and check dependencies.

Parses content/policies/allowed-licenses.md at runtime to build allow/conditional/deny
lists. Runs pip-licenses (via subprocess) and reports per-dependency status.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path


# ── Dataclasses ──────────────────────────────────────────────────────────


@dataclass(frozen=True)
class LicenseCategory:
    """A license entry from the policy with its category and optional condition."""

    name: str
    patterns: tuple[str, ...]
    condition: str = ""


@dataclass(frozen=True)
class LicensePolicy:
    """Parsed license policy with three categories."""

    allowed: tuple[LicenseCategory, ...]
    conditional: tuple[LicenseCategory, ...]
    disallowed: tuple[LicenseCategory, ...]


@dataclass(frozen=True)
class LicenseFinding:
    """License status for a single dependency."""

    package: str
    version: str
    license_name: str
    status: str  # "pass", "conditional", "fail", "unknown"
    policy_note: str = ""


@dataclass(frozen=True)
class LicenseAuditReport:
    """Aggregated license audit results."""

    findings: tuple[LicenseFinding, ...]
    policy_file: str
    ecosystem: str


# ── Policy Parsing ───────────────────────────────────────────────────────


def _extract_table_rows(section: str) -> list[tuple[str, str]]:
    """Extract (name, notes) pairs from a markdown table section."""
    rows: list[tuple[str, str]] = []
    for line in section.splitlines():
        line = line.strip()
        if not line.startswith("|") or line.startswith("|--") or line.startswith("| License"):
            continue
        cells = [c.strip() for c in line.split("|")]
        # Filter empty strings from leading/trailing pipes
        cells = [c for c in cells if c]
        if len(cells) >= 2:
            rows.append((cells[0], cells[1]))
    return rows


def _build_patterns(license_name: str) -> tuple[str, ...]:
    """Build case-insensitive match patterns from a license name.

    Handles common variations: "MIT" vs "MIT License", "Apache 2.0" vs "Apache-2.0",
    "BSD 3-Clause" vs "BSD-3-Clause", slash-separated entries like "CC0 / Public Domain / Unlicense".
    """
    patterns: list[str] = []
    # Handle slash-separated entries (e.g., "CC0 / Public Domain / Unlicense")
    parts = [p.strip() for p in license_name.split("/")]
    for part in parts:
        normalized = part.lower().strip()
        if not normalized:
            continue
        patterns.append(normalized)
        # Add variations with/without "license" suffix
        if not normalized.endswith("license"):
            patterns.append(f"{normalized} license")
        # Add dash/space variants (e.g., "apache 2.0" → "apache-2.0")
        if " " in normalized:
            patterns.append(normalized.replace(" ", "-"))
        if "-" in normalized:
            patterns.append(normalized.replace("-", " "))
        # Handle version variants: "v2" ↔ "2", "v3" ↔ "3"
        version_match = re.search(r"\bv(\d)", normalized)
        if version_match:
            patterns.append(normalized.replace(f"v{version_match.group(1)}", version_match.group(1)))
    return tuple(dict.fromkeys(patterns))  # dedupe preserving order


def _parse_section(content: str, heading: str) -> str:
    """Extract the content between a heading and the next ## heading."""
    pattern = rf"^##\s+{re.escape(heading)}.*?$"
    match = re.search(pattern, content, re.MULTILINE)
    if not match:
        return ""
    start = match.end()
    next_heading = re.search(r"^##\s+", content[start:], re.MULTILINE)
    end = start + next_heading.start() if next_heading else len(content)
    return content[start:end]


def parse_license_policy(policy_path: Path) -> LicensePolicy:
    """Parse the allowed-licenses.md policy file into structured categories.

    Raises ValueError if the file is missing or cannot be parsed.
    """
    if not policy_path.is_file():
        raise ValueError(
            f"License policy file not found: {policy_path}. "
            "Cannot determine allowed licenses without this file."
        )

    content = policy_path.read_text(encoding="utf-8")

    allowed_section = _parse_section(content, "Allowed (Permissive)")
    conditional_section = _parse_section(content, "Allowed with Conditions")
    disallowed_section = _parse_section(content, "Disallowed (Copyleft")

    if not allowed_section and not disallowed_section:
        raise ValueError(
            f"Could not parse license categories from {policy_path}. "
            "Expected '## Allowed (Permissive)' and '## Disallowed' sections."
        )

    allowed = tuple(
        LicenseCategory(name=name, patterns=_build_patterns(name))
        for name, _notes in _extract_table_rows(allowed_section)
    )
    conditional = tuple(
        LicenseCategory(name=name, patterns=_build_patterns(name), condition=condition)
        for name, condition in _extract_table_rows(conditional_section)
    )
    disallowed = tuple(
        LicenseCategory(name=name, patterns=_build_patterns(name))
        for name, _reason in _extract_table_rows(disallowed_section)
    )

    return LicensePolicy(allowed=allowed, conditional=conditional, disallowed=disallowed)


# ── License Matching ─────────────────────────────────────────────────────


def _classify_license(
    license_text: str,
    policy: LicensePolicy,
) -> tuple[str, str]:
    """Classify a license string against policy categories.

    Returns (status, note) where status is one of: "pass", "conditional", "fail", "unknown".
    """
    normalized = license_text.lower().strip()
    if not normalized or normalized in ("unknown", "unknown license"):
        return "unknown", "License not specified or unknown — manual review required"

    for cat in policy.allowed:
        if _matches_category(normalized, cat):
            return "pass", ""

    for cat in policy.conditional:
        if _matches_category(normalized, cat):
            return "conditional", cat.condition

    for cat in policy.disallowed:
        if _matches_category(normalized, cat):
            return "fail", f"Disallowed license: {cat.name}"

    return "unknown", f"License '{license_text}' not in policy — manual review required"


def _matches_category(normalized_license: str, category: LicenseCategory) -> bool:
    """Check if a normalized license string matches any pattern in a category."""
    for pattern in category.patterns:
        if pattern in normalized_license or normalized_license in pattern:
            return True
        # Also check without common suffixes/prefixes
        stripped = normalized_license.replace(" license", "").replace("-or-later", "")
        if pattern in stripped or stripped in pattern:
            return True
    return False


# ── Dependency Discovery ─────────────────────────────────────────────────


def _run_pip_licenses() -> list[dict[str, str]]:
    """Run pip-licenses and return parsed JSON output.

    Tries uvx first, falls back to pip-licenses directly.
    """
    commands = [
        ["uvx", "pip-licenses", "--format=json", "--with-system"],
        ["pip-licenses", "--format=json", "--with-system"],
    ]

    last_error: Exception | None = None
    for cmd in commands:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=60,
            )
            if proc.returncode == 0 and proc.stdout.strip():
                return json.loads(proc.stdout)  # type: ignore[no-any-return]
            last_error = RuntimeError(
                f"{cmd[0]} exited with code {proc.returncode}: {proc.stderr.strip()}"
            )
        except FileNotFoundError:
            last_error = FileNotFoundError(f"{cmd[0]} not found")
            continue
        except subprocess.TimeoutExpired:
            last_error = RuntimeError(f"{cmd[0]} timed out")
            continue
        except json.JSONDecodeError as exc:
            last_error = RuntimeError(f"{cmd[0]} returned invalid JSON: {exc}")
            continue

    raise RuntimeError(
        "Could not run pip-licenses. Install it with: uvx pip-licenses --format=json\n"
        f"Last error: {last_error}"
    )


# ── Public API ───────────────────────────────────────────────────────────


def audit_licenses(
    policy_path: Path,
    dep_data: list[dict[str, str]] | None = None,
) -> LicenseAuditReport:
    """Run license audit against the policy file.

    Parameters
    ----------
    policy_path:
        Path to the allowed-licenses.md policy file.
    dep_data:
        Optional pre-loaded dependency data (for testing). If None, runs pip-licenses.
    """
    policy = parse_license_policy(policy_path)

    if dep_data is None:
        dep_data = _run_pip_licenses()

    findings: list[LicenseFinding] = []
    for dep in dep_data:
        name = dep.get("Name", dep.get("name", ""))
        version = dep.get("Version", dep.get("version", ""))
        license_name = dep.get("License", dep.get("license", ""))

        status, note = _classify_license(license_name, policy)
        findings.append(
            LicenseFinding(
                package=name,
                version=version,
                license_name=license_name,
                status=status,
                policy_note=note,
            )
        )

    return LicenseAuditReport(
        findings=tuple(findings),
        policy_file=str(policy_path),
        ecosystem="python",
    )


def format_license_report(report: LicenseAuditReport) -> dict:
    """Serialize a LicenseAuditReport to a JSON-compatible dict."""
    return {
        "type": "license_audit",
        "ecosystem": report.ecosystem,
        "policy_file": report.policy_file,
        "summary": {
            "total": len(report.findings),
            "pass": sum(1 for f in report.findings if f.status == "pass"),
            "conditional": sum(1 for f in report.findings if f.status == "conditional"),
            "fail": sum(1 for f in report.findings if f.status == "fail"),
            "unknown": sum(1 for f in report.findings if f.status == "unknown"),
        },
        "findings": [
            {
                "package": f.package,
                "version": f.version,
                "license": f.license_name,
                "status": f.status,
                "note": f.policy_note,
            }
            for f in report.findings
        ],
    }


def print_license_report(report: LicenseAuditReport) -> None:
    """Print a human-readable license audit report."""
    import click

    pass_count = sum(1 for f in report.findings if f.status == "pass")
    conditional_count = sum(1 for f in report.findings if f.status == "conditional")
    fail_count = sum(1 for f in report.findings if f.status == "fail")
    unknown_count = sum(1 for f in report.findings if f.status == "unknown")

    click.echo(f"\n=== License Audit ({report.ecosystem}) ===")
    click.echo(f"Policy: {report.policy_file}")
    click.echo(
        f"Total: {len(report.findings)} | "
        f"Pass: {pass_count} | Conditional: {conditional_count} | "
        f"Fail: {fail_count} | Unknown: {unknown_count}\n"
    )

    # Show failures and unknowns first
    for f in report.findings:
        if f.status == "fail":
            click.echo(f"  FAIL  {f.package}=={f.version}  [{f.license_name}]")
            if f.policy_note:
                click.echo(f"        {f.policy_note}")
    for f in report.findings:
        if f.status == "unknown":
            click.echo(f"  ???   {f.package}=={f.version}  [{f.license_name}]")
            if f.policy_note:
                click.echo(f"        {f.policy_note}")
    for f in report.findings:
        if f.status == "conditional":
            click.echo(f"  COND  {f.package}=={f.version}  [{f.license_name}]")
            if f.policy_note:
                click.echo(f"        {f.policy_note}")
