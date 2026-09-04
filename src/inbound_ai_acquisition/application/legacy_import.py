"""将上一版多表 JSON 无损封存并映射到 SQLite。"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ..errors import ValidationError
from ..storage.database import Database, canonical_hash, new_id, utc_now
from .services import normalize_name, normalize_url, root_domain

RUN_STATUS_MAP = {
    "planned": "created",
    "researching": "researching",
    "review_ready": "reviewing",
    "approved": "reviewing",
    "manually_sent": "reviewing",
    "closed": "closed",
}
DRAFT_STATUS_MAP = {"manually_sent": "sent"}


def import_legacy_bundle(db: Database, path: Path, request_id: str) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    sheets = payload.get("sheets")
    if not isinstance(sheets, dict):
        raise ValidationError("旧数据必须包含 sheets")
    source_hash = canonical_hash(payload)
    with db.transaction() as connection:
        previous = connection.execute(
            "SELECT raw_import_id FROM raw_imports WHERE source_hash=?", (source_hash,)
        ).fetchone()
        if previous:
            return {
                "request_id": request_id,
                "status": "already_applied",
                "changed_records": 0,
                "raw_import_id": previous[0],
                "errors": [],
            }
        raw_id = new_id("raw")
        connection.execute(
            "INSERT INTO raw_imports VALUES (?,?,?,?,?,?)",
            (raw_id, str(path), source_hash, "legacy-workbook-1.0", json.dumps(payload, ensure_ascii=False), utc_now()),
        )
        changed = 1
        for row in sheets.get("RunConfig", []):
            connection.execute(
                "INSERT OR IGNORE INTO runs(run_id,markets,segments,target_count,status,next_action,product_version,voice_version,created_at,closed_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (
                    row["run_id"],
                    row.get("market", ""),
                    row.get("client_types", ""),
                    int(row.get("target_count") or 1),
                    RUN_STATUS_MAP.get(row.get("run_status"), "created"),
                    "检查迁移数据",
                    row.get("product_profile_version", ""),
                    row.get("voice_profile_version", ""),
                    row.get("created_at") or utc_now(),
                    row.get("created_at") if row.get("run_status") == "closed" else None,
                ),
            )
            changed += connection.execute("SELECT changes()").fetchone()[0]
        fallback_run = sheets.get("RunConfig", [{}])[0].get("run_id") if sheets.get("RunConfig") else None
        for row in sheets.get("Companies", []):
            website = normalize_url(row.get("website", "")) if row.get("website") else ""
            now = row.get("observed_at") or utc_now()
            connection.execute(
                "INSERT OR IGNORE INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["company_id"],
                    row.get("run_id") or fallback_run,
                    row.get("company_name_original", ""),
                    row.get("company_name_normalized") or normalize_name(row.get("company_name_original", "")),
                    row.get("country", ""),
                    row.get("city", ""),
                    row.get("company_type", ""),
                    website,
                    row.get("root_domain") or root_domain(website),
                    normalize_url(row.get("linkedin_company_url", "")) if row.get("linkedin_company_url") else "",
                    row.get("candidate_status", "chat_candidate"),
                    row.get("fit_reason", ""),
                    row.get("risk_note", ""),
                    now,
                    now,
                ),
            )
            changed += connection.execute("SELECT changes()").fetchone()[0]
        for row in sheets.get("Contacts", []):
            now = row.get("observed_at") or utc_now()
            identity = (
                "unverified"
                if row.get("identity_status") == "identity_pending"
                else row.get("identity_status", "unverified")
            )
            connection.execute(
                "INSERT OR IGNORE INTO contacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["contact_id"],
                    row["company_id"],
                    row.get("name", ""),
                    row.get("title", ""),
                    row.get("department_or_scope", ""),
                    row.get("contact_role", "primary"),
                    normalize_url(row.get("linkedin_url", "")) if row.get("linkedin_url") else "",
                    row.get("business_email", "").lower(),
                    identity,
                    row.get("contact_status", "not_contacted"),
                    now,
                    now,
                    now,
                ),
            )
            changed += connection.execute("SELECT changes()").fetchone()[0]
        for row in sheets.get("Evidence", []):
            connection.execute(
                "INSERT OR IGNORE INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["evidence_id"],
                    None,
                    row["entity_type"],
                    row["entity_id"],
                    normalize_url(row["source_url"]),
                    row.get("source_tier", "X"),
                    row.get("supported_field", ""),
                    row.get("fact_summary", ""),
                    row.get("source_published_at") or None,
                    row.get("observed_at") or utc_now(),
                    canonical_hash(row.get("fact_summary", "")),
                    row.get("source_access_status", "opened"),
                    int(bool(row.get("conflict_note"))),
                ),
            )
            changed += connection.execute("SELECT changes()").fetchone()[0]
        for row in sheets.get("ResearchGaps", []):
            connection.execute(
                "INSERT OR IGNORE INTO research_gaps VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    row["gap_id"],
                    row["entity_type"],
                    row["entity_id"],
                    row.get("missing_field", ""),
                    row.get("why_it_matters", ""),
                    int(bool(row.get("blocks_outreach"))),
                    row.get("gap_status", "open"),
                    utc_now(),
                    None,
                ),
            )
            changed += connection.execute("SELECT changes()").fetchone()[0]
        for row in sheets.get("Drafts", []):
            contact = connection.execute(
                "SELECT company_id FROM contacts WHERE contact_id=?", (row["contact_id"],)
            ).fetchone()
            if not contact:
                continue
            status = DRAFT_STATUS_MAP.get(row.get("draft_status", "draft"), row.get("draft_status", "draft"))
            body = row.get("message", "")
            now = utc_now()
            connection.execute(
                "INSERT OR IGNORE INTO drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    row["message_id"],
                    fallback_run,
                    contact[0],
                    row["contact_id"],
                    row.get("channel", "email"),
                    row.get("subject", ""),
                    body,
                    json.dumps(
                        [row.get("personalization_evidence_id")] if row.get("personalization_evidence_id") else []
                    ),
                    "",
                    canonical_hash(body),
                    status,
                    now,
                    now,
                    row.get("sent_at") or None,
                ),
            )
            changed += connection.execute("SELECT changes()").fetchone()[0]
        db.append_event(
            connection,
            event_type="legacy.imported",
            request_id=request_id,
            run_id=fallback_run,
            entity_type="raw_import",
            entity_id=raw_id,
            payload={"source_hash": source_hash},
        )
    return {
        "request_id": request_id,
        "status": "succeeded",
        "changed_records": changed,
        "raw_import_id": raw_id,
        "run_id": fallback_run,
        "next_action": "检查迁移数据",
        "errors": [],
    }
