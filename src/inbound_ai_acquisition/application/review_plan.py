"""Build a read-only, evidence-aware review plan for an existing research run."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from ..storage.database import Database

SERVICE_FIT_FIELDS = (
    "qualification_policy",
    "fit_basis",
    "business_signal",
    "service_fit",
    "cooperation_hypothesis",
    "counter_evidence",
    "next_action",
)


def _cell(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\r", " ").replace("\n", " ").strip()


def _route_grade(contact: dict[str, Any], claims: list[dict[str, Any]]) -> tuple[str, str]:
    route_claims = [row for row in claims if row["field_name"] == "route_grade"]
    for status in ("accepted", "proposed", "held"):
        matching = [row for row in route_claims if row["status"] == status]
        if matching:
            value = str(matching[-1]["proposed_value"]).upper()
            return (value if value in {"R0", "R1", "R2", "R3"} else "R0", f"claim:{status}")
    match = re.search(r"(?:入口等级[：:]?\s*|\b)(R[0-3])\b", str(contact.get("role_scope", "")), re.I)
    if match:
        return match.group(1).upper(), "legacy_text_pending"
    return "R0", "missing"


def _contract_checks(raw: str | None) -> tuple[str, str]:
    if not raw:
        return "needs_review", "needs_review"
    try:
        contract = json.loads(raw)
    except (TypeError, json.JSONDecodeError):
        return "invalid", "invalid"
    return str(contract.get("fact_check_status", "needs_review")), str(
        contract.get("voice_check_status", "needs_review")
    )


def build_review_plan(db: Database, run_id: str) -> dict[str, Any]:
    """Return a structured review plan without changing the database."""
    runs = db.query("SELECT * FROM runs WHERE run_id=?", (run_id,))
    if not runs:
        raise ValidationError("找不到 run")
    run = runs[0]
    companies = db.query("SELECT * FROM companies WHERE run_id=? ORDER BY name_normalized", (run_id,))
    contacts = db.query(
        "SELECT c.* FROM contacts c JOIN companies x ON x.company_id=c.company_id "
        "WHERE x.run_id=? ORDER BY x.name_normalized,c.contact_role,c.contact_id",
        (run_id,),
    )
    entity_ids = {row["company_id"] for row in companies} | {row["contact_id"] for row in contacts}
    evidence = db.query(
        "SELECT e.* FROM evidence e WHERE "
        "(e.entity_type='company' AND e.entity_id IN (SELECT company_id FROM companies WHERE run_id=?)) OR "
        "(e.entity_type='contact' AND e.entity_id IN "
        "(SELECT c.contact_id FROM contacts c JOIN companies x ON x.company_id=c.company_id WHERE x.run_id=?)) "
        "ORDER BY e.observed_at,e.evidence_id",
        (run_id, run_id),
    )
    claims = db.query(
        "SELECT cl.* FROM claims cl WHERE "
        "(cl.entity_type='company' AND cl.entity_id IN (SELECT company_id FROM companies WHERE run_id=?)) OR "
        "(cl.entity_type='contact' AND cl.entity_id IN "
        "(SELECT c.contact_id FROM contacts c JOIN companies x ON x.company_id=c.company_id WHERE x.run_id=?)) "
        "ORDER BY cl.created_at,cl.claim_id",
        (run_id, run_id),
    )
    gaps = db.query(
        "SELECT g.* FROM research_gaps g WHERE "
        "(g.entity_type='company' AND g.entity_id IN (SELECT company_id FROM companies WHERE run_id=?)) OR "
        "(g.entity_type='contact' AND g.entity_id IN "
        "(SELECT c.contact_id FROM contacts c JOIN companies x ON x.company_id=c.company_id WHERE x.run_id=?)) "
        "ORDER BY g.created_at,g.gap_id",
        (run_id, run_id),
    )
    drafts = db.query(
        "SELECT d.*,dc.contract_json FROM drafts d LEFT JOIN draft_contracts dc ON dc.draft_id=d.draft_id "
        "WHERE d.run_id=? ORDER BY d.company_id,d.contact_id,d.draft_id",
        (run_id,),
    )
    source_runs = db.query("SELECT * FROM source_runs WHERE run_id=? ORDER BY started_at,source_run_id", (run_id,))
    duplicates = db.query(
        "SELECT d.*,l.name_original AS left_name,r.name_original AS right_name "
        "FROM duplicate_candidates d "
        "LEFT JOIN companies l ON d.left_id=l.company_id "
        "LEFT JOIN companies r ON d.right_id=r.company_id "
        "WHERE (l.run_id=? OR r.run_id=?) ORDER BY d.status,d.duplicate_id",
        (run_id, run_id),
    )

    evidence_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    claims_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    gaps_by_entity: dict[str, list[dict[str, Any]]] = defaultdict(list)
    contacts_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    drafts_by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in evidence:
        evidence_by_entity[row["entity_id"]].append(row)
    for row in claims:
        claims_by_entity[row["entity_id"]].append(row)
    for row in gaps:
        gaps_by_entity[row["entity_id"]].append(row)
    for row in contacts:
        contacts_by_company[row["company_id"]].append(row)
    for row in drafts:
        drafts_by_company[row["company_id"]].append(row)

    route_counts: Counter[str] = Counter()
    company_rows: list[dict[str, Any]] = []
    contact_rows: list[dict[str, Any]] = []
    draft_rows: list[dict[str, Any]] = []
    for company in companies:
        company_id = company["company_id"]
        company_claims = claims_by_entity[company_id]
        accepted_fields = {row["field_name"] for row in company_claims if row["status"] == "accepted"}
        proposed_fields = {row["field_name"] for row in company_claims if row["status"] == "proposed"}
        missing_service_fit = [field for field in SERVICE_FIT_FIELDS if field not in accepted_fields | proposed_fields]
        company_contacts = contacts_by_company[company_id]
        company_gap_rows = list(gaps_by_entity[company_id])
        for contact in company_contacts:
            company_gap_rows.extend(gaps_by_entity[contact["contact_id"]])
            grade, origin = _route_grade(contact, claims_by_entity[contact["contact_id"]])
            route_counts[grade] += 1
            contact_rows.append(
                {
                    "company_id": company_id,
                    "company": company["name_original"],
                    "contact_id": contact["contact_id"],
                    "name": contact["full_name"],
                    "title": contact["title"],
                    "route_grade": grade,
                    "route_origin": origin,
                    "identity_status": contact["identity_status"],
                    "contact_evidence": len(evidence_by_entity[contact["contact_id"]]),
                    "next_action": (
                        "核验具名人员、现任公司与职责" if grade == "R1" else
                        "核验部门商务用途及转交范围" if grade == "R2" else
                        "补查相关业务部门或具名职责入口" if grade == "R3" else
                        "补查公开且合规的企业联系入口"
                    ),
                }
            )
        open_gaps = [row for row in company_gap_rows if row["status"] == "open"]
        blocking_gaps = [row for row in open_gaps if int(row["blocking"])]
        company_evidence_count = len(evidence_by_entity[company_id])
        next_actions: list[str] = []
        if not company_evidence_count:
            next_actions.append("重新打开官网/业务页并记录公司证据")
        if company_contacts and any(row["identity_status"] not in {"supported", "verified"} for row in company_contacts):
            next_actions.append("复核联系入口")
        if missing_service_fit:
            next_actions.append("证据完成后恢复 service_fit_v1")
        if drafts_by_company[company_id]:
            next_actions.append("最后审校草稿事实与语气")
        company_rows.append(
            {
                "company_id": company_id,
                "company": company["name_original"],
                "country": company["country"],
                "website": company["website"],
                "company_evidence": company_evidence_count,
                "contact_evidence": sum(len(evidence_by_entity[row["contact_id"]]) for row in company_contacts),
                "accepted_claims": sum(1 for row in company_claims if row["status"] == "accepted"),
                "proposed_claims": sum(1 for row in company_claims if row["status"] == "proposed"),
                "missing_service_fit_fields": missing_service_fit,
                "open_gaps": len(open_gaps),
                "blocking_gaps": len(blocking_gaps),
                "drafts": len(drafts_by_company[company_id]),
                "next_action": "；".join(next_actions) or "人工确认当前记录",
            }
        )

    for draft in drafts:
        fact_check, voice_check = _contract_checks(draft.get("contract_json"))
        try:
            evidence_ids = json.loads(draft.get("evidence_ids") or "[]")
        except json.JSONDecodeError:
            evidence_ids = []
        draft_rows.append(
            {
                "draft_id": draft["draft_id"],
                "company_id": draft["company_id"],
                "contact_id": draft["contact_id"],
                "channel": draft["channel"],
                "subject": draft["subject"],
                "status": draft["status"],
                "evidence_count": len(evidence_ids) if isinstance(evidence_ids, list) else 0,
                "fact_check_status": fact_check,
                "voice_check_status": voice_check,
                "review_gate": "blocked" if not evidence_ids or fact_check != "passed" or voice_check != "passed" else "human_approval",
            }
        )

    summary = {
        "companies": len(companies),
        "contacts": len(contacts),
        "company_evidence": sum(1 for row in evidence if row["entity_type"] == "company"),
        "contact_evidence": sum(1 for row in evidence if row["entity_type"] == "contact"),
        "claims": len(claims),
        "accepted_claims": sum(1 for row in claims if row["status"] == "accepted"),
        "open_gaps": sum(1 for row in gaps if row["status"] == "open"),
        "blocking_gaps": sum(1 for row in gaps if row["status"] == "open" and int(row["blocking"])),
        "drafts": len(drafts),
        "approvable_drafts": sum(1 for row in draft_rows if row["review_gate"] == "human_approval"),
        "companies_without_evidence": sum(1 for row in company_rows if row["company_evidence"] == 0),
        "companies_with_incomplete_service_fit": sum(1 for row in company_rows if row["missing_service_fit_fields"]),
        "route_grades": {grade: route_counts.get(grade, 0) for grade in ("R0", "R1", "R2", "R3")},
        "duplicate_candidates": len(duplicates),
        "source_attempts": len(source_runs),
        "failed_or_restricted_sources": sum(1 for row in source_runs if row["outcome"] != "succeeded"),
    }
    return {
        "status": "needs_review" if summary["companies_without_evidence"] or summary["blocking_gaps"] else "ready_for_human_review",
        "run": run,
        "summary": summary,
        "companies": company_rows,
        "contacts": contact_rows,
        "drafts": draft_rows,
        "duplicates": duplicates,
        "source_runs": source_runs,
        "database_entities_checked": len(entity_ids),
        "boundaries": [
            "This report is read-only and does not accept Claims, resolve gaps, approve drafts, or send outreach.",
            "A missing duplicate/group record does not prove that no corporate relationship exists.",
            "Legacy route grades parsed from text remain pending until supported by public evidence and a reviewed Claim.",
        ],
    }


def render_review_plan_markdown(plan: dict[str, Any]) -> str:
    """Render a structured review plan as an employee-facing Markdown report."""
    run = plan["run"]
    summary = plan["summary"]
    lines = [
        f"# PlusC 增量复核任务包 — {_cell(run['run_id'])}",
        "",
        "> 这是只读复核清单，不是事实批准、文案批准或发送许可。",
        "",
        "## 批次概况",
        "",
        "| 项目 | 数量/状态 |",
        "|---|---:|",
        f"| 公司 | {summary['companies']} |",
        f"| 联系入口 | {summary['contacts']} |",
        f"| 公司证据 | {summary['company_evidence']} |",
        f"| 联系人证据 | {summary['contact_evidence']} |",
        f"| Claim / 已接受 Claim | {summary['claims']} / {summary['accepted_claims']} |",
        f"| 开放缺口 / 阻塞缺口 | {summary['open_gaps']} / {summary['blocking_gaps']} |",
        f"| 草稿 / 当前可进入人工批准 | {summary['drafts']} / {summary['approvable_drafts']} |",
        f"| 公司无证据 | {summary['companies_without_evidence']} |",
        f"| `service_fit_v1` 字段不完整 | {summary['companies_with_incomplete_service_fit']} |",
        f"| 入口等级 R0/R1/R2/R3 | {summary['route_grades']['R0']}/{summary['route_grades']['R1']}/{summary['route_grades']['R2']}/{summary['route_grades']['R3']} |",
        "",
        "## 公司增量复核表",
        "",
        "| # | 公司 | 市场 | 官网 | 公司/联系人证据 | 接受/待审Claim | 阻塞缺口 | 下一动作 |",
        "|---:|---|---|---|---:|---:|---:|---|",
    ]
    for index, row in enumerate(plan["companies"], 1):
        website = f"[官网]({_cell(row['website'])})" if row["website"] else "待补查"
        lines.append(
            f"| {index} | {_cell(row['company'])} | {_cell(row['country'])} | {website} | "
            f"{row['company_evidence']}/{row['contact_evidence']} | {row['accepted_claims']}/{row['proposed_claims']} | "
            f"{row['blocking_gaps']} | {_cell(row['next_action'])} |"
        )
    lines.extend(
        [
            "",
            "## Evidence / Claim 恢复缺口",
            "",
            f"- {summary['companies_without_evidence']} 家公司没有正式 Evidence。Excel 摘要不能替代重新打开的原始来源。",
            f"- {summary['companies_with_incomplete_service_fit']} 家公司的 `service_fit_v1` 合同字段尚未齐备。",
            f"- 当前已接受 Claim 为 {summary['accepted_claims']}；只有人工审核可接受 Claim。",
            "- 建议顺序：主体与业务信号证据 → 联系入口证据 → `service_fit_v1` 提案 → 人工决定 Claim。",
            "",
            "## 联系入口复核",
            "",
            "| 公司 | 联系人/部门 | 当前等级 | 等级来源 | 身份状态 | 联系证据 | 下一动作 |",
            "|---|---|---|---|---|---:|---|",
        ]
    )
    for row in plan["contacts"]:
        label = row["name"] or row["title"] or "企业/部门转交入口"
        lines.append(
            f"| {_cell(row['company'])} | {_cell(label)} | {row['route_grade']} | {_cell(row['route_origin'])} | "
            f"{_cell(row['identity_status'])} | {row['contact_evidence']} | {_cell(row['next_action'])} |"
        )
    lines.extend(["", "## 重复公司与集团关系", ""])
    if plan["duplicates"]:
        lines.extend(["| 左侧公司 | 右侧公司 | 匹配依据 | 状态 |", "|---|---|---|---|"])
        for row in plan["duplicates"]:
            lines.append(
                f"| {_cell(row.get('left_name') or row['left_id'])} | {_cell(row.get('right_name') or row['right_id'])} | "
                f"{_cell(row['match_type'])} | {_cell(row['status'])} |"
            )
    else:
        lines.append("- 数据库中没有已登记的重复候选；这不证明不存在集团、品牌或共享采购关系，仍需逐家核验。")
    lines.extend(["", "## 英文开发信事实审校队列", ""])
    if plan["drafts"]:
        lines.extend(
            [
                "| 草稿 | 渠道 | 主题 | 状态 | 证据数 | 事实/语气检查 | 门禁 |",
                "|---|---|---|---|---:|---|---|",
            ]
        )
        for row in plan["drafts"]:
            lines.append(
                f"| {_cell(row['draft_id'])} | {_cell(row['channel'])} | {_cell(row['subject'])} | {_cell(row['status'])} | "
                f"{row['evidence_count']} | {_cell(row['fact_check_status'])}/{_cell(row['voice_check_status'])} | {_cell(row['review_gate'])} |"
            )
    else:
        lines.append("- 本批次没有草稿。")
    lines.extend(["", "## 失败来源与恢复任务", ""])
    failed_sources = [row for row in plan["source_runs"] if row["outcome"] != "succeeded"]
    if failed_sources:
        lines.extend(["| 来源/查询 | 结果 | 错误 | 可重试 | 下一动作 |", "|---|---|---|---|---|"])
        for row in failed_sources:
            next_action = "换同站业务/联系页或其他公开来源后重试" if int(row["retryable"]) else "记录限制并选择替代公开来源"
            lines.append(
                f"| {_cell(row['query_summary'] or row['adapter_id'])} | {_cell(row['outcome'])} | "
                f"{_cell(row['error_code'])} | {'是' if int(row['retryable']) else '否'} | {next_action} |"
            )
    else:
        lines.append("- 没有已登记的失败或受限来源任务。")
    lines.extend(
        [
            "",
            "## 人工审核闸门",
            "",
            "1. 公司原始来源已实际打开，观察时间、正文摘要和 URL 已保存。",
            "2. 联系入口的身份、职责、用途及归属已由公开证据支持；R3 仍只表示转交入口。",
            "3. `service_fit_v1` 字段逐项绑定 Evidence，合作假设未写成采购需求。",
            "4. 草稿事实与语气分别由真实审核人复核；系统不得代替人工标记通过。",
            "5. 在批准前仍须检查产品版本、证据时效、触达依据和停止联系规则。",
            "6. 本任务包不执行邮件、表单、LinkedIn、报价或商业承诺。",
            "",
        ]
    )
    return "\n".join(lines)


def write_review_plan(db: Database, run_id: str, output: Path) -> dict[str, Any]:
    """Write a Markdown review plan and return its machine-readable summary."""
    output = output.expanduser().resolve()
    if output.suffix.lower() not in {".md", ".markdown"}:
        raise ValidationError("复核任务包输出必须是 Markdown 文件")
    plan = build_review_plan(db, run_id)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_review_plan_markdown(plan), encoding="utf-8")
    return {"status": plan["status"], "run_id": run_id, "output": str(output), "summary": plan["summary"]}
