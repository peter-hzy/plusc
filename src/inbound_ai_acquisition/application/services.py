"""核心用例：批次、导入、事实、草稿、回复、停止与去重。"""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from ..domain.enums import CLAIM_STATUSES, DRAFT_STATUSES, SOURCE_OUTCOMES
from ..domain.policies import ensure_draft_can_advance, normalize_reply, require_one_cta
from ..domain.transitions import require_draft_transition
from ..errors import StateError, ValidationError
from ..storage.database import Database, canonical_hash, new_id, utc_now
from ..storage.repositories import accepted_claim_count, active_stop_exists, blocking_gap_count


def _result(
    request_id: str,
    *,
    status: str = "succeeded",
    run_id: str | None = None,
    changed: int = 0,
    next_action: str = "",
    errors: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "request_id": request_id,
        "status": status,
        "run_id": run_id,
        "changed_records": changed,
        "next_action": next_action,
        "errors": errors or [],
    }


def normalize_name(value: str) -> str:
    value = re.sub(r"[^\w\s]", " ", value.casefold())
    return re.sub(r"\s+", " ", value).strip()


def normalize_url(value: str) -> str:
    value = value.strip()
    if not value:
        return ""
    parsed = urlsplit(value if "://" in value else "https://" + value)
    host = (parsed.hostname or "").lower()
    if not host:
        raise ValidationError(f"无效 URL：{value}")
    path = parsed.path.rstrip("/")
    return f"{parsed.scheme.lower() or 'https'}://{host}{path}"


def root_domain(value: str) -> str:
    if not value:
        return ""
    host = (urlsplit(value if "://" in value else "https://" + value).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def create_run(
    db: Database,
    *,
    markets: list[str],
    segments: list[str],
    target: int,
    request_id: str,
    idempotency_key: str,
    product_version: str = "",
    voice_version: str = "",
    candidate_pool_multiplier: float = 3.0,
    min_source_categories: int = 3,
    production_min_target: int = 20,
) -> dict[str, Any]:
    payload = {
        "markets": markets,
        "segments": segments,
        "target": target,
        "product_version": product_version,
        "voice_version": voice_version,
        "candidate_pool_multiplier": candidate_pool_multiplier,
        "min_source_categories": min_source_categories,
        "production_min_target": production_min_target,
    }
    if not markets or not segments or target < 1:
        raise ValidationError("市场、客户类型和目标数量不能为空")
    if candidate_pool_multiplier < 1 or min_source_categories < 1 or production_min_target < 1:
        raise ValidationError("候选池倍数、来源类别和正式批次基线必须大于等于1")
    with db.transaction() as connection:
        prior = db.idempotency_lookup(connection, idempotency_key, payload)
        if prior:
            return prior
        run_id = new_id("run")
        connection.execute(
            "INSERT INTO runs(run_id,markets,segments,target_count,candidate_pool_multiplier,min_source_categories,"
            "production_min_target,status,next_action,product_version,voice_version,created_at) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                run_id,
                ",".join(markets),
                ",".join(segments),
                target,
                candidate_pool_multiplier,
                min_source_categories,
                production_min_target,
                "created",
                "导入或研究候选公司",
                product_version,
                voice_version,
                utc_now(),
            ),
        )
        result = _result(request_id, run_id=run_id, changed=1, next_action="导入或研究候选公司")
        db.append_event(connection, event_type="run.created", request_id=request_id, run_id=run_id, payload=payload)
        db.idempotency_store(connection, idempotency_key, payload, result)
        return result


def run_status(db: Database, run_id: str) -> dict[str, Any]:
    rows = db.query("SELECT * FROM runs WHERE run_id=?", (run_id,))
    if not rows:
        raise ValidationError("找不到 run")
    summary = rows[0]
    counts: dict[str, int] = {}
    for table in ("companies", "contacts", "source_runs", "evidence", "claims", "drafts", "replies", "research_gaps"):
        if table in {"companies", "drafts"}:
            count = db.query(f"SELECT COUNT(*) AS n FROM {table} WHERE run_id=?", (run_id,))[0]["n"]
        elif table == "contacts":
            count = db.query(
                "SELECT COUNT(*) AS n FROM contacts c JOIN companies x ON x.company_id=c.company_id WHERE x.run_id=?",
                (run_id,),
            )[0]["n"]
        elif table == "source_runs":
            count = db.query("SELECT COUNT(*) AS n FROM source_runs WHERE run_id=?", (run_id,))[0]["n"]
        elif table == "evidence":
            count = db.query(
                "SELECT COUNT(*) AS n FROM evidence e WHERE "
                "(e.entity_type='company' AND e.entity_id IN (SELECT company_id FROM companies WHERE run_id=?)) OR "
                "(e.entity_type='contact' AND e.entity_id IN (SELECT c.contact_id FROM contacts c JOIN companies x ON x.company_id=c.company_id WHERE x.run_id=?))",
                (run_id, run_id),
            )[0]["n"]
        elif table in {"claims", "research_gaps"}:
            count = db.query(
                f"SELECT COUNT(*) AS n FROM {table} t JOIN companies x ON x.company_id=t.entity_id "
                "WHERE t.entity_type='company' AND x.run_id=?",
                (run_id,),
            )[0]["n"]
        else:
            count = db.query(
                "SELECT COUNT(*) AS n FROM replies r JOIN contacts c ON c.contact_id=r.contact_id "
                "JOIN companies x ON x.company_id=c.company_id WHERE x.run_id=?",
                (run_id,),
            )[0]["n"]
        counts[table] = int(count)
    summary["counts"] = counts
    return summary


def close_run(db: Database, run_id: str, request_id: str) -> dict[str, Any]:
    with db.transaction() as connection:
        row = connection.execute("SELECT status FROM runs WHERE run_id=?", (run_id,)).fetchone()
        if not row:
            raise ValidationError("找不到 run")
        if row[0] == "closed":
            return _result(request_id, status="already_applied", run_id=run_id)
        connection.execute(
            "UPDATE runs SET status='closed',closed_at=?,next_action='' WHERE run_id=?", (utc_now(), run_id)
        )
        db.append_event(connection, event_type="run.closed", request_id=request_id, run_id=run_id)
    return _result(request_id, run_id=run_id, changed=1)


def _load_records(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with path.open("r", encoding="utf-8-sig", newline="") as handle:
            return [dict(row) for row in csv.DictReader(handle)]
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        return payload
    for key in ("records", "companies", "contacts", "evidence", "replies"):
        if isinstance(payload.get(key), list):
            return payload[key]
    raise ValidationError("导入文件必须是 CSV、JSON 数组或包含 records 的 JSON")


def _entity_exists(connection: Any, entity_type: str, entity_id: str) -> bool:
    table, column = {
        "company": ("companies", "company_id"),
        "contact": ("contacts", "contact_id"),
        "draft": ("drafts", "draft_id"),
        "reply": ("replies", "reply_id"),
    }.get(entity_type, (None, None))
    return bool(table and connection.execute(f"SELECT 1 FROM {table} WHERE {column}=?", (entity_id,)).fetchone())


def import_companies(db: Database, run_id: str, path: Path, request_id: str) -> dict[str, Any]:
    records = _load_records(path)
    changed = 0
    with db.transaction() as connection:
        if not connection.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
            raise ValidationError("找不到 run")
        for row in records:
            unknown = set(row) - {
                "company_id",
                "name",
                "company_name",
                "country",
                "city",
                "segment",
                "website",
                "linkedin_url",
                "fit_status",
                "fit_reason",
                "risk_notes",
            }
            if unknown:
                raise ValidationError("公司导入包含未知字段：" + ", ".join(sorted(unknown)))
            name = str(row.get("name") or row.get("company_name") or "").strip()
            if not name:
                raise ValidationError("公司缺少 name/company_name")
            website = normalize_url(str(row.get("website", ""))) if row.get("website") else ""
            domain = root_domain(website)
            existing = connection.execute(
                "SELECT company_id FROM companies WHERE run_id=? AND root_domain=? AND ?<>''",
                (run_id, domain, domain),
            ).fetchone()
            if existing:
                continue
            company_id = str(row.get("company_id") or new_id("co"))
            now = utc_now()
            connection.execute(
                "INSERT INTO companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    company_id,
                    run_id,
                    name,
                    normalize_name(name),
                    str(row.get("country", "")),
                    str(row.get("city", "")),
                    str(row.get("segment", "")),
                    website,
                    domain,
                    normalize_url(str(row.get("linkedin_url", ""))) if row.get("linkedin_url") else "",
                    str(row.get("fit_status", "chat_candidate")),
                    str(row.get("fit_reason", "")),
                    str(row.get("risk_notes", "")),
                    now,
                    now,
                ),
            )
            if domain:
                connection.execute(
                    "INSERT INTO entity_keys(entity_key_id,entity_type,entity_id,key_type,normalized_value,status,source,observed_at) VALUES (?,?,?,?,?,?,?,?)",
                    (new_id("key"), "company", company_id, "root_domain", domain, "active", str(path), now),
                )
            changed += 1
        db.append_event(
            connection,
            event_type="companies.imported",
            request_id=request_id,
            run_id=run_id,
            payload={"file_hash": canonical_hash(path.read_bytes().hex()), "count": changed},
        )
    return _result(request_id, run_id=run_id, changed=changed, next_action="补充公司证据和负责人")


def import_contacts(db: Database, path: Path, request_id: str) -> dict[str, Any]:
    records = _load_records(path)
    changed = 0
    with db.transaction() as connection:
        for row in records:
            unknown = set(row) - {
                "contact_id",
                "company_id",
                "full_name",
                "title",
                "role_scope",
                "contact_role",
                "linkedin_url",
                "public_email",
                "identity_status",
                "identity_evidence_url",
                "identity_evidence_text",
                "observed_at",
            }
            if unknown:
                raise ValidationError("联系人导入包含未知字段：" + ", ".join(sorted(unknown)))
            company_id = str(row.get("company_id", ""))
            if not connection.execute("SELECT 1 FROM companies WHERE company_id=?", (company_id,)).fetchone():
                raise ValidationError(f"联系人引用不存在的 company_id：{company_id}")
            linkedin = normalize_url(str(row.get("linkedin_url", ""))) if row.get("linkedin_url") else ""
            email = str(row.get("public_email", "")).strip().lower()
            if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise ValidationError(f"邮箱格式无效：{email}")
            now = utc_now()
            contact_id = str(row.get("contact_id") or new_id("ct"))
            identity_status = str(row.get("identity_status", "unverified"))
            if identity_status in {"supported", "verified"} and not (
                str(row.get("identity_evidence_url", "")).strip() and str(row.get("identity_evidence_text", "")).strip()
            ):
                raise ValidationError("supported/verified 联系人必须提供身份来源 URL 和观察内容")
            connection.execute(
                "INSERT INTO contacts(contact_id,company_id,full_name,title,role_scope,contact_role,linkedin_url,public_email,identity_status,contact_status,last_verified_at,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    contact_id,
                    company_id,
                    str(row.get("full_name", "")),
                    str(row.get("title", "")),
                    str(row.get("role_scope", "")),
                    str(row.get("contact_role", "primary")),
                    linkedin,
                    email,
                    identity_status,
                    "not_contacted",
                    str(row.get("observed_at") or now) if identity_status in {"supported", "verified"} else None,
                    now,
                    now,
                ),
            )
            for key_type, value in (("linkedin", linkedin), ("email", email)):
                if value:
                    connection.execute(
                        "INSERT INTO entity_keys(entity_key_id,entity_type,entity_id,key_type,normalized_value,status,source,observed_at) VALUES (?,?,?,?,?,?,?,?)",
                        (new_id("key"), "contact", contact_id, key_type, value, "active", str(path), now),
                    )
            if identity_status in {"supported", "verified"}:
                observed_text = str(row["identity_evidence_text"])
                connection.execute(
                    "INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_id("ev"),
                        None,
                        "contact",
                        contact_id,
                        normalize_url(str(row["identity_evidence_url"])),
                        "primary" if identity_status == "verified" else "secondary",
                        "identity_status",
                        observed_text,
                        None,
                        str(row.get("observed_at") or now),
                        canonical_hash(observed_text),
                        "accessible",
                        0,
                    ),
                )
            changed += 1
        db.append_event(connection, event_type="contacts.imported", request_id=request_id, payload={"count": changed})
    return _result(request_id, changed=changed, next_action="核验联系人并建立事实")


def import_evidence(db: Database, path: Path, request_id: str) -> dict[str, Any]:
    records = _load_records(path)
    changed = 0
    with db.transaction() as connection:
        for row in records:
            required = {"entity_type", "entity_id", "source_url", "observed_text"}
            if not required.issubset(row) or not all(str(row.get(k, "")).strip() for k in required):
                raise ValidationError("证据缺少 entity_type/entity_id/source_url/observed_text")
            if not _entity_exists(connection, str(row["entity_type"]), str(row["entity_id"])):
                raise ValidationError(f"证据引用不存在的实体：{row['entity_type']}:{row['entity_id']}")
            now = utc_now()
            connection.execute(
                "INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(row.get("evidence_id") or new_id("ev")),
                    row.get("source_run_id"),
                    row["entity_type"],
                    row["entity_id"],
                    normalize_url(str(row["source_url"])),
                    str(row.get("source_level", "secondary")),
                    str(row.get("purpose", "")),
                    str(row["observed_text"]),
                    row.get("published_at"),
                    str(row.get("observed_at") or now),
                    canonical_hash(str(row["observed_text"])),
                    str(row.get("access_status", "accessible")),
                    int(bool(row.get("conflicts", False))),
                ),
            )
            changed += 1
        db.append_event(connection, event_type="evidence.imported", request_id=request_id, payload={"count": changed})
    return _result(request_id, changed=changed, next_action="提出并审核 Claims")


def decide_claim(db: Database, claim_id: str, status: str, actor: str, reason: str, request_id: str) -> dict[str, Any]:
    if status not in CLAIM_STATUSES - {"proposed", "superseded"}:
        raise ValidationError("无效 Claim 决策")
    with db.transaction() as connection:
        row = connection.execute("SELECT * FROM claims WHERE claim_id=?", (claim_id,)).fetchone()
        if not row:
            raise ValidationError("找不到 claim")
        evidence_count = connection.execute(
            "SELECT COUNT(*) FROM claim_evidence WHERE claim_id=?", (claim_id,)
        ).fetchone()[0]
        if status == "accepted" and evidence_count < 1:
            raise StateError("没有证据的 Claim 不能接受")
        conflicts = connection.execute(
            "SELECT COUNT(*) FROM evidence e JOIN claim_evidence ce ON ce.evidence_id=e.evidence_id WHERE ce.claim_id=? AND e.conflicts=1",
            (claim_id,),
        ).fetchone()[0]
        if status == "accepted" and conflicts:
            raise StateError("Claim 存在冲突证据，只能暂缓或拒绝")
        connection.execute(
            "UPDATE claims SET status=?,decided_by=?,decided_at=?,decision_reason=? WHERE claim_id=?",
            (status, actor, utc_now(), reason, claim_id),
        )
        if status == "accepted":
            company_fields = {
                "country",
                "city",
                "segment",
                "website",
                "linkedin_url",
                "fit_status",
                "fit_reason",
                "risk_notes",
            }
            contact_fields = {
                "full_name",
                "title",
                "role_scope",
                "linkedin_url",
                "public_email",
                "identity_status",
                "contact_status",
            }
            allowed = (
                company_fields
                if row["entity_type"] == "company"
                else contact_fields
                if row["entity_type"] == "contact"
                else set()
            )
            if row["field_name"] in allowed:
                value = row["proposed_value"]
                if row["field_name"] in {"website", "linkedin_url"}:
                    value = normalize_url(value)
                if row["field_name"] == "public_email":
                    value = value.strip().lower()
                    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", value):
                        raise ValidationError("Claim 中的邮箱格式无效")
                if row["field_name"] == "identity_status" and value not in {
                    "unverified",
                    "supported",
                    "verified",
                    "not_found",
                    "contradicted",
                }:
                    raise ValidationError("Claim 中的 identity_status 无效")
                if row["field_name"] in {"website", "linkedin_url", "public_email", "identity_status"} and row[
                    "evidence_grade"
                ] not in {"strong", "primary"}:
                    raise StateError("身份和联系方式字段需要 strong/primary 证据等级")
                table = "companies" if row["entity_type"] == "company" else "contacts"
                id_column = "company_id" if row["entity_type"] == "company" else "contact_id"
                connection.execute(
                    f"UPDATE {table} SET {row['field_name']}=?,updated_at=? WHERE {id_column}=?",
                    (value, utc_now(), row["entity_id"]),
                )
                key_type = None
                key_value = value
                if row["entity_type"] == "company" and row["field_name"] == "website":
                    key_type = "root_domain"
                    key_value = root_domain(value)
                    connection.execute(
                        "UPDATE companies SET root_domain=? WHERE company_id=?", (key_value, row["entity_id"])
                    )
                elif row["field_name"] in {"linkedin_url", "public_email"}:
                    key_type = "linkedin" if row["field_name"] == "linkedin_url" else "email"
                if key_type and key_value:
                    connection.execute(
                        "UPDATE entity_keys SET status='retired' WHERE entity_type=? AND entity_id=? AND key_type=? AND status='active'",
                        (row["entity_type"], row["entity_id"], key_type),
                    )
                    connection.execute(
                        "INSERT INTO entity_keys VALUES (?,?,?,?,?,?,?,?)",
                        (
                            new_id("key"),
                            row["entity_type"],
                            row["entity_id"],
                            key_type,
                            key_value,
                            "active",
                            f"claim:{claim_id}",
                            utc_now(),
                        ),
                    )
        db.append_event(
            connection, event_type=f"claim.{status}", request_id=request_id, entity_type="claim", entity_id=claim_id
        )
    return _result(request_id, changed=1)


def create_draft(db: Database, payload: dict[str, Any], request_id: str) -> dict[str, Any]:
    channel = str(payload.get("channel", ""))
    if channel not in {"email", "linkedin"}:
        raise ValidationError("channel 必须是 email 或 linkedin")
    body = str(payload.get("body", "")).strip()
    if not body:
        raise ValidationError("草稿正文不能为空")
    require_one_cta(body)
    with db.transaction() as connection:
        contact = connection.execute(
            "SELECT * FROM contacts WHERE contact_id=?", (payload.get("contact_id"),)
        ).fetchone()
        if not contact:
            raise ValidationError("找不到联系人")
        company_id = contact["company_id"]
        evidence_ids = payload.get("evidence_ids", [])
        if not isinstance(evidence_ids, list) or not evidence_ids:
            raise ValidationError("草稿必须引用至少一条 Evidence")
        placeholders = ",".join("?" for _ in evidence_ids)
        matched_evidence = connection.execute(
            f"SELECT COUNT(*) FROM evidence WHERE evidence_id IN ({placeholders}) AND ((entity_type='company' AND entity_id=?) OR (entity_type='contact' AND entity_id=?))",
            (*evidence_ids, company_id, contact["contact_id"]),
        ).fetchone()[0]
        if matched_evidence != len(set(evidence_ids)):
            raise ValidationError("草稿引用了不存在或不属于当前公司/联系人的 Evidence")
        ensure_draft_can_advance(
            has_contact=True,
            identity_status=contact["identity_status"],
            accepted_claims=accepted_claim_count(connection, company_id),
            open_blocking_gaps=blocking_gap_count(connection, company_id),
            stopped=active_stop_exists(connection, contact["contact_id"], company_id),
        )
        now = utc_now()
        draft_id = str(payload.get("draft_id") or new_id("dr"))
        body_hash = canonical_hash(body)
        connection.execute(
            "INSERT INTO drafts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                draft_id,
                payload.get("run_id"),
                company_id,
                contact["contact_id"],
                channel,
                str(payload.get("subject", "")),
                body,
                json.dumps(evidence_ids, ensure_ascii=False),
                str(payload.get("product_version", "")),
                body_hash,
                "review_ready",
                now,
                now,
                None,
            ),
        )
        db.append_event(
            connection,
            event_type="draft.created",
            request_id=request_id,
            run_id=payload.get("run_id"),
            entity_type="draft",
            entity_id=draft_id,
        )
    result = _result(request_id, run_id=payload.get("run_id"), changed=1, next_action="人工审核并批准")
    result["draft_id"] = draft_id
    return result


def approve_draft(db: Database, draft_id: str, actor: str, reason: str, request_id: str) -> dict[str, Any]:
    with db.transaction() as connection:
        row = connection.execute("SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        if not row:
            raise ValidationError("找不到草稿")
        require_draft_transition(row["status"], "approved")
        current_hash = canonical_hash(row["body"])
        connection.execute(
            "UPDATE drafts SET status='approved',body_hash=?,updated_at=? WHERE draft_id=?",
            (current_hash, utc_now(), draft_id),
        )
        connection.execute(
            "INSERT INTO approvals VALUES (?,?,?,?,?,?)",
            (new_id("ap"), draft_id, current_hash, actor, reason, utc_now()),
        )
        db.append_event(
            connection,
            event_type="draft.approved",
            request_id=request_id,
            run_id=row["run_id"],
            entity_type="draft",
            entity_id=draft_id,
        )
    return _result(request_id, run_id=row["run_id"], changed=1, next_action="人工发送后记录 mark-sent")


def set_draft_status(db: Database, draft_id: str, target: str, request_id: str) -> dict[str, Any]:
    if target not in DRAFT_STATUSES:
        raise ValidationError("无效草稿状态")
    with db.transaction() as connection:
        row = connection.execute("SELECT * FROM drafts WHERE draft_id=?", (draft_id,)).fetchone()
        if not row:
            raise ValidationError("找不到草稿")
        require_draft_transition(row["status"], target)
        if target == "sent":
            approval = connection.execute(
                "SELECT body_hash FROM approvals WHERE draft_id=? ORDER BY approved_at DESC LIMIT 1", (draft_id,)
            ).fetchone()
            if not approval or approval[0] != canonical_hash(row["body"]):
                raise StateError("草稿未批准或批准后正文已修改")
            if active_stop_exists(connection, row["contact_id"], row["company_id"]):
                raise StateError("命中停止联系规则，不能记录发送")
        connection.execute(
            "UPDATE drafts SET status=?,updated_at=?,sent_at=? WHERE draft_id=?",
            (target, utc_now(), utc_now() if target == "sent" else None, draft_id),
        )
        db.append_event(
            connection,
            event_type=f"draft.{target}",
            request_id=request_id,
            run_id=row["run_id"],
            entity_type="draft",
            entity_id=draft_id,
        )
    return _result(request_id, run_id=row["run_id"], changed=1)


def ingest_reply(db: Database, payload: dict[str, Any], idempotency_key: str, request_id: str) -> dict[str, Any]:
    payload = normalize_reply(payload)
    required = {"message_id", "contact_id", "channel", "received_at", "reply_category"}
    if not required.issubset(payload):
        raise ValidationError("回复缺少必填字段")
    with db.transaction() as connection:
        prior = db.idempotency_lookup(connection, idempotency_key, payload)
        if prior:
            return prior
        contact = connection.execute("SELECT * FROM contacts WHERE contact_id=?", (payload["contact_id"],)).fetchone()
        if not contact:
            raise ValidationError("回复引用不存在的联系人")
        reply_id = new_id("rp")
        connection.execute(
            "INSERT INTO replies(reply_id,external_message_id,contact_id,channel,received_at,source_reference,category,confirmed_needs,unknown_needs,next_action,needs_human_takeover,do_not_contact,raw_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                reply_id,
                payload["message_id"],
                payload["contact_id"],
                payload["channel"],
                payload["received_at"],
                str(payload.get("source_reference", "")),
                payload["reply_category"],
                str(payload.get("confirmed_needs", "")),
                str(payload.get("unknown_needs", "")),
                str(payload.get("next_action", "")),
                int(payload["needs_human_takeover"]),
                int(payload["do_not_contact"]),
                canonical_hash(payload),
                utc_now(),
            ),
        )
        changed = 1
        if payload["do_not_contact"]:
            try:
                connection.execute(
                    "INSERT INTO stop_rules VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        new_id("stop"),
                        "contact",
                        payload["contact_id"],
                        payload["reply_category"],
                        "active",
                        "reply_ingest",
                        utc_now(),
                        None,
                        None,
                        "",
                    ),
                )
                changed += 1
            except Exception as exc:
                if "UNIQUE" not in str(exc):
                    raise
            cursor = connection.execute(
                "UPDATE drafts SET status='stopped',updated_at=? WHERE contact_id=? AND status IN ('draft','review_ready','approved')",
                (utc_now(), payload["contact_id"]),
            )
            changed += cursor.rowcount
        result = _result(
            request_id,
            changed=changed,
            next_action="人工处理回复" if payload["needs_human_takeover"] else "更新询盘状态",
        )
        result["reply_id"] = reply_id
        db.append_event(
            connection,
            event_type="reply.ingested",
            request_id=request_id,
            entity_type="reply",
            entity_id=reply_id,
            payload={"category": payload["reply_category"]},
        )
        db.idempotency_store(connection, idempotency_key, payload, result)
        return result


def add_stop(
    db: Database, scope_type: str, scope_value: str, reason: str, actor: str, request_id: str
) -> dict[str, Any]:
    if scope_type not in {"contact", "company", "email", "domain"}:
        raise ValidationError("无效停止范围")
    with db.transaction() as connection:
        prior = connection.execute(
            "SELECT stop_rule_id FROM stop_rules WHERE scope_type=? AND scope_value=? AND status='active'",
            (scope_type, scope_value),
        ).fetchone()
        if prior:
            return _result(request_id, status="already_applied")
        rule_id = new_id("stop")
        connection.execute(
            "INSERT INTO stop_rules VALUES (?,?,?,?,?,?,?,?,?,?)",
            (rule_id, scope_type, scope_value, reason, "active", actor, utc_now(), None, None, ""),
        )
        db.append_event(
            connection, event_type="stop.added", request_id=request_id, entity_type="stop_rule", entity_id=rule_id
        )
    return _result(request_id, changed=1)


def release_stop(db: Database, rule_id: str, actor: str, reason: str, request_id: str) -> dict[str, Any]:
    if not reason.strip():
        raise ValidationError("解除停止必须填写理由")
    with db.transaction() as connection:
        cursor = connection.execute(
            "UPDATE stop_rules SET status='released',released_by=?,released_at=?,release_reason=? WHERE stop_rule_id=? AND status='active'",
            (actor, utc_now(), reason, rule_id),
        )
        if cursor.rowcount != 1:
            raise ValidationError("找不到活动停止规则")
        db.append_event(
            connection, event_type="stop.released", request_id=request_id, entity_type="stop_rule", entity_id=rule_id
        )
    return _result(request_id, changed=1)


def scan_duplicates(db: Database, request_id: str) -> dict[str, Any]:
    changed = 0
    with db.transaction() as connection:
        rows = connection.execute(
            "SELECT company_id,name_normalized,country FROM companies ORDER BY company_id"
        ).fetchall()
        for index, left in enumerate(rows):
            for right in rows[index + 1 :]:
                if (
                    left["name_normalized"]
                    and left["name_normalized"] == right["name_normalized"]
                    and left["country"] == right["country"]
                ):
                    exists = connection.execute(
                        "SELECT 1 FROM duplicate_candidates WHERE entity_type='company' AND left_id=? AND right_id=?",
                        (left["company_id"], right["company_id"]),
                    ).fetchone()
                    if not exists:
                        connection.execute(
                            "INSERT INTO duplicate_candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                            (
                                new_id("dup"),
                                "company",
                                left["company_id"],
                                right["company_id"],
                                "name_country",
                                0.9,
                                "pending",
                                None,
                                None,
                                "",
                            ),
                        )
                        changed += 1
        db.append_event(connection, event_type="dedupe.scanned", request_id=request_id, payload={"candidates": changed})
    return _result(request_id, changed=changed, next_action="人工审核重复候选")


def backup_database(db: Database, destination: Path) -> dict[str, Any]:
    if not db.path.exists():
        raise ValidationError("数据库不存在")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db.path, destination)
    return {"status": "succeeded", "backup": str(destination), "sha256": canonical_hash(destination.read_bytes().hex())}


def record_source_result(
    db: Database, payload: dict[str, Any], idempotency_key: str, request_id: str
) -> dict[str, Any]:
    required = {"run_id", "adapter_id", "outcome"}
    if not required.issubset(payload):
        raise ValidationError("来源结果缺少 run_id/adapter_id/outcome")
    if payload["outcome"] not in SOURCE_OUTCOMES:
        raise ValidationError("无效来源 outcome")
    observations = payload.get("observations", [])
    if not isinstance(observations, list):
        raise ValidationError("observations 必须是数组")
    with db.transaction() as connection:
        prior = db.idempotency_lookup(connection, idempotency_key, payload)
        if prior:
            return prior
        if not connection.execute("SELECT 1 FROM runs WHERE run_id=?", (payload["run_id"],)).fetchone():
            raise ValidationError("来源结果引用不存在的 run")
        source_run_id = str(payload.get("source_run_id") or new_id("src"))
        fingerprint = canonical_hash({"adapter": payload["adapter_id"], "query": payload.get("query_summary", "")})
        connection.execute(
            "INSERT INTO source_runs(source_run_id,run_id,adapter_id,query_summary,query_fingerprint,started_at,finished_at,attempts,outcome,result_count,cost_amount,duration_ms,error_code,retryable) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                source_run_id,
                payload["run_id"],
                payload["adapter_id"],
                str(payload.get("query_summary", "")),
                fingerprint,
                str(payload.get("started_at") or utc_now()),
                str(payload.get("finished_at") or utc_now()),
                int(payload.get("attempts", 1)),
                payload["outcome"],
                len(observations),
                float(payload.get("cost_amount", 0)),
                int(payload.get("duration_ms", 0)),
                str(payload.get("error_code", "")),
                int(bool(payload.get("retryable", False))),
            ),
        )
        changed = 1
        for row in observations:
            if not all(
                str(row.get(key, "")).strip() for key in ("entity_type", "entity_id", "source_url", "observed_text")
            ):
                raise ValidationError("来源观察缺少 entity_type/entity_id/source_url/observed_text")
            if not _entity_exists(connection, str(row["entity_type"]), str(row["entity_id"])):
                raise ValidationError(f"来源观察引用不存在的实体：{row['entity_type']}:{row['entity_id']}")
            connection.execute(
                "INSERT INTO evidence VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    str(row.get("evidence_id") or new_id("ev")),
                    source_run_id,
                    row["entity_type"],
                    row["entity_id"],
                    normalize_url(str(row["source_url"])),
                    str(row.get("source_level", "secondary")),
                    str(row.get("purpose", "")),
                    str(row["observed_text"]),
                    row.get("published_at"),
                    str(row.get("observed_at") or utc_now()),
                    canonical_hash(row["observed_text"]),
                    str(row.get("access_status", "accessible")),
                    int(bool(row.get("conflicts", False))),
                ),
            )
            changed += 1
        result = _result(
            request_id, run_id=payload["run_id"], changed=changed, next_action="检查 Evidence 并提出 Claim"
        )
        result["source_run_id"] = source_run_id
        db.append_event(
            connection,
            event_type="source.recorded",
            request_id=request_id,
            run_id=payload["run_id"],
            entity_type="source_run",
            entity_id=source_run_id,
            payload={"outcome": payload["outcome"]},
        )
        db.idempotency_store(connection, idempotency_key, payload, result)
        return result
