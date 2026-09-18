"""数据库 JSON 快照。"""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
from typing import Any

from ..storage.database import Database, utc_now

TABLES = (
    "workspace_meta",
    "raw_imports",
    "runs",
    "companies",
    "contacts",
    "entity_keys",
    "source_runs",
    "source_plan_entries",
    "candidates",
    "candidate_sources",
    "evidence",
    "claims",
    "claim_evidence",
    "research_gaps",
    "duplicate_candidates",
    "drafts",
    "draft_contracts",
    "approvals",
    "replies",
    "stop_rules",
    "events",
)


def export_json(db: Database, output: Path, run_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"exported_at": utc_now(), "run_id": run_id, "tables": {}}
    with closing(db.connect()) as connection:
        tables = {table: [dict(row) for row in connection.execute(f"SELECT * FROM {table}")] for table in TABLES}
        if run_id:
            if not any(r["run_id"] == run_id for r in tables["runs"]):
                from ..errors import ValidationError

                raise ValidationError("找不到导出批次")
            companies = {r["company_id"] for r in tables["companies"] if r["run_id"] == run_id}
            contacts = {r["contact_id"] for r in tables["contacts"] if r["company_id"] in companies}

            def belongs(row: dict[str, Any]) -> bool:
                return (row.get("entity_type") == "company" and row.get("entity_id") in companies) or (
                    row.get("entity_type") == "contact" and row.get("entity_id") in contacts
                )

            for table in (
                "runs",
                "companies",
                "source_runs",
                "source_plan_entries",
                "candidates",
                "candidate_sources",
                "drafts",
            ):
                tables[table] = [r for r in tables[table] if r["run_id"] == run_id]
            tables["contacts"] = [r for r in tables["contacts"] if r["contact_id"] in contacts]
            for table in ("evidence", "claims", "research_gaps", "entity_keys"):
                tables[table] = [r for r in tables[table] if belongs(r)]
            claims = {r["claim_id"] for r in tables["claims"]}
            evidence = {r["evidence_id"] for r in tables["evidence"]}
            drafts = {r["draft_id"] for r in tables["drafts"]}
            tables["claim_evidence"] = [
                r for r in tables["claim_evidence"] if r["claim_id"] in claims and r["evidence_id"] in evidence
            ]
            for table in ("approvals", "draft_contracts"):
                tables[table] = [r for r in tables[table] if r["draft_id"] in drafts]
            tables["replies"] = [r for r in tables["replies"] if r["contact_id"] in contacts]
            tables["events"] = [r for r in tables["events"] if r["run_id"] == run_id or belongs(r)]
            tables["duplicate_candidates"] = [
                r
                for r in tables["duplicate_candidates"]
                if r["left_id"] in companies | contacts and r["right_id"] in companies | contacts
            ]
            emails = {r["public_email"] for r in tables["contacts"] if r["public_email"]}
            domains = {r["root_domain"] for r in tables["companies"] if r["root_domain"]}
            scopes = {"company": companies, "contact": contacts, "email": emails, "domain": domains}
            tables["stop_rules"] = [
                r for r in tables["stop_rules"] if r["scope_value"] in scopes.get(r["scope_type"], set())
            ]
            # 原始导入可能混合多个批次，只在完整工作区备份中提供。
            tables["raw_imports"] = []
        payload["tables"] = tables
        known_costs = {
            e["entity_id"]: json.loads(e["payload_json"])
            for e in tables["events"]
            if e["event_type"] == "source.recorded"
        }
        for row in tables["source_runs"]:
            cost = known_costs.get(row["source_run_id"], {})
            row["cost_known"] = bool(cost.get("cost_known"))
            row["cost_amount"] = cost.get("cost_amount") if row["cost_known"] else None
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "succeeded", "output": str(output), "tables": len(TABLES)}
