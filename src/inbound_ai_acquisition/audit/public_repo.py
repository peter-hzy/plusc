"""公开仓库敏感内容和运行产物检查。"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    "build",
    "dist",
    "outputs",
    "workspace",
    "data",
}
SENSITIVE_NAMES = {".env", "acquisition.db"}
SECRET_PATTERNS = {
    "private_key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    "github_token": re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    "generic_secret": re.compile(r"(?im)(api[_-]?key|secret|password)[ \t]*[:=][ \t]*['\"]?[A-Za-z0-9_\-]{16,}"),
}


def audit_public_repo(root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for path in root.rglob("*"):
        if not path.is_file() or any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in path.parts):
            continue
        relative = path.relative_to(root).as_posix()
        if path.name in SENSITIVE_NAMES or path.suffix.lower() in {".db", ".sqlite", ".xlsx"}:
            findings.append({"path": relative, "reason": "运行数据或敏感文件类型"})
            continue
        if path.stat().st_size > 2_000_000:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"path": relative, "reason": name})
    return {"status": "succeeded" if not findings else "failed", "findings": findings}
