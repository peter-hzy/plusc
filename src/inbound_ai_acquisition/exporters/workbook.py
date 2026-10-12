"""单表客户结果；完整草稿位于同表下方，审计数据只保留在数据库。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ..application.research import research_status
from ..storage.database import Database

BUSINESS_SHEET = "客户结果"
HEADERS = ["公司", "市场/客群", "为什么值得联系", "找谁", "联系入口", "开发信", "当前结果/下一步"]


def _route_kind(email: str, linkedin: str, contact_role: str = "primary", recipient_kind: str = "unknown") -> str:
    if email:
        return {"person": "个人业务邮箱", "department": "部门邮箱", "company": "公司邮箱"}.get(
            recipient_kind, "企业转交邮箱" if contact_role == "handoff" else "邮箱归属待确认"
        )
    return "LinkedIn" if linkedin else "联系入口待研究"


def _safe(cell: Any, value: Any) -> None:
    # 外部网页和邮件中的等号不得变成Excel公式。
    cell.value = str(value or "")
    cell.data_type = "s"


def export_workbook(db: Database, output: Path, run_id: str | None = None) -> dict[str, Any]:
    from openpyxl import Workbook, load_workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo

    runs = [run_id] if run_id else [r["run_id"] for r in db.query("SELECT run_id FROM runs ORDER BY created_at")]
    review = [item for rid in runs for item in research_status(db, rid)["review"]]
    review.sort(
        key=lambda item: (
            item["company_preview"].get("fit_status") != "priority_chat",
            item["company_preview"]["name_original"].casefold(),
        )
    )
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = BUSINESS_SHEET
    sheet.append(HEADERS)
    sheet.freeze_panes = "B2"
    sheet.sheet_view.showGridLines = False
    widths = [26, 23, 48, 30, 38, 16, 42]
    for i, width in enumerate(widths, 1):
        sheet.column_dimensions[sheet.cell(1, i).column_letter].width = width
    for cell in sheet[1]:
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.font = Font(bold=True, color="FFFFFF", size=11)
    detail_row = len(review) + 5
    statuses = {
        "review_ready": "待审核",
        "approved": "已批准，待执行",
        "sent": "已记录发送",
        "stopped": "停止联系",
        "draft": "待完善",
    }
    for index, item in enumerate(review, 2):
        company = item["company_preview"]
        contacts = {r["contact_id"]: r for r in item["contact_previews"]}
        drafts = item["drafts"]
        contact = contacts.get(drafts[-1]["contact_id"]) if drafts else None
        contact = contact or max(contacts.values(), key=lambda row: (
            row.get("route_purpose") != "unsuitable",
            row.get("identity_status") in {"supported", "verified"},
            bool(row.get("public_email") or row.get("linkedin_url")),
            {"R1": 3, "R2": 2, "R3": 1}.get(row.get("route_grade"), 0),
        ), default={})
        contract = {}
        if drafts:
            rows = db.query("SELECT contract_json FROM draft_contracts WHERE draft_id=?", (drafts[-1]["draft_id"],))
            contract = json.loads(rows[0]["contract_json"]) if rows else {}
        role = contact.get("contact_role", "")
        email, linkedin = contact.get("public_email", ""), contact.get("linkedin_url", "")
        contact_page = next(
            (
                e["source_url"]
                for e in item["evidence"]
                if e["entity_type"] == "contact"
                and e["entity_id"] == contact.get("contact_id")
                and e["purpose"] == "contact_route"
                and e["access_status"] == "accessible"
                and not e["conflicts"]
                and re.match(r"^https?://", e["source_url"])
            ),
            "",
        )
        kind = _route_kind(email, linkedin, role, contract.get("recipient_kind", "unknown"))
        recipient = contract.get("recipient") or email or linkedin
        if not recipient and contact_page:
            kind = "官网联系页（转交路径待确认）"
        route = (recipient or contact_page or "未找到") + "\n" + kind
        route += "\n" + {
            "R1": "具名职责入口（以审核状态为准）",
            "R2": "部门职责入口（以审核状态为准）",
            "R3": "通用转交，商务用途待确认",
            "R0": "入口缺失",
        }.get(contact.get("route_grade", "R3"), "入口待核验")
        if contact.get("route_purpose") == "unsuitable":
            route += "；不适合本次业务联系"
        if role == "handoff":
            who = contact.get("role_scope") or "部门/公司转交入口"
        else:
            who = " / ".join(str(contact.get(k, "")) for k in ("full_name", "title")).strip(" /") or "负责人待研究"
        state = item["decision_state"]
        if drafts:
            state += "；" + " / ".join(dict.fromkeys(statuses.get(d["status"], d["status"]) for d in drafts))
        else:
            state += "；" + ("核准产品匹配；需触达时再准备文案" if email or linkedin else "核实企业转交路径")
        if (email or linkedin) and contract.get("recipient_kind", "unknown") == "unknown":
            state += "；" + ("收件职责待确认" if role == "handoff" else "地址归属未确认")
        if drafts and not contract.get("consent"):
            state += "；触达依据待审核"
        if drafts and not contract.get("product_approved_by"):
            state += "；我方产品能力待批准"
        gaps = [g["business_impact"] for g in item["gaps"] if g["status"] == "open"]
        if gaps:
            state += "；" + "；".join(gaps)
        if company.get("risk_notes"):
            state += "；" + company["risk_notes"]
        if item.get("replies"):
            replies = item["replies"]
            latest = {r["contact_id"]: r for r in reversed(replies)}.values()
            state = (
                "\n".join(
                    "回复："
                    + r["category"]
                    + "；已确认："
                    + (r["confirmed_needs"] or "无")
                    + "；待确认："
                    + (r["unknown_needs"] or "无")
                    + "；下一步："
                    + (r["next_action"] or "人工处理回复")
                    + ("；需人工接管" if r["needs_human_takeover"] else "")
                    + ("；该联系人停止联系" if r["do_not_contact"] else "")
                    for r in latest
                )
                + "\n研究/草稿记录："
                + state
            )
        elif company.get("next_action"):
            state += "；" + company["next_action"]
        reason = company["fit_reason"]
        if company.get("qualification_policy") == "service_fit_v1":
            reason = company["business_signal"] + "\n服务关联：" + company["service_fit"]
        elif company.get("qualification_path") in {"expansion", "channel"}:
            reason = ("扩展假设" if company["qualification_path"] == "expansion" else "渠道合作假设") + "：" + reason
        if company.get("cooperation_hypothesis"):
            reason += "\n合作假设：" + company["cooperation_hypothesis"]
        if company.get("counter_evidence"):
            reason += "\n限制：" + company["counter_evidence"]
        values = [
            company["name_original"],
            f"{ {'AU': '澳洲', 'NZ': '新西兰'}.get(company['country'], company['country']) } / "
            + {
                "travel_agency": "旅行社",
                "tour_operator": "旅游运营商",
                "dmc": "目的地管理公司",
                "mice": "会奖旅游",
            }.get(company["segment"], company["segment"]),
            reason,
            who,
            route,
            "查看文案" if drafts else "尚未准备",
            state,
        ]
        for col, value in enumerate(values, 1):
            _safe(sheet.cell(index, col), value)
        contact_link = ("mailto:" + email) if email else linkedin or contact_page
        if contact_link:
            sheet.cell(index, 5).hyperlink = contact_link
            sheet.cell(index, 5).font = Font(color="0563C1", underline="single")
        url = company.get("website", "")
        if re.match(r"^https?://", url):
            sheet.cell(index, 1).hyperlink = url
            sheet.cell(index, 1).font = Font(color="0563C1", underline="single")
        sheet.row_dimensions[index].height = min(
            409,
            max(
                56,
                max(
                    sum(
                        max(1, (sum(2 if ord(c) > 255 else 1 for c in line) + int(width * 0.65) - 1)
                            // int(width * 0.65))
                        for line in str(value).split("\n")
                    )
                    for value, width in zip(values, widths, strict=True)
                )
                * 18 + 24,
            ),
        )
        if drafts:
            # 使用固定客户ID命名区域；主表排序时链接随单元格保留。
            anchor = detail_row
            sheet.cell(index, 6).hyperlink = f"#'{BUSINESS_SHEET}'!A{anchor}"
            sheet.cell(index, 6).font = Font(color="0563C1", underline="single")
            for draft in drafts:
                dr_contract = db.query(
                    "SELECT contract_json FROM draft_contracts WHERE draft_id=?", (draft["draft_id"],)
                )
                metadata = json.loads(dr_contract[0]["contract_json"]) if dr_contract else {}
                fields = [
                    ("客户", company["name_original"] + " / " + company["company_id"]),
                    ("渠道/收件人", draft["channel"] + " / " + metadata.get("recipient", "未确认")),
                    ("主题", draft["subject"]),
                ]
                # 分行呈现长邮件，避免Excel单行高度上限造成截断。
                fields += [("正文" if n == 0 else "", part) for n, part in enumerate(draft["body"].splitlines())]
                fields += [("状态", statuses.get(draft["status"], draft["status"])), ("返回名单", "返回客户列表")]
                for label, value in fields:
                    _safe(sheet.cell(detail_row, 1), label)
                    sheet.merge_cells(start_row=detail_row, start_column=2, end_row=detail_row, end_column=7)
                    _safe(sheet.cell(detail_row, 2), value)
                    sheet.row_dimensions[detail_row].height = max(25, (len(str(value)) // 130 + 1) * 18)
                    if label == "返回名单":
                        sheet.cell(detail_row, 2).hyperlink = f"#'{BUSINESS_SHEET}'!A1"
                    detail_row += 1
                detail_row += 2
    end = len(review) + 1
    if review:
        table = Table(displayName="CustomerResults", ref=f"A1:G{end}")
        table.tableStyleInfo = TableStyleInfo(name="TableStyleMedium2", showRowStripes=True)
        sheet.add_table(table)
    sheet.auto_filter.ref = f"A1:G{max(1, end)}"
    for row in sheet:
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    sheet.page_setup.orientation = "landscape"
    sheet.page_setup.paperSize = sheet.PAPERSIZE_A3
    sheet.page_setup.fitToWidth = 1
    sheet.page_setup.fitToHeight = 0
    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    reopened = load_workbook(output, read_only=True)
    if reopened.sheetnames != [BUSINESS_SHEET] or reopened.active.max_column != 7:
        raise ValueError("Excel回读结构不符合单表7列合同")
    reopened.close()
    return {"status": "succeeded", "output": str(output), "sheets": 1, "companies": len(review)}
