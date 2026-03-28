"""Excel export for token consumption reports using xlsxwriter."""

from __future__ import annotations

from open_workspace_builder.tokens.models import TokenReport


def export_to_xlsx(report: TokenReport, output_path: str) -> None:
    """Export a TokenReport to an Excel workbook.

    Creates tabs matching the Google Sheets structure:
    Monthly Summary, Daily Detail, Model Mix, Cache Efficiency.
    """
    import xlsxwriter

    workbook = xlsxwriter.Workbook(output_path)
    bold = workbook.add_format({"bold": True})
    money = workbook.add_format({"num_format": "$#,##0.00"})
    number = workbook.add_format({"num_format": "#,##0"})
    pct = workbook.add_format({"num_format": "0.0%"})

    _write_monthly_sheet(workbook, report, bold, money, number)
    _write_daily_sheet(workbook, report, bold, money, number)
    _write_model_sheet(workbook, report, bold, money, number)
    _write_cache_sheet(workbook, report, bold, money, number, pct)

    workbook.close()


def _write_monthly_sheet(
    workbook: object, report: TokenReport, bold: object, money: object, number: object
) -> None:
    ws = workbook.add_worksheet("Monthly Summary")  # type: ignore[union-attr]
    headers = [
        "Period Start", "Period End", "Sessions", "Messages",
        "Input Tokens", "Output Tokens", "Cache Create", "Cache Read",
        "Input Cost", "Output Cost", "Cache Write Cost", "Cache Read Cost",
        "Total Cost",
    ]
    for col, h in enumerate(headers):
        ws.write(0, col, h, bold)

    ws.write(1, 0, report.period_start)
    ws.write(1, 1, report.period_end)
    ws.write(1, 2, report.session_count, number)
    ws.write(1, 3, report.message_count, number)
    ws.write(1, 4, report.total_input, number)
    ws.write(1, 5, report.total_output, number)
    ws.write(1, 6, report.total_cache_creation, number)
    ws.write(1, 7, report.total_cache_read, number)
    ws.write(1, 8, report.total_cost.input_cost, money)
    ws.write(1, 9, report.total_cost.output_cost, money)
    ws.write(1, 10, report.total_cost.cache_write_cost, money)
    ws.write(1, 11, report.total_cost.cache_read_cost, money)
    ws.write(1, 12, report.total_cost.total, money)

    ws.set_column(0, 1, 14)
    ws.set_column(4, 7, 16)
    ws.set_column(8, 12, 14)


def _write_daily_sheet(
    workbook: object, report: TokenReport, bold: object, money: object, number: object
) -> None:
    ws = workbook.add_worksheet("Daily Detail")  # type: ignore[union-attr]
    headers = ["Date", "Input Tokens", "Output Tokens", "Cache Create", "Cache Read", "Total Cost"]
    for col, h in enumerate(headers):
        ws.write(0, col, h, bold)

    for row_idx, d in enumerate(report.by_day, start=1):
        ws.write(row_idx, 0, d.date)
        ws.write(row_idx, 1, d.input_tokens, number)
        ws.write(row_idx, 2, d.output_tokens, number)
        ws.write(row_idx, 3, d.cache_creation_tokens, number)
        ws.write(row_idx, 4, d.cache_read_tokens, number)
        ws.write(row_idx, 5, d.cost.total, money)

    ws.set_column(0, 0, 12)
    ws.set_column(1, 4, 16)
    ws.set_column(5, 5, 14)


def _write_model_sheet(
    workbook: object, report: TokenReport, bold: object, money: object, number: object
) -> None:
    ws = workbook.add_worksheet("Model Mix")  # type: ignore[union-attr]
    headers = ["Model", "Input Tokens", "Output Tokens", "Cache Create", "Cache Read", "Total Cost"]
    for col, h in enumerate(headers):
        ws.write(0, col, h, bold)

    for row_idx, m in enumerate(report.by_model, start=1):
        ws.write(row_idx, 0, m.model)
        ws.write(row_idx, 1, m.input_tokens, number)
        ws.write(row_idx, 2, m.output_tokens, number)
        ws.write(row_idx, 3, m.cache_creation_tokens, number)
        ws.write(row_idx, 4, m.cache_read_tokens, number)
        ws.write(row_idx, 5, m.cost.total, money)

    ws.set_column(0, 0, 30)
    ws.set_column(1, 4, 16)
    ws.set_column(5, 5, 14)


def _write_cache_sheet(
    workbook: object,
    report: TokenReport,
    bold: object,
    money: object,
    number: object,
    pct: object,
) -> None:
    ws = workbook.add_worksheet("Cache Efficiency")  # type: ignore[union-attr]
    headers = [
        "Period", "Cache Hit Ratio", "Cost Reduction %",
        "Total Reads", "Total Writes", "Total Input",
    ]
    for col, h in enumerate(headers):
        ws.write(0, col, h, bold)

    eff = report.cache_efficiency
    ws.write(1, 0, f"{report.period_start} to {report.period_end}")
    ws.write(1, 1, eff.cache_hit_ratio, pct)
    ws.write(1, 2, eff.cost_reduction_pct, pct)
    ws.write(1, 3, eff.total_cache_reads, number)
    ws.write(1, 4, eff.total_cache_writes, number)
    ws.write(1, 5, eff.total_input_tokens, number)

    ws.set_column(0, 0, 28)
    ws.set_column(1, 2, 16)
    ws.set_column(3, 5, 16)
