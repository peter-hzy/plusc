#!/usr/bin/env python3
"""执行三遍本地检查：结构、业务逻辑、安全边界。"""

from __future__ import annotations

import sys
from pathlib import Path


def check(root: Path) -> list[tuple[str, str]]:
    results: list[tuple[str, str]] = []
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    refs = "\n".join(path.read_text(encoding="utf-8") for path in (root / "references").glob("*.md"))

    structural = all((root / item).exists() for item in ("SKILL.md", "README.md", "agents/openai.yaml", "references", "templates", "scripts", "tests"))
    results.append(("结构", "通过" if structural else "失败"))

    business_terms = ("20—25", "澳大利亚", "新西兰", "旅行社", "DMC", "LinkedIn", "人工审核")
    business_ok = all(term in skill or term in refs for term in business_terms)
    results.append(("业务逻辑", "通过" if business_ok else "失败"))

    safety_terms = ("不自动", "Cookie", "密码", "退订", "未知", "外部网页")
    safety_ok = all(term in skill or term in refs for term in safety_terms)
    results.append(("安全边界", "通过" if safety_ok else "失败"))
    return results


def main() -> int:
    root = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
    results = check(root)
    print("THREE-PASS CHECK")
    for name, result in results:
        print(f"{name}: {result}")
    return 0 if all(result == "通过" for _, result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

