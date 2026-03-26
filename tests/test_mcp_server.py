"""Tests for the OWB MCP server module."""

from __future__ import annotations

from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest


# ── Import guard ─────────────────────────────────────────────────────────


class TestImportGuard:
    def test_require_mcp_raises_when_not_installed(self) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP", None):
            from open_workspace_builder.mcp_server import _require_mcp

            with pytest.raises(ImportError, match="mcp"):
                _require_mcp()


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture()
def scan_verdict() -> object:
    """Create a mock ScanVerdict."""
    flag = MagicMock(
        category="secret",
        severity="critical",
        evidence="API_KEY=...",
        description="Hardcoded secret",
        line_number=5,
        layer=2,
    )
    return MagicMock(
        file_path="/test/file.md",
        verdict="malicious",
        flags=[flag],
    )


@pytest.fixture()
def scan_report(scan_verdict: object) -> object:
    """Create a mock ScanReport."""
    return MagicMock(
        directory="/test/dir",
        verdicts=[scan_verdict],
        summary={"clean": 0, "flagged": 0, "malicious": 1, "error": 0},
    )


# ── Serializer tests ────────────────────────────────────────────────────


class TestSerializers:
    def test_serialize_scan_verdict(self, scan_verdict: object) -> None:
        from open_workspace_builder.mcp_server import _serialize_scan_verdict

        result = _serialize_scan_verdict(scan_verdict)
        assert result["file_path"] == "/test/file.md"
        assert result["verdict"] == "malicious"
        assert len(result["flags"]) == 1
        assert result["flags"][0]["category"] == "secret"

    def test_serialize_scan_report(self, scan_report: object) -> None:
        from open_workspace_builder.mcp_server import _serialize_scan_report

        result = _serialize_scan_report(scan_report)
        assert result["directory"] == "/test/dir"
        assert len(result["verdicts"]) == 1
        assert result["summary"]["malicious"] == 1

    def test_serialize_audit_report(self) -> None:
        from open_workspace_builder.mcp_server import _serialize_audit_report

        vuln = MagicMock(
            findings=[
                MagicMock(
                    package="requests",
                    installed_version="2.28.0",
                    vuln_id="CVE-2023-1234",
                    fix_version="2.28.1",
                    description="Test vuln",
                )
            ],
            skipped=["some-pkg"],
            fix_suggestions=["requests==2.28.1"],
        )
        gd = MagicMock(
            flagged=[
                MagicMock(
                    package="evil-pkg",
                    rule_name="cmd-overwrite",
                    severity="critical",
                    file_path="setup.py",
                    evidence="os.system(...)",
                )
            ],
            clean=["safe-pkg"],
        )
        report = MagicMock(vuln_report=vuln, guarddog_report=gd)
        result = _serialize_audit_report(report)

        assert len(result["vulnerabilities"]["findings"]) == 1
        assert result["vulnerabilities"]["findings"][0]["vuln_id"] == "CVE-2023-1234"
        assert len(result["guarddog"]["flagged"]) == 1
        assert result["guarddog"]["clean"] == ["safe-pkg"]


# ── Confirmation flow ────────────────────────────────────────────────────


class TestConfirmation:
    def test_confirmation_response_structure(self) -> None:
        from open_workspace_builder.mcp_server import _confirmation_response

        result = _confirmation_response("Are you sure?", "test_action", foo="bar")
        assert result["requires_confirmation"] is True
        assert result["message"] == "Are you sure?"
        assert result["action"] == "test_action"
        assert result["parameters"]["foo"] == "bar"


# ── Tool: owb_security_scan ─────────────────────────────────────────────


class TestSecurityScanTool:
    def test_default_layers_are_l1_l2(self, tmp_path: Path) -> None:
        """Without layers specified, runs L1+L2 only and notes L3 available."""
        test_file = tmp_path / "test.md"
        test_file.write_text("# Clean file\nNo issues.", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            # Extract the registered owb_security_scan function
            tool_fn = _extract_tool(mock_fmcp, "owb_security_scan")

        with patch("open_workspace_builder.security.scanner.Scanner") as MockScanner:
            mock_scanner = MockScanner.return_value
            mock_scanner.scan_file.return_value = MagicMock(
                file_path=str(test_file), verdict="clean", flags=[]
            )

            result = tool_fn(path=str(test_file), confirmed=True)

        MockScanner.assert_called_once_with(layers=(1, 2))
        assert result["type"] == "file_scan"
        assert "Layer 3" in result.get("note", "")

    def test_l3_requires_confirmation(self, tmp_path: Path) -> None:
        """L3 request without confirmed=True returns confirmation prompt."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_security_scan")

        result = tool_fn(path=str(test_file), layers=[1, 2, 3])

        assert result["requires_confirmation"] is True
        assert "Layer 3" in result["message"]
        assert "tokens" in result["message"]

    def test_l3_confirmed_executes(self, tmp_path: Path) -> None:
        """L3 with confirmed=True proceeds to scan."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_security_scan")

        with patch("open_workspace_builder.security.scanner.Scanner") as MockScanner:
            mock_scanner = MockScanner.return_value
            mock_scanner.scan_file.return_value = MagicMock(
                file_path=str(test_file), verdict="clean", flags=[]
            )

            result = tool_fn(path=str(test_file), layers=[1, 2, 3], confirmed=True)

        MockScanner.assert_called_once_with(layers=(1, 2, 3))
        assert result["type"] == "file_scan"
        assert "requires_confirmation" not in result

    def test_directory_scan(self, tmp_path: Path) -> None:
        """Directory path returns directory_scan type."""
        (tmp_path / "a.md").write_text("a", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_security_scan")

        with patch("open_workspace_builder.security.scanner.Scanner") as MockScanner:
            mock_scanner = MockScanner.return_value
            mock_scanner.scan_directory.return_value = MagicMock(
                directory=str(tmp_path),
                verdicts=[],
                summary={"clean": 0, "flagged": 0, "malicious": 0, "error": 0},
            )

            result = tool_fn(path=str(tmp_path), confirmed=True)

        assert result["type"] == "directory_scan"


# ── Tool: owb_audit_deps ────────────────────────────────────────────────


class TestAuditDepsTool:
    def test_returns_correct_structure(self) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_audit_deps")

        with patch("open_workspace_builder.security.dep_audit.run_full_audit") as mock_audit:
            mock_audit.return_value = MagicMock(
                vuln_report=MagicMock(findings=(), skipped=(), fix_suggestions=()),
                guarddog_report=MagicMock(flagged=(), clean=()),
            )

            result = tool_fn()

        assert result["type"] == "dep_audit"
        assert "vulnerabilities" in result
        assert "guarddog" in result

    def test_passes_deep_and_fix(self) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_audit_deps")

        with patch("open_workspace_builder.security.dep_audit.run_full_audit") as mock_audit:
            mock_audit.return_value = MagicMock(
                vuln_report=MagicMock(findings=(), skipped=(), fix_suggestions=()),
                guarddog_report=MagicMock(flagged=(), clean=()),
            )

            tool_fn(deep=True, fix=True)

        mock_audit.assert_called_once_with(deep=True, fix=True)


# ── Tool: owb_audit_package ─────────────────────────────────────────────


class TestAuditPackageTool:
    def test_returns_correct_structure(self) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_audit_package")

        with patch(
            "open_workspace_builder.security.dep_audit.audit_single_package"
        ) as mock_audit:
            mock_audit.return_value = MagicMock(
                vuln_report=MagicMock(findings=(), skipped=(), fix_suggestions=()),
                guarddog_report=MagicMock(flagged=(), clean=()),
            )

            result = tool_fn(package_name="requests", version="2.31.0")

        mock_audit.assert_called_once_with("requests", "2.31.0")
        assert result["type"] == "package_audit"
        assert result["package_name"] == "requests"
        assert result["ecosystem"] == "pypi"


# ── Tool: owb_audit_licenses ────────────────────────────────────────────


class TestAuditLicensesTool:
    def test_returns_error_when_module_unavailable(self) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_audit_licenses")

        with patch.dict("sys.modules", {"open_workspace_builder.security.license_audit": None}):
            # Force ImportError by patching the import inside the tool
            original_import = __builtins__.__import__ if hasattr(__builtins__, '__import__') else __import__

            def mock_import(name, *args, **kwargs):
                if name == "open_workspace_builder.security.license_audit":
                    raise ImportError("not available")
                return original_import(name, *args, **kwargs)

            with patch("builtins.__import__", side_effect=mock_import):
                result = tool_fn()

        assert result["type"] == "license_audit"
        assert "error" in result

    def test_returns_error_when_policy_not_found(self, tmp_path: Path) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_audit_licenses")

        result = tool_fn(project_path=str(tmp_path))
        assert "error" in result
        assert "not found" in result["error"]

    def test_returns_report_when_policy_found(self, tmp_path: Path) -> None:
        # Create a policy file
        policies_dir = tmp_path / "content" / "policies"
        policies_dir.mkdir(parents=True)
        (policies_dir / "allowed-licenses.md").write_text("# Policy", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_audit_licenses")

        mock_report = {"type": "license_audit", "summary": {"total": 0}}
        with patch(
            "open_workspace_builder.security.license_audit.audit_licenses"
        ), patch(
            "open_workspace_builder.security.license_audit.format_license_report",
            return_value=mock_report,
        ):
            result = tool_fn(project_path=str(tmp_path))

        assert result["type"] == "license_audit"
        assert "error" not in result


# ── Batch guardrails ────────────────────────────────────────────────────


class TestBatchGuardrails:
    def test_batch_10_plus_requires_confirmation(self, tmp_path: Path) -> None:
        """10+ items triggers batch confirmation for L1+L2."""
        for i in range(12):
            (tmp_path / f"file{i}.md").write_text(f"content {i}", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_security_scan")

        result = tool_fn(path=str(tmp_path))

        assert result["requires_confirmation"] is True
        assert "12 items" in result["message"]

    def test_single_item_skips_batch_confirmation(self, tmp_path: Path) -> None:
        """Single file skips batch confirmation."""
        test_file = tmp_path / "test.md"
        test_file.write_text("content", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_security_scan")

        with patch("open_workspace_builder.security.scanner.Scanner") as MockScanner:
            mock_scanner = MockScanner.return_value
            mock_scanner.scan_file.return_value = MagicMock(
                file_path=str(test_file), verdict="clean", flags=[]
            )

            result = tool_fn(path=str(test_file))

        assert "requires_confirmation" not in result

    def test_under_10_items_no_batch_confirmation(self, tmp_path: Path) -> None:
        """Under 10 items does not trigger batch confirmation."""
        for i in range(5):
            (tmp_path / f"file{i}.md").write_text(f"content {i}", encoding="utf-8")

        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()
            tool_fn = _extract_tool(mock_fmcp, "owb_security_scan")

        with patch("open_workspace_builder.security.scanner.Scanner") as MockScanner:
            mock_scanner = MockScanner.return_value
            mock_scanner.scan_directory.return_value = MagicMock(
                directory=str(tmp_path),
                verdicts=[],
                summary={"clean": 5, "flagged": 0, "malicious": 0, "error": 0},
            )

            result = tool_fn(path=str(tmp_path))

        assert "requires_confirmation" not in result


# ── Server startup ──────────────────────────────────────────────────────


class TestServerStartup:
    def test_create_server_registers_four_tools(self) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import create_server

            create_server()

        # FastMCP.tool() is used as a decorator 4 times
        assert mock_fmcp.return_value.tool.call_count == 4

    def test_run_server_calls_run(self) -> None:
        with patch("open_workspace_builder.mcp_server.FastMCP") as mock_fmcp:
            from open_workspace_builder.mcp_server import run_server

            run_server()

        mock_fmcp.return_value.run.assert_called_once()


# ── Utility functions ────────────────────────────────────────────────────


class TestUtilities:
    def test_count_scannable_single_file(self, tmp_path: Path) -> None:
        from open_workspace_builder.mcp_server import _count_scannable_items

        f = tmp_path / "test.md"
        f.write_text("content", encoding="utf-8")
        assert _count_scannable_items(f) == 1

    def test_count_scannable_directory(self, tmp_path: Path) -> None:
        from open_workspace_builder.mcp_server import _count_scannable_items

        for i in range(5):
            (tmp_path / f"file{i}.md").write_text("content", encoding="utf-8")
        (tmp_path / "not_md.txt").write_text("ignored", encoding="utf-8")
        assert _count_scannable_items(tmp_path) == 5

    def test_find_policy_file_found(self, tmp_path: Path) -> None:
        from open_workspace_builder.mcp_server import _find_policy_file

        policies_dir = tmp_path / "content" / "policies"
        policies_dir.mkdir(parents=True)
        (policies_dir / "allowed-licenses.md").write_text("policy", encoding="utf-8")

        result = _find_policy_file(str(tmp_path))
        assert result is not None
        assert result.name == "allowed-licenses.md"

    def test_find_policy_file_not_found(self, tmp_path: Path) -> None:
        from open_workspace_builder.mcp_server import _find_policy_file

        result = _find_policy_file(str(tmp_path))
        assert result is None


# ── Helpers ──────────────────────────────────────────────────────────────


def _extract_tool(mock_fmcp: MagicMock, tool_name: str) -> Any:
    """Extract a registered tool function from the mock FastMCP instance.

    FastMCP.tool() is used as a decorator: @mcp.tool(). The mock records
    each call to tool() and the subsequent call to the returned decorator
    with the actual function.
    """
    mock_server = mock_fmcp.return_value
    # Each @mcp.tool() call returns a decorator, which is then called with the fn
    for call in mock_server.tool.return_value.call_args_list:
        fn = call[0][0] if call[0] else None
        if fn and fn.__name__ == tool_name:
            return fn

    # If the mock pattern is different, try extracting from method_calls
    for name, args, kwargs in mock_server.method_calls:
        if name == "tool().return_value" or name == "tool().__call__":
            continue

    # Alternative: FastMCP.tool() returns a decorator that wraps the function.
    # With MagicMock, the decorator is a mock that was called with the function.
    # Let's check all calls to the tool() return value.
    decorator_mock = mock_server.tool.return_value
    for call_args in decorator_mock.call_args_list:
        fn = call_args[0][0] if call_args[0] else None
        if fn and hasattr(fn, "__name__") and fn.__name__ == tool_name:
            return fn

    raise ValueError(
        f"Tool {tool_name!r} not found in mock registrations. "
        f"Registered calls: {decorator_mock.call_args_list}"
    )
