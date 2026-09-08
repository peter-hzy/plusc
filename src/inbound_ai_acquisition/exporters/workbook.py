"""使用 openpyxl 生成可人工审阅的 Excel。"""

from __future__ import annotations

from contextlib import closing
from pathlib import Path
from typing import Any

from ..application.discovery import discovery_coverage
from ..errors import ValidationError
from ..storage.database import Database

BUSINESS_SHEET = "LeadReview"
COVERAGE_SHEET = "DiscoveryCoverage"


def _preview_claims(connection: Any, entity_type: str, entity_id: str, row: Any) -> tuple[dict[str, Any], str]:
    """在审阅页展示待批值，但不把它们写成正式字段。"""
    preview = dict(row)
    claims = connection.execute(
        "SELECT field_name,proposed_value,status FROM claims WHERE entity_type=? AND entity_id=? ORDER BY created_at",
        (entity_type, entity_id),
    ).fetchall()
    for claim in claims:
        if claim["status"] in {"proposed", "accepted"}:
            preview[claim["field_name"]] = claim["proposed_value"]
    statuses = {claim["status"] for claim in claims}
    state = "待人工批准" if "proposed" in statuses else "已批准" if statuses == {"accepted"} else "部分已处理"
    return preview, state


def _route_kind(email: str, linkedin: str, contact_role: str = "primary") -> str:
    if email:
        local = email.split("@", 1)[0].lower()
        generic_locals = {
            "info", "sales", "support", "hello", "contact", "enquiries", "bookings",
            "tailormade", "partnerships", "product", "trade", "groups",
        }
        if contact_role == "handoff" or local in generic_locals:
            return "LinkedIn负责人 + 公开企业邮箱（非个人邮箱）" if linkedin else "公开企业邮箱（非个人邮箱）"
        return "公开个人邮箱 + LinkedIn" if linkedin else "公开个人邮箱"
    return "LinkedIn负责人" if linkedin else "公开转交入口"


def _priority_label(status: str) -> str:
    return {
        "priority_chat": "A｜优先联系",
        "chat_candidate": "B｜可以联系",
        "nurture": "C｜长期培育",
        "research_needed": "待继续研究",
        "not_fit": "不适配",
        "do_not_contact": "禁止联系",
    }.get(status, status)


def _fit_gate_label(field: str, value: str) -> str:
    labels = {
        "source_market_role": {
            "outbound_seller": "确认：当地出境客源方",
            "unclear": "待确认",
            "not_source_market": "非客源方",
        },
        "china_product_signal": {"direct": "直接销售中国产品", "adjacent": "亚洲长线可适配", "none": "无相关产品"},
        "ground_partner_route": {
            "external_partner_possible": "有外部地接合作路径",
            "unclear": "合作方式未知",
            "in_house": "疑似自营地接",
        },
        "competitive_position": {
            "potential_buyer": "潜在合作方",
            "mixed": "合作与竞争并存",
            "competitor": "同行竞争",
            "unknown": "关系待确认",
        },
    }
    return labels.get(field, {}).get(value, value or "待确认")


SHEETS = {
    "RunSummary": "runs",
    "CandidatePool": "candidates",
    "SourcePlan": "source_plan_entries",
    "CandidateSources": "candidate_sources",
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
        review_sheet = workbook.create_sheet(BUSINESS_SHEET)
        review_headers = [
            "优先级",
            "公司",
            "官网",
            "资料状态",
            "买方角色",
            "中国产品",
            "地接合作空间",
            "竞争关系",
            "联系人及渠道",
            "判断依据",
            "风险与下一步",
        ]
        review_sheet.append(review_headers)
        company_rows = connection.execute(
            "SELECT c.* FROM companies c "
            "LEFT JOIN claims priority_claim ON priority_claim.entity_type='company' "
            "AND priority_claim.entity_id=c.company_id AND priority_claim.field_name='fit_status' "
            "AND priority_claim.status='proposed' "
            + ("WHERE c.run_id=? " if run_id else "")
            + "ORDER BY CASE COALESCE(priority_claim.proposed_value,c.fit_status) "
            "WHEN 'priority_chat' THEN 0 WHEN 'chat_candidate' THEN 1 WHEN 'nurture' THEN 2 "
            "WHEN 'research_needed' THEN 3 WHEN 'not_fit' THEN 4 WHEN 'do_not_contact' THEN 5 ELSE 6 END, "
            "c.name_original",
            (run_id,) if run_id else (),
        ).fetchall()
        for company in company_rows:
            company_view, decision_state = _preview_claims(connection, "company", company["company_id"], company)
            contact_row = connection.execute(
                "SELECT * FROM contacts WHERE company_id=? ORDER BY CASE contact_role WHEN 'primary' THEN 0 WHEN 'handoff' THEN 1 ELSE 2 END LIMIT 1",
                (company["company_id"],),
            ).fetchone()
            contact = None
            if contact_row:
                contact, contact_state = _preview_claims(connection, "contact", contact_row["contact_id"], contact_row)
                if contact_state == "待人工批准":
                    decision_state = "待人工批准"
            gaps = connection.execute(
                "SELECT field_name,business_impact FROM research_gaps WHERE entity_type='company' AND entity_id=? AND status='open'",
                (company["company_id"],),
            ).fetchall()
            drafts = connection.execute(
                "SELECT channel,subject,body,status FROM drafts WHERE company_id=? ORDER BY channel",
                (company["company_id"],),
            ).fetchall()
            draft_by_channel = {row["channel"]: row for row in drafts}
            gap_text = "\n".join(f"{row['field_name']}: {row['business_impact']}" for row in gaps) or "无阻塞缺口"
            email_draft = draft_by_channel.get("email")
            linkedin_draft = draft_by_channel.get("linkedin")
            next_step = (
                "先审核并批准资料"
                if decision_state == "待人工批准"
                else "人工审核两条草稿"
                if email_draft and linkedin_draft
                else "生成 Email 和 LinkedIn 草稿"
                if contact
                else "继续负责人研究"
            )
            review_sheet.append(
                [
                    _priority_label(company_view["fit_status"]),
                    company_view["name_original"],
                    company_view["website"],
                    decision_state,
                    _fit_gate_label("source_market_role", company_view.get("source_market_role", "")),
                    _fit_gate_label("china_product_signal", company_view.get("china_product_signal", "")),
                    _fit_gate_label("ground_partner_route", company_view.get("ground_partner_route", "")),
                    _fit_gate_label("competitive_position", company_view.get("competitive_position", "")),
                    (
                        f"{contact['full_name']} / {contact['title']}\n"
                        f"{_route_kind(contact['public_email'], contact['linkedin_url'], contact['contact_role'])}\n"
                        f"{contact['public_email']}\n{contact['linkedin_url']}"
                        if contact
                        else ""
                    ),
                    company_view["fit_reason"],
                    f"风险：{company_view['risk_notes'] or '未记录'}\n缺口：{gap_text}\n下一步：{next_step}",
                ]
            )
        review_sheet.freeze_panes = "B2"
        review_sheet.auto_filter.ref = f"A1:K{len(company_rows) + 1}"
        review_sheet.sheet_view.showGridLines = False
        review_sheet.page_setup.orientation = "landscape"
        review_sheet.page_setup.fitToWidth = 1
        review_sheet.page_setup.fitToHeight = 0
        review_sheet.row_dimensions[1].height = 34
        widths = [15, 23, 29, 15, 20, 18, 22, 18, 38, 48, 46]
        for index, width in enumerate(widths, 1):
            review_sheet.column_dimensions[review_sheet.cell(1, index).column_letter].width = width
        for cell in review_sheet[1]:
            cell.font = Font(bold=True, color="FFFFFF")
            cell.fill = PatternFill("solid", fgColor="1F4E78")
            cell.alignment = Alignment(horizontal="center", vertical="center")
        for row in review_sheet.iter_rows(min_row=2, max_row=len(company_rows) + 1):
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)
            review_sheet.row_dimensions[row[0].row].height = 115
            if row[3].value == "待人工批准":
                row[3].fill = PatternFill("solid", fgColor="FFF2CC")
            priority_colors = {
                "A｜优先联系": "E2F0D9",
                "B｜可以联系": "FFF2CC",
                "C｜长期培育": "D9EAF7",
            }
            if row[0].value in priority_colors:
                row[0].fill = PatternFill("solid", fgColor=priority_colors[row[0].value])
            for column in (3,):
                cell = row[column - 1]
                if isinstance(cell.value, str) and cell.value.startswith(("http://", "https://")):
                    cell.hyperlink = cell.value
                    cell.style = "Hyperlink"
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
        if run_id:
            coverage = discovery_coverage(db, run_id)
            coverage_sheet = workbook.create_sheet(COVERAGE_SHEET)
            coverage_sheet.append(["指标", "结果", "说明"])
            policy = coverage["policy"]
            coverage_sheet.append(
                ["正式目标", coverage["target_count"], f"本批次正式基线为{policy['production_min_target']}家"]
            )
            coverage_sheet.append(["候选公司", coverage["candidate_count"], "包含未入选候选"])
            coverage_sheet.append(["已选公司", coverage["selected_count"], "不代表已经证明采购意愿"])
            coverage_sheet.append(
                ["建议候选池", coverage["recommended_pool"], f"本批次为目标的{policy['candidate_pool_multiplier']:g}倍"]
            )
            coverage_sheet.append(
                ["来源类别", coverage["source_category_count"], f"本批次基线为{policy['min_source_categories']}类"]
            )
            coverage_sheet.append(
                ["正式批次可结束", "是" if coverage["production_ready"] else "否", "不使用客户类型硬配额"]
            )
            coverage_sheet.append([])
            coverage_sheet.append(["补搜提醒", "", ""])
            for warning in coverage["warnings"]:
                coverage_sheet.append([warning, "", ""])
            coverage_sheet.append([])
            coverage_sheet.append(["来源类别", "候选", "独有", "重叠", "入选", "来源运行"])
            for item in coverage["source_performance"]:
                coverage_sheet.append(
                    [
                        item["source_category"],
                        item["candidates"],
                        item["unique_candidates"],
                        item["overlap_candidates"],
                        item["selected"],
                        item["source_runs"],
                    ]
                )
            coverage_sheet.freeze_panes = "A2"
            coverage_sheet.column_dimensions["A"].width = 72
            for column in ("B", "C", "D", "E", "F"):
                coverage_sheet.column_dimensions[column].width = 18
            for cell in coverage_sheet[1]:
                cell.font = Font(bold=True, color="FFFFFF")
                cell.fill = PatternFill("solid", fgColor="1F4E78")
            for row in coverage_sheet.iter_rows():
                for cell in row:
                    cell.alignment = Alignment(vertical="top", wrap_text=True)
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
    expected_sheets = set(SHEETS) | {BUSINESS_SHEET} | ({COVERAGE_SHEET} if run_id else set())
    if set(reopened.sheetnames) != expected_sheets:
        raise ValidationError("Excel 回读验证失败：工作表不完整")
    reopened.close()
    return {"status": "succeeded", "output": str(output), "sheets": len(expected_sheets)}
