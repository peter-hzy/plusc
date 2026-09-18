"""小型仓储辅助函数，避免业务代码重复拼装常用查询。"""

from __future__ import annotations

import sqlite3


def active_stop_exists(
    connection: sqlite3.Connection,
    contact_id: str,
    company_id: str,
    *,
    preview_email: str = "",
    preview_linkedin: str = "",
    preview_domain: str = "",
) -> bool:
    contact = connection.execute(
        "SELECT public_email,linkedin_url FROM contacts WHERE contact_id=?", (contact_id,)
    ).fetchone()
    company = connection.execute("SELECT root_domain FROM companies WHERE company_id=?", (company_id,)).fetchone()
    preview_email = preview_email or (contact[0] if contact else "")
    preview_linkedin = preview_linkedin or (contact[1] if contact else "")
    preview_domain = preview_domain or (company[0] if company else "")
    normalized_domain = preview_domain.strip().lower().rstrip(".").removeprefix("www.")
    if normalized_domain:
        for row in connection.execute(
            "SELECT scope_value FROM stop_rules WHERE scope_type='domain' AND status='active'"
        ).fetchall():
            stopped_domain = row[0].strip().lower().rstrip(".").removeprefix("www.")
            if stopped_domain and (
                normalized_domain == stopped_domain or normalized_domain.endswith("." + stopped_domain)
            ):
                return True
    # Conservative linkage to unresolved identities of stopped records, never a license to send.
    for entity_type, field, value in (
        ("contact", "public_email", preview_email),
        ("contact", "linkedin_url", preview_linkedin),
        ("company", "website", "https://" + preview_domain if preview_domain else ""),
    ):
        if not value:
            continue
        stopped_claims = connection.execute(
            "SELECT cl.proposed_value FROM claims cl JOIN stop_rules s "
            "ON s.scope_type=cl.entity_type AND s.scope_value=cl.entity_id "
            "WHERE s.status='active' AND cl.entity_type=? AND cl.field_name=? "
            "AND cl.status IN ('proposed','accepted','held')",
            (entity_type, field),
        ).fetchall()
        for row in stopped_claims:
            if field == "website":
                from urllib.parse import urlsplit

                old_domain = (urlsplit(row[0]).hostname or "").lower().removeprefix("www.")
                if old_domain == preview_domain.lower().removeprefix("www."):
                    return True
            elif row[0].strip().casefold() == value.strip().casefold():
                return True
    # Pending observations must not bypass stops just because formal fields are still empty.
    if preview_email or preview_linkedin or preview_domain:
        for kind, value in (("email", preview_email), ("domain", preview_domain)):
            if (
                value
                and connection.execute(
                    "SELECT 1 FROM stop_rules WHERE scope_type=? AND lower(scope_value)=lower(?) AND status='active'",
                    (kind, value),
                ).fetchone()
            ):
                return True
        if connection.execute(
            "SELECT 1 FROM stop_rules s JOIN contacts c ON s.scope_type='contact' AND s.scope_value=c.contact_id "
            "WHERE s.status='active' AND ((?<>'' AND lower(c.public_email)=lower(?)) OR "
            "(?<>'' AND c.linkedin_url=?))",
            (preview_email, preview_email, preview_linkedin, preview_linkedin),
        ).fetchone():
            return True
        if (
            preview_domain
            and connection.execute(
                "SELECT 1 FROM stop_rules s JOIN companies c ON s.scope_type='company' AND s.scope_value=c.company_id "
                "WHERE s.status='active' AND lower(c.root_domain)=lower(?)",
                (preview_domain,),
            ).fetchone()
        ):
            return True
    values = [
        ("contact", contact_id),
        ("company", company_id),
    ]
    if contact and contact[0]:
        values.append(("email", contact[0]))
    if company and company[0]:
        values.append(("domain", company[0]))
    direct = any(
        connection.execute(
            "SELECT 1 FROM stop_rules WHERE scope_type=? AND scope_value=? AND status='active'",
            pair,
        ).fetchone()
        for pair in values
    )
    if direct:
        return True
    # 联系人/公司停止记录跨研究批次仍有效，不扩大个人拒绝为全公司拒绝。
    if (
        contact
        and connection.execute(
            "SELECT 1 FROM stop_rules s JOIN contacts c ON s.scope_type='contact' AND s.scope_value=c.contact_id "
            "WHERE s.status='active' AND ((?<>'' AND c.public_email=?) OR (?<>'' AND c.linkedin_url=?))",
            (contact[0], contact[0], contact[1], contact[1]),
        ).fetchone()
    ):
        return True
    return bool(
        company
        and company[0]
        and connection.execute(
            "SELECT 1 FROM stop_rules s JOIN companies c ON s.scope_type='company' AND s.scope_value=c.company_id "
            "WHERE s.status='active' AND c.root_domain=?",
            (company[0],),
        ).fetchone()
    )


def accepted_claim_count(connection: sqlite3.Connection, company_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM claims WHERE entity_type='company' AND entity_id=? AND status='accepted'",
        (company_id,),
    ).fetchone()
    return int(row[0])


def blocking_gap_count(connection: sqlite3.Connection, company_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM research_gaps WHERE blocking=1 AND status='open' AND "
        "((entity_type='company' AND entity_id=?) OR (entity_type='contact' AND entity_id IN "
        "(SELECT contact_id FROM contacts WHERE company_id=?)))",
        (company_id, company_id),
    ).fetchone()
    return int(row[0])
