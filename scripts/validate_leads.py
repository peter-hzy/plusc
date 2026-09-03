#!/usr/bin/env python3
"""校验名单 CSV；不会修改输入文件。"""

from __future__ import annotations

import csv
import sys
from pathlib import Path


REQUIRED = {
    "account_id",
    "company_name",
    "country",
    "company_type",
    "website",
    "fit_reason",
    "fit_status",
    "evidence_urls",
    "evidence_date",
    "contact_name",
    "contact_title",
    "contact_linkedin",
    "contact_business_email",
    "email_draft",
    "linkedin_draft",
}
ALLOWED = {"priority_chat", "chat_candidate", "research_needed", "nurture", "not_fit", "do_not_contact"}


def main() -> int:
    if len(sys.argv) != 2:
        print("用法：python validate_leads.py <leads.csv>")
        return 2
    path = Path(sys.argv[1])
    if not path.exists():
        print(f"文件不存在：{path}")
        return 2
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = set(reader.fieldnames or [])
        missing = REQUIRED - fields
        if missing:
            print("LEADS VALIDATION FAILED")
            print("缺少字段：" + ", ".join(sorted(missing)))
            return 1
        rows = list(reader)

    errors: list[str] = []
    seen: set[str] = set()
    for number, row in enumerate(rows, start=2):
        account_id = row["account_id"].strip()
        if not account_id:
            errors.append(f"第 {number} 行缺少 account_id")
        elif account_id in seen:
            errors.append(f"第 {number} 行 account_id 重复：{account_id}")
        seen.add(account_id)
        if row["fit_status"].strip() not in ALLOWED:
            errors.append(f"第 {number} 行 fit_status 无效")
        if row["fit_status"].strip() != "do_not_contact" and not row["evidence_urls"].strip():
            errors.append(f"第 {number} 行缺少 evidence_urls")
        if row["fit_status"].strip() == "do_not_contact" and not row["stop_reason"].strip():
            errors.append(f"第 {number} 行 do_not_contact 必须有 stop_reason")
        if row["contact_business_email"].strip() and "@" not in row["contact_business_email"]:
            errors.append(f"第 {number} 行邮箱格式明显不完整")
        if row["human_review_status"].strip() == "approved" and not row["email_draft"].strip():
            errors.append(f"第 {number} 行 approved 但没有 email_draft")

    if errors:
        print("LEADS VALIDATION FAILED")
        print("\n".join(f"- {error}" for error in errors))
        return 1
    print(f"LEADS VALIDATION PASSED: {len(rows)} rows")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

