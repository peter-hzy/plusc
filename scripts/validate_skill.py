#!/usr/bin/env python3
"""检查 Skill、项目结构、路由和正式运行入口。仅读取仓库。"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REQUIRED_FILES = (
    "SKILL.md", "README.md", "ARCHITECTURE.md", "CHANGELOG.md", "LICENSE",
    "SECURITY.md", "CONTRIBUTING.md", "pyproject.toml", "agents/openai.yaml",
    "src/inbound_ai_acquisition/cli.py",
    "src/inbound_ai_acquisition/storage/migrations.py",
    "src/inbound_ai_acquisition/domain/policies.py",
    "docs/quickstart.md", "docs/cli.md", "docs/data-model.md", "docs/privacy.md", "docs/uat.md",
    ".github/workflows/ci.yml",
)
REFERENCES = (
    "business-context.md", "research-protocol.md", "identity-matching.md", "data-contract.md",
    "outreach-protocol.md", "reply-retro-protocol.md", "safety-and-compliance.md",
    "api-mcp-boundaries.md", "open-source-adaptation.md",
)


def configure_console() -> None:
    """统一为 UTF-8，避免 Windows/CI 的默认代码页掩盖真实检查结果。"""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")


def main() -> int:
    configure_console()
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    errors: list[str] = []
    for relative in REQUIRED_FILES:
        if not (root / relative).is_file():
            errors.append(f"缺少 {relative}")

    skill_path = root / "SKILL.md"
    if skill_path.is_file():
        skill = skill_path.read_text(encoding="utf-8")
        if not skill.startswith("---\n"):
            errors.append("SKILL.md 缺少 YAML frontmatter")
        if "name: inbound-ai-acquisition" not in skill:
            errors.append("SKILL.md name 不正确")
        if not re.search(r'description:\s*"[^\n]+"', skill):
            errors.append("SKILL.md description 缺失")
        for reference in REFERENCES:
            if not (root / "references" / reference).is_file():
                errors.append(f"缺少 references/{reference}")
            elif reference not in skill:
                errors.append(f"SKILL.md 未路由到 {reference}")
        for marker in ("inbound-leads", "SQLite", "人工审核", "不自动", "不猜测", "LinkedIn"):
            if marker not in skill:
                errors.append(f"SKILL.md 缺少关键约束：{marker}")

    pyproject = (root / "pyproject.toml").read_text(encoding="utf-8") if (root / "pyproject.toml").exists() else ""
    if 'inbound-leads = "inbound_ai_acquisition.cli:main"' not in pyproject:
        errors.append("pyproject 未声明 inbound-leads CLI")
    readme = (root / "README.md").read_text(encoding="utf-8") if (root / "README.md").exists() else ""
    for marker in ("git clone", "pip install", "inbound-leads init", "当前验证边界"):
        if marker not in readme:
            errors.append(f"README 缺少冷启动信息：{marker}")

    if errors:
        print("VALIDATION FAILED")
        print("\n".join(f"- {item}" for item in errors))
        return 1
    print(f"VALIDATION PASSED: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
