from __future__ import annotations

import json
from datetime import datetime, timedelta
from typing import Any

from app.database import connect


def utc_now() -> str:
    return datetime.utcnow().isoformat(timespec="seconds")


def publish_message(
    source_agent: str,
    target_agent: str,
    message_type: str,
    payload: dict[str, Any],
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_messages(source_agent, target_agent, message_type, payload_json)
            VALUES(?, ?, ?, ?)
            """,
            (source_agent, target_agent, message_type, json.dumps(payload, ensure_ascii=False)),
        )
        return int(cursor.lastrowid)


def consume_messages(target_agent: str, limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM agent_messages
            WHERE target_agent = ? AND status = 'pending'
            ORDER BY created_at ASC
            LIMIT ?
            """,
            (target_agent, limit),
        ).fetchall()
        ids = [row["id"] for row in rows]
        if ids:
            placeholders = ",".join("?" for _ in ids)
            conn.execute(
                f"""
                UPDATE agent_messages
                SET status = 'processing'
                WHERE id IN ({placeholders})
                """,
                ids,
            )
    messages = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
        messages.append(item)
    return messages


def mark_message(message_id: int, status: str) -> None:
    with connect() as conn:
        conn.execute(
            """
            UPDATE agent_messages
            SET status = ?, processed_at = ?
            WHERE id = ?
            """,
            (status, utc_now(), message_id),
        )


def update_agent_state(
    agent_id: str,
    status: str,
    success: bool | None = None,
    latency_ms: float | None = None,
    error: str | None = None,
    schedule_minutes: int | None = None,
) -> None:
    now = utc_now()
    next_run = (
        (datetime.utcnow() + timedelta(minutes=schedule_minutes)).isoformat(timespec="seconds")
        if schedule_minutes
        else None
    )
    with connect() as conn:
        row = conn.execute(
            "SELECT success_count, failure_count, avg_latency_ms FROM agent_states WHERE agent_id = ?",
            (agent_id,),
        ).fetchone()
        success_count = int(row["success_count"]) if row else 0
        failure_count = int(row["failure_count"]) if row else 0
        avg_latency = float(row["avg_latency_ms"]) if row else 0
        if success is True:
            success_count += 1
        elif success is False:
            failure_count += 1
        if latency_ms is not None:
            total_runs = max(success_count + failure_count, 1)
            avg_latency = round(((avg_latency * (total_runs - 1)) + latency_ms) / total_runs, 2)
        total = success_count + failure_count
        success_rate = round(success_count / total, 4) if total else 1.0
        conn.execute(
            """
            UPDATE agent_states
            SET status = ?,
                last_heartbeat = ?,
                last_run_at = CASE WHEN ? IS NOT NULL THEN ? ELSE last_run_at END,
                next_run_at = COALESCE(?, next_run_at),
                success_count = ?,
                failure_count = ?,
                avg_latency_ms = ?,
                success_rate = ?,
                last_error = ?
            WHERE agent_id = ?
            """,
            (
                status,
                now,
                success,
                now,
                next_run,
                success_count,
                failure_count,
                avg_latency,
                success_rate,
                error,
                agent_id,
            ),
        )


def record_agent_run(
    agent_id: str,
    status: str,
    started_at: str,
    latency_ms: float,
    metrics: dict[str, Any],
    error: str | None = None,
) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_runs(agent_id, status, started_at, finished_at, latency_ms, metrics_json, error)
            VALUES(?, ?, ?, ?, ?, ?, ?)
            """,
            (
                agent_id,
                status,
                started_at,
                utc_now(),
                latency_ms,
                json.dumps(metrics, ensure_ascii=False),
                error,
            ),
        )
        return int(cursor.lastrowid)


def list_agent_states() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_states ORDER BY agent_type"
        ).fetchall()
    states = []
    for row in rows:
        item = dict(row)
        item["config"] = json.loads(item.pop("config_json") or "{}")
        item["enabled"] = bool(item["enabled"])
        states.append(item)
    return states


def recent_messages(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM agent_messages ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    messages = []
    for row in rows:
        item = dict(row)
        item["payload"] = json.loads(item.pop("payload_json") or "{}")
        messages.append(item)
    return messages
