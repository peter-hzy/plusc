"""数据库 JSON 快照。"""

from __future__ import annotations

import json
from contextlib import closing
from pathlib import Path
from typing import Any

from ..storage.database import Database, utc_now

TABLES = (
    "workspace_meta",
    "raw_imports",
    "runs",
    "companies",
    "contacts",
    "entity_keys",
    "source_runs",
    "evidence",
    "claims",
    "claim_evidence",
    "research_gaps",
    "duplicate_candidates",
    "drafts",
    "approvals",
    "replies",
    "stop_rules",
    "events",
)


def export_json(db: Database, output: Path, run_id: str | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"exported_at": utc_now(), "run_id": run_id, "tables": {}}
    with closing(db.connect()) as connection:
        for table in TABLES:
            columns = {row[1] for row in connection.execute(f"PRAGMA table_info({table})")}
            if run_id and "run_id" in columns:
                rows = connection.execute(f"SELECT * FROM {table} WHERE run_id=?", (run_id,)).fetchall()
            else:
                rows = connection.execute(f"SELECT * FROM {table}").fetchall()
            payload["tables"][table] = [dict(row) for row in rows]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "succeeded", "output": str(output), "tables": len(TABLES)}
