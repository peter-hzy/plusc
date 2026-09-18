"""开发信证据与发送快照。技术可达、身份和营销依据分别核验。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from ..errors import StateError, ValidationError
from ..storage.database import canonical_hash


def validate_product_binding(connection: Any, run_id: str, product_version: str) -> None:
    run = connection.execute("SELECT product_version FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run or not str(run[0]).strip():
        raise StateError("研究批次没有实际产品版本；提供产品后新建批次重评，不能直接准备外联")
    if not isinstance(product_version, str) or product_version != run[0]:
        raise StateError("草稿产品版本必须与本批次已登记产品版本一致")


def accepted_draft_claims(connection: Any, contact: Any, evidence_ids: list[str]) -> list[str]:
    """每条引用都必须由当前公司或联系人的已接受事实支持。"""
    claims: set[str] = set()
    for evidence_id in evidence_ids:
        rows = connection.execute(
            "SELECT cl.claim_id FROM claims cl JOIN claim_evidence ce ON ce.claim_id=cl.claim_id "
            "JOIN evidence e ON e.evidence_id=ce.evidence_id WHERE ce.evidence_id=? "
            "AND cl.status='accepted' AND e.conflicts=0 AND e.access_status='accessible' "
            "AND ((cl.entity_type='company' AND cl.entity_id=?) OR "
            "(cl.entity_type='contact' AND cl.entity_id=?))",
            (evidence_id, contact["company_id"], contact["contact_id"]),
        ).fetchall()
        if not rows:
            raise StateError("草稿引用的每条证据都必须关联当前客户的已接受且无冲突事实")
        claims.update(row[0] for row in rows)
    return sorted(claims)


def contract_for(contact: Any, payload: dict[str, Any], claims: list[str]) -> dict[str, Any]:
    supplied = payload.get("outreach_contract", {})
    if not isinstance(supplied, dict):
        raise ValidationError("outreach_contract 必须是对象")
    allowed = {
        "recipient",
        "recipient_kind",
        "address_status",
        "role_reason",
        "consent",
        "product_approved_by",
        "attachments",
        "fact_checked_by",
        "primary_cta",
    }
    if set(supplied) - allowed:
        raise ValidationError("outreach_contract 存在未知字段")
    for key in allowed - {"attachments", "consent"}:
        if key in supplied and not isinstance(supplied[key], str):
            raise ValidationError(f"{key}必须是文本")
    if "consent" in supplied and not isinstance(supplied["consent"], dict):
        raise ValidationError("consent必须是对象")
    default_address = contact["public_email"] if payload["channel"] == "email" else contact["linkedin_url"]
    contract = {
        "recipient": default_address,
        "recipient_kind": "unknown",
        "address_status": "unknown",
        "role_reason": contact["role_scope"],
        "consent": {},
        "product_approved_by": "",
        "attachments": [],
        "fact_checked_by": "",
        "primary_cta": "",
        **supplied,
        "claim_ids": claims,
    }
    if contract["recipient"] != default_address:
        raise ValidationError("收件地址必须与已核验联系人当前渠道一致")
    if contract["recipient_kind"] not in {"person", "department", "company", "unknown"}:
        raise ValidationError("recipient_kind 必须明确个人、部门、公司或未知")
    if contract["address_status"] not in {"valid", "published", "accept_all", "unknown", "invalid"}:
        raise ValidationError("address_status 无效")
    if not isinstance(contract["attachments"], list) or any(
        not isinstance(a, dict) or not a.get("name") or not a.get("sha256") for a in contract["attachments"]
    ):
        raise ValidationError("附件必须记录名称和内容哈希")
    return contract


def load_contract(connection: Any, draft_id: str) -> dict[str, Any]:
    row = connection.execute("SELECT contract_json FROM draft_contracts WHERE draft_id=?", (draft_id,)).fetchone()
    if not row:
        raise StateError("旧草稿缺少完整联系合同，请重新创建后审核")
    return json.loads(row[0])


def evidence_fingerprint(connection: Any, claim_ids: list[str], evidence_ids: list[str]) -> str:
    claims = [dict(connection.execute("SELECT * FROM claims WHERE claim_id=?", (cid,)).fetchone()) for cid in claim_ids]
    evidence = [
        dict(connection.execute("SELECT * FROM evidence WHERE evidence_id=?", (eid,)).fetchone())
        for eid in evidence_ids
    ]
    return canonical_hash({"claims": claims, "evidence": evidence})


def validate_for_approval(connection: Any, draft: Any, contract: dict[str, Any]) -> None:
    validate_product_binding(connection, draft["run_id"], draft["product_version"])
    contact = connection.execute("SELECT * FROM contacts WHERE contact_id=?", (draft["contact_id"],)).fetchone()
    if not contact or contact["identity_status"] not in {"supported", "verified"}:
        raise StateError("联系人身份当前未核验或已发生冲突")
    if connection.execute(
        "SELECT 1 FROM research_gaps WHERE status='open' AND blocking=1 AND "
        "((entity_type='company' AND entity_id=?) OR (entity_type='contact' AND entity_id=?))",
        (draft["company_id"], draft["contact_id"]),
    ).fetchone():
        raise StateError("仍有阻止外联的研究缺口")
    address = contact["public_email"] if draft["channel"] == "email" else contact["linkedin_url"]
    if not address or address != contract["recipient"]:
        raise StateError("收件地址缺失或已改变，请重新创建草稿")
    if contract["recipient_kind"] == "unknown" or contract["address_status"] not in {"valid", "published"}:
        raise StateError("联系方式归属或可用性尚未确认")
    if not contract["role_reason"] or not contract["fact_checked_by"]:
        raise StateError("缺少职责相关性说明或文案事实复核人")
    if not draft["product_version"] or not contract["product_approved_by"]:
        raise StateError("缺少已批准的产品资料版本")
    consent = contract.get("consent")
    if not isinstance(consent, dict) or consent.get("basis") not in {"express", "inferred", "deemed"}:
        raise StateError("缺少已审核的适用触达依据，公开邮箱不自动代表同意")
    for field in ("market", "source_reference", "reason", "reviewed_by", "valid_until"):
        if not consent.get(field):
            raise StateError(f"触达依据缺少 {field}")
    company = connection.execute("SELECT * FROM companies WHERE company_id=?", (contact["company_id"],)).fetchone()
    fit = {
        r["field_name"]: r["proposed_value"]
        for r in connection.execute(
            "SELECT field_name,proposed_value FROM claims WHERE entity_type='company' AND entity_id=? AND status='accepted'",
            (contact["company_id"],),
        ).fetchall()
    }
    if (
        fit.get("source_market_role") != "outbound_seller"
        or fit.get("china_product_signal") not in {"direct", "adjacent"}
        or fit.get("ground_partner_route") not in {"external_partner_possible", "unclear", "in_house"}
        or fit.get("competitive_position") not in {"potential_buyer", "mixed", "unknown"}
    ):
        raise StateError("缺少已核验的旅游客源买方适配事实")
    if company["fit_status"] in {"not_fit", "do_not_contact", "research_needed", "nurture"}:
        raise StateError("客户当前不在可联系状态")
    if consent["market"] != company["country"]:
        raise StateError("触达依据市场与客户市场不一致")
    try:
        expiry = datetime.fromisoformat(str(consent["valid_until"]).replace("Z", "+00:00"))
        if expiry.tzinfo is None or expiry <= datetime.now(timezone.utc):
            raise ValueError()
    except (ValueError, TypeError):
        raise StateError("触达依据过期或 valid_until 缺少时区") from None
    current_claims = accepted_draft_claims(connection, contact, json.loads(draft["evidence_ids"]))
    if not set(contract["claim_ids"]).issubset(current_claims):
        raise StateError("引用事实已撤回或变化，请重新审核")
    if contract.get("evidence_fingerprint") != evidence_fingerprint(
        connection, contract["claim_ids"], json.loads(draft["evidence_ids"])
    ):
        raise StateError("事实或证据内容已改变，请重新创建草稿")


def approval_fingerprint(draft: Any, contract: dict[str, Any]) -> str:
    fields = ("run_id", "company_id", "contact_id", "channel", "subject", "body", "evidence_ids", "product_version")
    return canonical_hash({"draft": {k: draft[k] for k in fields}, "contract": contract})
