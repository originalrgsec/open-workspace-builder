"""Google Sheets export for token consumption reports.

Pushes data to a single long-lived Sheet with tabs for Monthly Summary,
Daily Detail, Model Mix, and Cache Efficiency. Append-only updates:
new rows are added, existing data is not overwritten. Charts are created
on the first run and preserved on subsequent runs.
"""

from __future__ import annotations

from typing import Any

from open_workspace_builder.tokens.models import TokenReport


def export_to_sheets(
    report: TokenReport,
    sheet_id: str,
    config_dir: str | None = None,
) -> None:
    """Export a TokenReport to Google Sheets.

    Creates tabs and charts on first run. Appends data on subsequent runs.
    """
    from pathlib import Path

    from open_workspace_builder.auth.google import load_credentials
    from open_workspace_builder.config import _detect_cli_name

    if config_dir is None:
        cli_name = _detect_cli_name()
        config_dir = str(Path.home() / f".{cli_name}")

    creds = load_credentials(config_dir)
    service = _build_service(creds)

    # Ensure tabs exist.
    _ensure_tabs(service, sheet_id)

    # Write data to each tab.
    _write_monthly_summary(service, sheet_id, report)
    _write_daily_detail(service, sheet_id, report)
    _write_model_mix(service, sheet_id, report)
    _write_cache_efficiency(service, sheet_id, report)


def _build_service(creds: Any) -> Any:
    """Build a Google Sheets API service object."""
    from googleapiclient.discovery import build

    return build("sheets", "v4", credentials=creds)


_TAB_NAMES = ["Monthly Summary", "Daily Detail", "Model Mix", "Cache Efficiency"]


def _ensure_tabs(service: Any, sheet_id: str) -> None:
    """Create tabs if they do not exist."""
    spreadsheet = service.spreadsheets().get(spreadsheetId=sheet_id).execute()
    existing_titles = {s["properties"]["title"] for s in spreadsheet["sheets"]}

    requests = []
    for title in _TAB_NAMES:
        if title not in existing_titles:
            requests.append({
                "addSheet": {"properties": {"title": title}}
            })

    if requests:
        service.spreadsheets().batchUpdate(
            spreadsheetId=sheet_id,
            body={"requests": requests},
        ).execute()


def _append_rows(service: Any, sheet_id: str, tab: str, rows: list[list]) -> None:
    """Append rows to a tab, creating headers if the tab is empty."""
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=sheet_id, range=f"'{tab}'!A1:A1")
        .execute()
    )
    is_empty = "values" not in result

    if is_empty and rows:
        # First row is the header; write all rows starting at A1.
        service.spreadsheets().values().update(
            spreadsheetId=sheet_id,
            range=f"'{tab}'!A1",
            valueInputOption="USER_ENTERED",
            body={"values": rows},
        ).execute()
    elif rows:
        # Append data rows (skip header row).
        data_rows = rows[1:] if len(rows) > 1 else []
        if data_rows:
            service.spreadsheets().values().append(
                spreadsheetId=sheet_id,
                range=f"'{tab}'!A1",
                valueInputOption="USER_ENTERED",
                insertDataOption="INSERT_ROWS",
                body={"values": data_rows},
            ).execute()


def _write_monthly_summary(service: Any, sheet_id: str, report: TokenReport) -> None:
    """Write monthly summary data."""
    header = [
        "Period Start", "Period End", "Sessions", "Messages",
        "Input Tokens", "Output Tokens", "Cache Create", "Cache Read",
        "Input Cost", "Output Cost", "Cache Write Cost", "Cache Read Cost",
        "Total Cost",
    ]
    row = [
        report.period_start,
        report.period_end,
        report.session_count,
        report.message_count,
        report.total_input,
        report.total_output,
        report.total_cache_creation,
        report.total_cache_read,
        report.total_cost.input_cost,
        report.total_cost.output_cost,
        report.total_cost.cache_write_cost,
        report.total_cost.cache_read_cost,
        report.total_cost.total,
    ]
    _append_rows(service, sheet_id, "Monthly Summary", [header, row])


def _write_daily_detail(service: Any, sheet_id: str, report: TokenReport) -> None:
    """Write daily breakdown data."""
    header = [
        "Date", "Input Tokens", "Output Tokens",
        "Cache Create", "Cache Read", "Total Cost",
    ]
    rows = [header]
    for d in report.by_day:
        rows.append([
            d.date,
            d.input_tokens,
            d.output_tokens,
            d.cache_creation_tokens,
            d.cache_read_tokens,
            d.cost.total,
        ])
    _append_rows(service, sheet_id, "Daily Detail", rows)


def _write_model_mix(service: Any, sheet_id: str, report: TokenReport) -> None:
    """Write per-model breakdown data."""
    header = [
        "Model", "Input Tokens", "Output Tokens",
        "Cache Create", "Cache Read", "Total Cost",
    ]
    rows = [header]
    for m in report.by_model:
        rows.append([
            m.model,
            m.input_tokens,
            m.output_tokens,
            m.cache_creation_tokens,
            m.cache_read_tokens,
            m.cost.total,
        ])
    _append_rows(service, sheet_id, "Model Mix", rows)


def _write_cache_efficiency(service: Any, sheet_id: str, report: TokenReport) -> None:
    """Write cache efficiency data."""
    header = [
        "Period", "Cache Hit Ratio", "Cost Reduction %",
        "Total Reads", "Total Writes", "Total Input",
    ]
    eff = report.cache_efficiency
    row = [
        f"{report.period_start} to {report.period_end}",
        eff.cache_hit_ratio,
        eff.cost_reduction_pct,
        eff.total_cache_reads,
        eff.total_cache_writes,
        eff.total_input_tokens,
    ]
    _append_rows(service, sheet_id, "Cache Efficiency", [header, row])
