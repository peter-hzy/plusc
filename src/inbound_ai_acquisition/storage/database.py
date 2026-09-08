"""SQLite 连接、事务、迁移、幂等和事件账本。"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator
from urllib.parse import urlsplit

from .. import __version__
from ..errors import IdempotencyConflict, ValidationError
from .migrations import INITIAL_SQL, SCHEMA_VERSION


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def canonical_hash(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _legacy_normalize_name(value: str) -> str:
    value = re.sub(r"[^\w\s]", " ", value.casefold())
    return re.sub(r"\s+", " ", value).strip()


def _legacy_root_domain(value: str) -> str:
    host = (urlsplit(value if "://" in value else "https://" + value).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _backfill_v2_discovery(connection: sqlite3.Connection) -> None:
    """从旧事件恢复候选清单；缺失的原始观察明确标为迁移说明。"""
    events = connection.execute(
        "SELECT run_id,payload_json,created_at FROM events WHERE event_type='research.sources_ingested'"
    ).fetchall()
    for event in events:
        payload = json.loads(event["payload_json"])
        candidates = payload.get("discovered_candidates", [])
        if not isinstance(candidates, list) or not candidates:
            continue
        run_id = event["run_id"]
        if connection.execute("SELECT 1 FROM candidates WHERE run_id=?", (run_id,)).fetchone():
            continue
        now = event["created_at"]
        source_run = connection.execute(
            "SELECT source_run_id,query_summary FROM source_runs WHERE run_id=? AND adapter_id='codex_bridge' "
            "ORDER BY started_at LIMIT 1",
            (run_id,),
        ).fetchone()
        if source_run:
            source_run_id = source_run["source_run_id"]
            query_summary = source_run["query_summary"]
        else:
            source_run_id = new_id("src")
            query_summary = "Legacy Codex discovery recovered from event ledger"
            connection.execute(
                "INSERT INTO source_runs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    source_run_id,
                    run_id,
                    "codex_bridge",
                    query_summary,
                    canonical_hash({"adapter": "codex_bridge", "query": query_summary}),
                    now,
                    now,
                    1,
                    "succeeded",
                    len(candidates),
                    0.0,
                    0,
                    "",
                    0,
                ),
            )
        connection.execute(
            "INSERT OR IGNORE INTO source_plan_entries VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (
                new_id("plan"),
                run_id,
                "legacy_codex_discovery",
                "discover",
                "旧版候选公司发现",
                query_summary,
                "旧版未保存细分覆盖信息",
                "migrated",
                "候选名称和URL已恢复；来源分类与完整观察不可追溯",
                now,
                now,
            ),
        )
        selected_by_name = {
            row["name_normalized"]: row["company_id"]
            for row in connection.execute(
                "SELECT company_id,name_normalized FROM companies WHERE run_id=?", (run_id,)
            ).fetchall()
        }
        for row in candidates:
            name = str(row.get("name", "")).strip()
            source_url = str(row.get("source_url", "")).strip()
            normalized = _legacy_normalize_name(name)
            if not normalized or not source_url:
                continue
            company_id = selected_by_name.get(normalized)
            segment_hint = ""
            country_hint = ""
            if company_id:
                hints = connection.execute(
                    "SELECT field_name,proposed_value FROM claims WHERE entity_type='company' AND entity_id=? "
                    "AND field_name IN ('country','segment') AND status IN ('proposed','accepted') ORDER BY created_at",
                    (company_id,),
                ).fetchall()
                values = {hint["field_name"]: hint["proposed_value"] for hint in hints}
                segment_hint = str(values.get("segment", ""))
                country_hint = str(values.get("country", ""))
            candidate_id = new_id("cand")
            connection.execute(
                "INSERT OR IGNORE INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    candidate_id,
                    run_id,
                    name,
                    normalized,
                    _legacy_root_domain(source_url),
                    source_url,
                    country_hint,
                    segment_hint,
                    "selected" if company_id else "candidate_pool",
                    "从旧版 research.sources_ingested 事件恢复；未入选原因当时未保存",
                    company_id,
                    now,
                    now,
                ),
            )
            stored = connection.execute(
                "SELECT candidate_id FROM candidates WHERE run_id=? AND name_normalized=?",
                (run_id, normalized),
            ).fetchone()
            if not stored:
                continue
            discovery_evidence = (
                connection.execute(
                    "SELECT observed_text,observed_at FROM evidence WHERE entity_type='company' "
                    "AND entity_id=? AND purpose='discovery' ORDER BY observed_at LIMIT 1",
                    (company_id,),
                ).fetchone()
                if company_id
                else None
            )
            observed_text = (
                discovery_evidence["observed_text"]
                if discovery_evidence
                else "旧版迁移仅恢复候选名称和来源URL；原始发现摘要当时没有独立保存。"
            )
            observed_at = discovery_evidence["observed_at"] if discovery_evidence else now
            connection.execute(
                "INSERT OR IGNORE INTO candidate_sources VALUES (?,?,?,?,?,?,?,?)",
                (
                    new_id("csrc"),
                    run_id,
                    stored["candidate_id"],
                    source_run_id,
                    "legacy_codex_discovery",
                    source_url,
                    observed_text,
                    observed_at,
                ),
            )


def _migrate_v3_run_policy(connection: sqlite3.Connection) -> None:
    """把发现基线变成批次配置，并将公司域名去重收窄到同一批次。"""
    columns = {row["name"] for row in connection.execute("PRAGMA table_info(runs)").fetchall()}
    if "candidate_pool_multiplier" not in columns:
        connection.execute("ALTER TABLE runs ADD COLUMN candidate_pool_multiplier REAL NOT NULL DEFAULT 3.0")
    if "min_source_categories" not in columns:
        connection.execute("ALTER TABLE runs ADD COLUMN min_source_categories INTEGER NOT NULL DEFAULT 3")
    if "production_min_target" not in columns:
        connection.execute("ALTER TABLE runs ADD COLUMN production_min_target INTEGER NOT NULL DEFAULT 20")
    connection.execute("DROP INDEX IF EXISTS uq_company_domain")
    connection.execute("DROP INDEX IF EXISTS uq_active_entity_key")
    duplicates = connection.execute(
        "SELECT run_id,root_domain FROM candidates WHERE root_domain<>'' "
        "GROUP BY run_id,root_domain HAVING COUNT(*)>1"
    ).fetchall()
    for duplicate in duplicates:
        rows = connection.execute(
            "SELECT candidate_id,selected_company_id,discovery_status FROM candidates "
            "WHERE run_id=? AND root_domain=? ORDER BY first_seen_at,candidate_id",
            (duplicate["run_id"], duplicate["root_domain"]),
        ).fetchall()
        keeper = rows[0]
        selected_company_id = keeper["selected_company_id"]
        for row in rows[1:]:
            for source in connection.execute(
                "SELECT candidate_source_id,source_url FROM candidate_sources WHERE candidate_id=?",
                (row["candidate_id"],),
            ).fetchall():
                already = connection.execute(
                    "SELECT 1 FROM candidate_sources WHERE candidate_id=? AND source_url=?",
                    (keeper["candidate_id"], source["source_url"]),
                ).fetchone()
                if already:
                    connection.execute(
                        "DELETE FROM candidate_sources WHERE candidate_source_id=?", (source["candidate_source_id"],)
                    )
                else:
                    connection.execute(
                        "UPDATE candidate_sources SET candidate_id=? WHERE candidate_source_id=?",
                        (keeper["candidate_id"], source["candidate_source_id"]),
                    )
            if not selected_company_id and row["selected_company_id"]:
                selected_company_id = row["selected_company_id"]
            connection.execute("DELETE FROM candidates WHERE candidate_id=?", (row["candidate_id"],))
        if selected_company_id:
            connection.execute(
                "UPDATE candidates SET selected_company_id=?,discovery_status='selected' WHERE candidate_id=?",
                (selected_company_id, keeper["candidate_id"]),
            )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_company_run_domain ON companies(run_id,root_domain) "
        "WHERE root_domain<>''"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_candidate_run_domain ON candidates(run_id,root_domain) "
        "WHERE root_domain<>''"
    )
    connection.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_active_entity_key "
        "ON entity_keys(entity_type,entity_id,key_type,normalized_value) WHERE status='active'"
    )


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)

    def connect(self) -> sqlite3.Connection:
        if not self.path.parent.exists():
            raise ValidationError(f"工作区不存在：{self.path.parent}")
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        return connection

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        connection = self.connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def migrate(self) -> dict[str, Any]:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as connection:
            connection.executescript(INITIAL_SQL)
            now = utc_now()
            current = connection.execute("SELECT schema_version FROM workspace_meta WHERE singleton=1").fetchone()
            if current and int(current[0]) > SCHEMA_VERSION:
                raise ValidationError("数据库版本高于当前程序，不能降级打开")
            if current:
                if int(current[0]) < 2:
                    _backfill_v2_discovery(connection)
                if int(current[0]) < 3:
                    _migrate_v3_run_policy(connection)
                connection.execute(
                    "UPDATE workspace_meta SET schema_version=?, project_version=?, last_migrated_at=? WHERE singleton=1",
                    (SCHEMA_VERSION, __version__, now),
                )
            else:
                _migrate_v3_run_policy(connection)
                connection.execute(
                    "INSERT INTO workspace_meta VALUES (1,?,?,?,?,?)",
                    (SCHEMA_VERSION, __version__, new_id("ws"), now, now),
                )
            connection.commit()
        return {"schema_version": SCHEMA_VERSION, "database": str(self.path)}

    def schema_version(self) -> int | None:
        if not self.path.exists():
            return None
        with closing(self.connect()) as connection:
            try:
                row = connection.execute("SELECT schema_version FROM workspace_meta WHERE singleton=1").fetchone()
            except sqlite3.OperationalError:
                return None
        return int(row[0]) if row else None

    def idempotency_lookup(self, connection: sqlite3.Connection, key: str, payload: Any) -> dict[str, Any] | None:
        row = connection.execute(
            "SELECT input_hash,result_json FROM idempotency WHERE idempotency_key=?", (key,)
        ).fetchone()
        if not row:
            return None
        if row["input_hash"] != canonical_hash(payload):
            raise IdempotencyConflict("同一 idempotency_key 对应的输入不同")
        result = json.loads(row["result_json"])
        result["status"] = "already_applied"
        result["changed_records"] = 0
        return result

    def idempotency_store(self, connection: sqlite3.Connection, key: str, payload: Any, result: dict[str, Any]) -> None:
        connection.execute(
            "INSERT INTO idempotency VALUES (?,?,?,?)",
            (key, canonical_hash(payload), json.dumps(result, ensure_ascii=False), utc_now()),
        )

    def append_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        request_id: str,
        run_id: str | None = None,
        entity_type: str = "",
        entity_id: str = "",
        payload: Any = None,
    ) -> str:
        row = connection.execute(
            "SELECT COALESCE(MAX(sequence),0)+1 FROM events WHERE run_id IS ?", (run_id,)
        ).fetchone()
        event_id = new_id("evt")
        connection.execute(
            "INSERT INTO events VALUES (?,?,?,?,?,?,?,?,?)",
            (
                event_id,
                run_id,
                int(row[0]),
                event_type,
                entity_type,
                entity_id,
                request_id,
                json.dumps(payload or {}, ensure_ascii=False),
                utc_now(),
            ),
        )
        return event_id

    def query(self, sql: str, params: tuple[Any, ...] = ()) -> list[dict[str, Any]]:
        with closing(self.connect()) as connection:
            return [dict(row) for row in connection.execute(sql, params).fetchall()]
