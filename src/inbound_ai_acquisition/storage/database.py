"""SQLite 连接、事务、迁移、幂等和事件账本。"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import uuid
from contextlib import closing, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

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
                connection.execute(
                    "UPDATE workspace_meta SET schema_version=?, project_version=?, last_migrated_at=? WHERE singleton=1",
                    (SCHEMA_VERSION, __version__, now),
                )
            else:
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
