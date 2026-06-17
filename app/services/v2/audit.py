from __future__ import annotations

import json
from typing import Any

from app.database import connect


def record_audit(actor: str, role: str, action: str, target: str, detail: dict[str, Any] | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_logs(actor, role, action, target, detail_json)
            VALUES(?, ?, ?, ?, ?)
            """,
            (actor, role, action, target, json.dumps(detail or {}, ensure_ascii=False)),
        )


def list_audit_logs(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM audit_logs ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    logs = []
    for row in rows:
        item = dict(row)
        item["detail"] = json.loads(item.pop("detail_json") or "{}")
        logs.append(item)
    return logs
