"""发布清单生成与验证。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .public_repo import EXCLUDED_PARTS, audit_public_repo, repository_files


def _files(root: Path) -> list[Path]:
    return sorted(
        path
        for path in repository_files(root)
        if path.is_file()
        and not any(part in EXCLUDED_PARTS or part.endswith(".egg-info") for part in path.parts)
        and path.name not in {"skills.lock.json", ".coverage"}
        and path.suffix.lower() not in {".pyc", ".xlsx", ".db", ".sqlite"}
    )


def _portable_hash(path: Path) -> str:
    raw = path.read_bytes()
    try:
        normalized = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")
    except UnicodeDecodeError:
        normalized = raw
    return hashlib.sha256(normalized).hexdigest()


def build_lock(root: Path, output: Path) -> dict[str, Any]:
    entries = []
    for path in _files(root):
        entries.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": _portable_hash(path),
            }
        )
    payload = {"schema_version": 1, "file_count": len(entries), "files": entries}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def audit_release(root: Path, lock_path: Path) -> dict[str, Any]:
    public = audit_public_repo(root)
    if public["status"] != "succeeded":
        return {"status": "failed", "errors": public["findings"]}
    if not lock_path.exists():
        return {"status": "failed", "errors": ["缺少 skills.lock.json"]}
    expected = json.loads(lock_path.read_text(encoding="utf-8"))
    actual_output = root / ".skills.lock.check.tmp"
    actual = build_lock(root, actual_output)
    actual_output.unlink()
    if expected != actual:
        return {"status": "failed", "errors": ["skills.lock.json 已过期"]}
    return {"status": "succeeded", "file_count": actual["file_count"]}
