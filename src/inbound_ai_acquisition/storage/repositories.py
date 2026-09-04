"""小型仓储辅助函数，避免业务代码重复拼装常用查询。"""

from __future__ import annotations

import sqlite3


def active_stop_exists(connection: sqlite3.Connection, contact_id: str, company_id: str) -> bool:
    contact = connection.execute("SELECT public_email FROM contacts WHERE contact_id=?", (contact_id,)).fetchone()
    company = connection.execute("SELECT root_domain FROM companies WHERE company_id=?", (company_id,)).fetchone()
    values = [
        ("contact", contact_id),
        ("company", company_id),
    ]
    if contact and contact[0]:
        values.append(("email", contact[0]))
    if company and company[0]:
        values.append(("domain", company[0]))
    return any(
        connection.execute(
            "SELECT 1 FROM stop_rules WHERE scope_type=? AND scope_value=? AND status='active'",
            pair,
        ).fetchone()
        for pair in values
    )


def accepted_claim_count(connection: sqlite3.Connection, company_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM claims WHERE entity_type='company' AND entity_id=? AND status='accepted'",
        (company_id,),
    ).fetchone()
    return int(row[0])


def blocking_gap_count(connection: sqlite3.Connection, company_id: str) -> int:
    row = connection.execute(
        "SELECT COUNT(*) FROM research_gaps WHERE entity_type='company' AND entity_id=? AND blocking=1 AND status='open'",
        (company_id,),
    ).fetchone()
    return int(row[0])
