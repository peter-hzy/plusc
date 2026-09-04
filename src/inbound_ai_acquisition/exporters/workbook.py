"""使用 openpyxl 生成可人工审阅的 Excel。"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from ..storage.database import Database

SHEETS = {
    "RunSummary": "runs",
    "Companies": "companies",
    "Contacts": "contacts",
    "Evidence": "evidence",
    "Claims": "claims",
    "ResearchGaps": "research_gaps",
    "Drafts": "drafts",
    "Approvals": "approvals",
    "Replies": "replies",
    "StopRules": "stop_rules",
    "DuplicateReview": "duplicate_candidates",
    "SourcePerformance": "source_runs",
}


def export_workbook(db: Database, output: Path, run_id: str | None = None) -> dict[str, Any]:
    try:
        from openpyxl import Workbook, load_workbook
        from openpyxl.styles import Alignment, Font, PatternFill
    except ImportError as exc:
        raise ValidationError("缺少 Excel 依赖，请安装 pip install -e .[excel]") from exc

    workbook = Workbook()
    workbook.remove(workbook.active)
    with closing(db.connect()) as connection:
        for sheet_name, table in SHEETS.items():
            sheet = workbook.create_sheet(sheet_name)
            columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
            sheet.append(columns)
            run_filter = run_id and "run_id" in columns
            rows = connection.execute(
                f"SELECT * FROM {table}" + (" WHERE run_id=?" if run_filter else ""),
                (run_id,) if run_filter else (),
            ).fetchall()
            for row in rows:
                sheet.append([row[column] for column in columns])
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for cell in sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E78")
                cell.alignment = Alignment(vertical="center")
            for column_cells in sheet.columns:
                values = [str(cell.value or "") for cell in list(column_cells)[:200]]
                width = min(60, max(10, max(map(len, values), default=10) + 2))
                sheet.column_dimensions[column_cells[0].column_letter].width = width
                for cell in column_cells[1:]:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
                    if isinstance(cell.value, str) and cell.value.startswith(("http://", "https://")):
                        cell.hyperlink = cell.value
                        cell.style = "Hyperlink"
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    reopened = load_workbook(output, read_only=True, data_only=False)
    if set(reopened.sheetnames) != set(SHEETS):
        raise ValidationError("Excel 回读验证失败：工作表不完整")
    reopened.close()
    return {"status": "succeeded", "output": str(output), "sheets": len(SHEETS)}
