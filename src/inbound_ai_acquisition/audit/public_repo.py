"""公开仓库敏感内容和运行产物检查。"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any

EXCLUDED_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".ruff_cache",
    ".pytest_cache",
    ".mypy_cache",
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


def repository_files(root: Path) -> list[Path]:
    """在 Git 仓库中只审计已跟踪/已暂存文件；普通目录退回全量扫描。"""
    try:
        inside = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--is-inside-work-tree"],
            check=True,
            capture_output=True,
            text=True,
        )
        if inside.stdout.strip() == "true":
            listed = subprocess.run(
                ["git", "-C", str(root), "ls-files", "-z", "--cached"],
                check=True,
                capture_output=True,
            )
            return sorted(
                path
                for item in listed.stdout.decode("utf-8").split("\0")
                if item and (path := root / item).is_file()
            )
    except (FileNotFoundError, subprocess.CalledProcessError, UnicodeDecodeError):
        pass
    return sorted(path for path in root.rglob("*") if path.is_file())


def audit_public_repo(root: Path) -> dict[str, Any]:
    findings: list[dict[str, str]] = []
    for path in repository_files(root):
        if not path.is_file():
            continue
        relative_path = path.relative_to(root)
        relative = relative_path.as_posix()
        # Git 已跟踪文件即使位于忽略目录也会上传，不能静默跳过。
        if any(part in {"outputs", "output", "workspace", "data", "secrets", "uat"} for part in relative_path.parts):
            findings.append({"path": relative, "reason": "私有运行目录不得发布"})
            continue
        if any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in relative_path.parts):
            continue
        if (
            path.name in SENSITIVE_NAMES
            or (path.name.startswith(".env.") and path.name != ".env.example")
            or path.suffix.lower() in {".db", ".sqlite", ".sqlite3", ".xlsx", ".xls", ".jsonl"}
        ):
            findings.append({"path": relative, "reason": "运行数据或敏感文件类型"})
            continue
        if path.stat().st_size > 2_000_000:
            findings.append({"path": relative, "reason": "大文件未自动完成内容审计，请单独复核后调整发布范围"})
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for name, pattern in SECRET_PATTERNS.items():
            if pattern.search(text):
                findings.append({"path": relative, "reason": name})
    return {"status": "succeeded" if not findings else "failed", "findings": findings}
