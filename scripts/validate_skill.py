#!/usr/bin/env python3
"""检查本地 Skill 包的结构和关键约束。仅读文件，不联网、不写入。"""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED = ["SKILL.md", "README.md", "references", "templates", "scripts"]
REFERENCES = [
    "business-context.md",
    "research-protocol.md",
    "data-contract.md",
    "outreach-protocol.md",
    "reply-retro-protocol.md",
    "safety-and-compliance.md",
    "api-mcp-boundaries.md",
    "open-source-adaptation.md",
]


def fail(message: str, errors: list[str]) -> None:
    errors.append(message)


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    errors: list[str] = []

    for name in REQUIRED:
        if not (root / name).exists():
            fail(f"缺少 {name}", errors)

    skill_path = root / "SKILL.md"
    if skill_path.exists():
        text = skill_path.read_text(encoding="utf-8")
        if not text.startswith("---\n"):
            fail("SKILL.md 缺少 YAML frontmatter", errors)
        if "name: inbound-ai-acquisition" not in text:
            fail("SKILL.md 的 name 不正确", errors)
        if not re.search(r"description:\s*\".+\"", text):
            fail("SKILL.md 的 description 必须是非空引号字符串", errors)
        for reference in REFERENCES:
            if not (root / "references" / reference).exists():
                fail(f"缺少 references/{reference}", errors)
            elif reference not in text:
                fail(f"SKILL.md 未路由到 references/{reference}", errors)
        for marker in ("产品资料", "人工审核", "不自动", "未知"):
            if marker not in text:
                fail(f"SKILL.md 缺少关键约束：{marker}", errors)

    if errors:
        print("VALIDATION FAILED")
        print("\n".join(f"- {item}" for item in errors))
        return 1

    print(f"VALIDATION PASSED: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

