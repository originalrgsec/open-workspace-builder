"""Tests for Sheets and xlsx export modules."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from open_workspace_builder.tokens.calculator import build_report
from open_workspace_builder.tokens.models import ModelPricing, TokenReport, TokenUsage


def _make_report() -> TokenReport:
    """Build a report with known data for export testing."""
    data = [
        (
            "project-a",
            "session-1",
            [
                TokenUsage(
                    model="claude-opus-4-6",
                    input_tokens=1000,
                    output_tokens=5000,
                    cache_creation_tokens=10000,
                    cache_read_tokens=50000,
                    timestamp="2026-03-28T10:00:00.000Z",
                ),
            ],
        ),
        (
            "project-b",
            "session-2",
            [
                TokenUsage(
                    model="claude-sonnet-4-6",
                    input_tokens=500,
                    output_tokens=2000,
                    cache_creation_tokens=5000,
                    cache_read_tokens=20000,
                    timestamp="2026-03-29T09:00:00.000Z",
                ),
            ],
        ),
    ]
    pricing = {
        "claude-opus-4-6": ModelPricing(5.0, 25.0, 6.25, 0.50),
        "claude-sonnet-4-6": ModelPricing(3.0, 15.0, 3.75, 0.30),
    }
    return build_report(data, pricing)


class TestSheetsExport:
    def test_ensure_tabs_creates_missing(self) -> None:
        from open_workspace_builder.tokens.sheets_export import _ensure_tabs

        mock_service = MagicMock()
        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [{"properties": {"title": "Sheet1"}}]
        }

        _ensure_tabs(mock_service, "test-sheet-id")

        # Should have called batchUpdate to create 4 tabs
        mock_service.spreadsheets().batchUpdate.assert_called_once()
        call_body = mock_service.spreadsheets().batchUpdate.call_args
        requests = call_body[1]["body"]["requests"] if "body" in call_body[1] else []
        assert len(requests) == 4

    def test_ensure_tabs_skips_existing(self) -> None:
        from open_workspace_builder.tokens.sheets_export import _ensure_tabs

        mock_service = MagicMock()
        mock_service.spreadsheets().get().execute.return_value = {
            "sheets": [
                {"properties": {"title": "Monthly Summary"}},
                {"properties": {"title": "Daily Detail"}},
                {"properties": {"title": "Model Mix"}},
                {"properties": {"title": "Cache Efficiency"}},
            ]
        }

        _ensure_tabs(mock_service, "test-sheet-id")

        # Should NOT call batchUpdate since all tabs exist
        mock_service.spreadsheets().batchUpdate.assert_not_called()

    def test_append_rows_writes_to_empty_tab(self) -> None:
        from open_workspace_builder.tokens.sheets_export import _append_rows

        mock_service = MagicMock()
        # Simulate empty tab
        mock_service.spreadsheets().values().get().execute.return_value = {}

        rows = [["Header1", "Header2"], ["data1", "data2"]]
        _append_rows(mock_service, "sheet-id", "Tab", rows)

        # Should use update (not append) for empty tabs
        mock_service.spreadsheets().values().update.assert_called_once()

    def test_append_rows_appends_to_existing_tab(self) -> None:
        from open_workspace_builder.tokens.sheets_export import _append_rows

        mock_service = MagicMock()
        # Simulate non-empty tab
        mock_service.spreadsheets().values().get().execute.return_value = {
            "values": [["existing"]]
        }

        rows = [["Header1", "Header2"], ["data1", "data2"]]
        _append_rows(mock_service, "sheet-id", "Tab", rows)

        # Should use append (not update)
        mock_service.spreadsheets().values().append.assert_called_once()


class TestXlsxExport:
    def test_creates_workbook(self, tmp_path: Path) -> None:
        pytest.importorskip("xlsxwriter")
        from open_workspace_builder.tokens.xlsx_export import export_to_xlsx

        output = tmp_path / "test_report.xlsx"
        report = _make_report()
        export_to_xlsx(report, str(output))

        assert output.exists()
        assert output.stat().st_size > 0

    def test_workbook_has_expected_sheets(self, tmp_path: Path) -> None:
        pytest.importorskip("xlsxwriter")
        from open_workspace_builder.tokens.xlsx_export import export_to_xlsx

        output = tmp_path / "test_report.xlsx"
        report = _make_report()
        export_to_xlsx(report, str(output))

        # xlsxwriter is write-only; verify by checking file was created
        # and is a valid zip (xlsx is a zip format)
        import zipfile

        assert zipfile.is_zipfile(str(output))
        with zipfile.ZipFile(str(output)) as zf:
            names = zf.namelist()
            # xlsx contains sheet XML files
            sheet_files = [n for n in names if n.startswith("xl/worksheets/sheet")]
            assert len(sheet_files) == 4  # 4 tabs

    def test_empty_report(self, tmp_path: Path) -> None:
        pytest.importorskip("xlsxwriter")
        from open_workspace_builder.tokens.xlsx_export import export_to_xlsx

        output = tmp_path / "empty_report.xlsx"
        report = TokenReport(period_start="2026-03-01", period_end="2026-03-31")
        export_to_xlsx(report, str(output))

        assert output.exists()
