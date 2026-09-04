#!/usr/bin/env python3
"""三遍静态检查：结构、业务闭环和风险边界。"""

from __future__ import annotations

import sys
from pathlib import Path


def check(root: Path) -> list[tuple[str, list[str]]]:
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    refs = "\n".join(path.read_text(encoding="utf-8") for path in (root / "references").glob("*.md"))
    sources = "\n".join(path.read_text(encoding="utf-8") for path in (root / "src").rglob("*.py"))

    structure_required = (
        "SKILL.md", "README.md", "ARCHITECTURE.md", "pyproject.toml", "src", "docs",
        "references", "templates", "scripts", "tests", ".github/workflows/ci.yml",
    )
    structural = [f"缺少 {item}" for item in structure_required if not (root / item).exists()]

    business_markers = (
        "20—25", "澳大利亚", "新西兰", "旅行社", "DMC", "LinkedIn", "人工审核",
        "Evidence", "Claim", "inbound-leads", "reply ingest", "export workbook",
    )
    business = [f"缺少业务闭环：{item}" for item in business_markers if item not in skill + refs]
    if "CREATE TABLE IF NOT EXISTS events" not in sources:
        business.append("缺少事件账本")
    if "idempotency_lookup" not in sources:
        business.append("缺少幂等保护")

    safety_markers = ("不自动发送", "Cookie", "密码", "退订", "不猜", "外部网页")
    safety = [f"缺少安全边界：{item}" for item in safety_markers if item not in skill + refs]
    forbidden_source = {
        "verify=False": "发现关闭TLS校验",
        "smtplib.SMTP": "发现自动邮件发送实现",
        "selenium.webdriver": "发现浏览器自动登录实现",
    }
    safety.extend(message for marker, message in forbidden_source.items() if marker in sources)
    return [("结构", structural), ("业务逻辑", business), ("安全边界", safety)]


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    results = check(root)
    print("THREE-PASS CHECK")
    for name, errors in results:
        print(f"{name}: {'通过' if not errors else '失败'}")
        for error in errors:
            print(f"- {error}")
    return 0 if all(not errors for _, errors in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

