"""MCP server exposing OWB security scan, dep audit, and license audit tools.

Requires the ``mcp`` optional dependency: ``uv pip install open-workspace-builder[mcp]``
"""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

try:
    from mcp.server.fastmcp import FastMCP
except ImportError:
    FastMCP = None  # type: ignore[assignment,misc]

# Token estimate per item for L3 semantic analysis (configurable)
L3_TOKENS_PER_ITEM = 2000

# Batch confirmation threshold
BATCH_CONFIRM_THRESHOLD = 10


def _require_mcp() -> None:
    """Raise a clear error if the mcp extra is not installed."""
    if FastMCP is None:
        raise ImportError(
            "The MCP server requires the 'mcp' package. "
            "Install it with: uv pip install open-workspace-builder[mcp]"
        )


# ── Response helpers ─────────────────────────────────────────────────────


@dataclass(frozen=True)
class ConfirmationRequired:
    """Structured response requesting user confirmation before proceeding."""

    requires_confirmation: bool
    message: str
    action: str
    parameters: dict[str, Any] = field(default_factory=dict)


def _confirmation_response(message: str, action: str, **params: Any) -> dict[str, Any]:
    """Build a confirmation-required response dict."""
    return asdict(ConfirmationRequired(
        requires_confirmation=True,
        message=message,
        action=action,
        parameters=params,
    ))


# ── Serializers ──────────────────────────────────────────────────────────


def _serialize_scan_verdict(verdict: Any) -> dict[str, Any]:
    """Serialize a ScanVerdict to a JSON-compatible dict."""
    return {
        "file_path": verdict.file_path,
        "verdict": verdict.verdict,
        "flags": [
            {
                "category": f.category,
                "severity": f.severity,
                "evidence": f.evidence,
                "description": f.description,
                "line_number": f.line_number,
                "layer": f.layer,
            }
            for f in verdict.flags
        ],
    }


def _serialize_scan_report(report: Any) -> dict[str, Any]:
    """Serialize a ScanReport to a JSON-compatible dict."""
    return {
        "directory": report.directory,
        "verdicts": [_serialize_scan_verdict(v) for v in report.verdicts],
        "summary": dict(report.summary),
    }


def _serialize_audit_report(report: Any) -> dict[str, Any]:
    """Serialize a FullAuditReport to a JSON-compatible dict."""
    vuln = report.vuln_report
    gd = report.guarddog_report
    return {
        "vulnerabilities": {
            "findings": [
                {
                    "package": f.package,
                    "installed_version": f.installed_version,
                    "vuln_id": f.vuln_id,
                    "fix_version": f.fix_version,
                    "description": f.description,
                }
                for f in vuln.findings
            ],
            "skipped": list(vuln.skipped),
            "fix_suggestions": list(vuln.fix_suggestions),
        },
        "guarddog": {
            "flagged": [
                {
                    "package": f.package,
                    "rule_name": f.rule_name,
                    "severity": f.severity,
                    "file_path": f.file_path,
                    "evidence": f.evidence,
                }
                for f in gd.flagged
            ],
            "clean": list(gd.clean),
        },
    }


# ── Server factory ───────────────────────────────────────────────────────


def create_server() -> FastMCP:
    """Create and configure the OWB MCP server with all tools registered."""
    _require_mcp()

    mcp = FastMCP("owb", instructions="Open Workspace Builder security and audit tools")

    @mcp.tool()
    def owb_security_scan(
        path: str,
        layers: list[int] | None = None,
        include_sca: bool = False,
        include_sast: bool = False,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        """Scan files for security issues using OWB's multi-layer scanner.

        Layers: 1=structural checks, 2=pattern matching, 3=LLM semantic analysis.
        L1+L2 run by default. L3 requires explicit opt-in and confirmation.
        """
        effective_layers = tuple(layers) if layers else (1, 2)

        # L3 confirmation gate
        if 3 in effective_layers and not confirmed:
            target = Path(path)
            item_count = _count_scannable_items(target)
            token_estimate = item_count * L3_TOKENS_PER_ITEM
            return _confirmation_response(
                message=(
                    f"Layer 3 uses LLM API calls. Scanning {item_count} items "
                    f"will consume approximately {token_estimate} tokens. Proceed?"
                ),
                action="owb_security_scan",
                path=path,
                layers=list(effective_layers),
                include_sca=include_sca,
                include_sast=include_sast,
            )

        # Batch confirmation gate (L1+L2 only, not for L3 which has its own gate)
        if 3 not in effective_layers:
            target = Path(path)
            item_count = _count_scannable_items(target)
            if item_count >= BATCH_CONFIRM_THRESHOLD and not confirmed:
                return _confirmation_response(
                    message=(
                        f"Scanning {item_count} items. This may take a moment. Proceed?"
                    ),
                    action="owb_security_scan",
                    path=path,
                    layers=list(effective_layers),
                    include_sca=include_sca,
                    include_sast=include_sast,
                )

        from open_workspace_builder.security.scanner import Scanner

        scanner = Scanner(layers=effective_layers)
        target = Path(path)

        if target.is_file():
            verdict = scanner.scan_file(target)
            result: dict[str, Any] = {
                "type": "file_scan",
                **_serialize_scan_verdict(verdict),
            }
        else:
            report = scanner.scan_directory(target)
            result = {"type": "directory_scan", **_serialize_scan_report(report)}

        # Note L3 availability if not used
        if 3 not in effective_layers:
            result["note"] = (
                "Layer 3 (LLM semantic analysis) is available but was not run. "
                "Pass layers=[1,2,3] and confirmed=true to enable it."
            )

        return result

    @mcp.tool()
    def owb_audit_deps(
        project_path: str = ".",
        deep: bool = False,
        fix: bool = False,
    ) -> dict[str, Any]:
        """Audit installed Python dependencies for known vulnerabilities.

        Uses pip-audit (Layer A) and optionally guarddog (Layer B with deep=true).
        """
        from open_workspace_builder.security.dep_audit import run_full_audit

        report = run_full_audit(deep=deep, fix=fix)
        result = _serialize_audit_report(report)
        result["type"] = "dep_audit"
        result["project_path"] = project_path
        return result

    @mcp.tool()
    def owb_audit_package(
        package_name: str,
        version: str | None = None,
        ecosystem: str = "pypi",
    ) -> dict[str, Any]:
        """Audit a single package for vulnerabilities and malicious code.

        Runs pip-audit + guarddog against the named package.
        """
        from open_workspace_builder.security.dep_audit import audit_single_package

        report = audit_single_package(package_name, version)
        result = _serialize_audit_report(report)
        result["type"] = "package_audit"
        result["package_name"] = package_name
        result["version"] = version
        result["ecosystem"] = ecosystem
        return result

    @mcp.tool()
    def owb_audit_licenses(
        project_path: str = ".",
    ) -> dict[str, Any]:
        """Audit installed dependency licenses against the OWB allowed-licenses policy."""
        try:
            from open_workspace_builder.security.license_audit import (
                audit_licenses,
                format_license_report,
            )
        except ImportError:
            return {
                "type": "license_audit",
                "error": (
                    "License audit module not available. "
                    "Ensure the S068 license audit feature is installed."
                ),
            }

        policy_path = _find_policy_file(project_path)
        if policy_path is None:
            return {
                "type": "license_audit",
                "error": (
                    "License policy file (allowed-licenses.md) not found. "
                    "Searched content/policies/ and Obsidian/code/."
                ),
            }

        report = audit_licenses(policy_path)
        return format_license_report(report)

    return mcp


# ── Utility functions ────────────────────────────────────────────────────


def _count_scannable_items(target: Path) -> int:
    """Count the number of files that would be scanned in a path."""
    if target.is_file():
        return 1
    return sum(1 for f in target.glob("*.md") if f.is_file())


def _find_policy_file(project_path: str) -> Path | None:
    """Locate the allowed-licenses.md policy file relative to project path."""
    base = Path(project_path)
    candidates = [
        base / "content" / "policies" / "allowed-licenses.md",
        base / "Obsidian" / "code" / "allowed-licenses.md",
    ]
    # Also try walking up from the project path
    for parent in [base] + list(base.resolve().parents)[:3]:
        candidates.append(parent / "content" / "policies" / "allowed-licenses.md")

    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


# ── Entry point ──────────────────────────────────────────────────────────


def run_server() -> None:
    """Start the MCP server (called by ``owb mcp serve``)."""
    _require_mcp()
    server = create_server()
    server.run()
