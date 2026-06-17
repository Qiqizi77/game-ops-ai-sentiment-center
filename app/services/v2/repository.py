from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from app.database import connect


def upsert_analysis_insight(insight: dict[str, Any]) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO analysis_insights(
                post_id, emotion, intent, entities_json, relevance, confidence,
                llm_provider, prompt_version, bilingual_summary
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(post_id) DO UPDATE SET
                emotion = excluded.emotion,
                intent = excluded.intent,
                entities_json = excluded.entities_json,
                relevance = excluded.relevance,
                confidence = excluded.confidence,
                llm_provider = excluded.llm_provider,
                prompt_version = excluded.prompt_version,
                bilingual_summary = excluded.bilingual_summary,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                insight["post_id"],
                insight["emotion"],
                insight["intent"],
                json.dumps(insight["entities"], ensure_ascii=False),
                insight["relevance"],
                insight["confidence"],
                insight["llm_provider"],
                insight["prompt_version"],
                insight["bilingual_summary"],
            ),
        )


def list_analysis_insights(limit: int = 100) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT ai.*, p.title, p.platform_name, p.game_version, p.category, p.sentiment_score
            FROM analysis_insights ai
            LEFT JOIN posts p ON p.id = ai.post_id
            ORDER BY ai.updated_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    insights = []
    for row in rows:
        item = dict(row)
        item["entities"] = json.loads(item.pop("entities_json") or "{}")
        insights.append(item)
    return insights


def upsert_cluster(game_id: str, cluster: dict[str, Any]) -> int:
    with connect() as conn:
        row = conn.execute(
            "SELECT id FROM issue_clusters WHERE game_id = ? AND cluster_key = ?",
            (game_id, cluster["cluster_key"]),
        ).fetchone()
        if row:
            cluster_id = int(row["id"])
            conn.execute(
                """
                UPDATE issue_clusters
                SET label = ?, size = ?, growth_2h = ?, avg_sentiment = ?,
                    keywords_json = ?, post_ids_json = ?, severity = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
                """,
                (
                    cluster["label"],
                    cluster["size"],
                    cluster["growth_2h"],
                    cluster["avg_sentiment"],
                    json.dumps(cluster["keywords"], ensure_ascii=False),
                    json.dumps(cluster["post_ids"], ensure_ascii=False),
                    cluster["severity"],
                    cluster_id,
                ),
            )
            return cluster_id
        cursor = conn.execute(
            """
            INSERT INTO issue_clusters(
                game_id, cluster_key, label, size, growth_2h, avg_sentiment,
                keywords_json, post_ids_json, severity
            )
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                game_id,
                cluster["cluster_key"],
                cluster["label"],
                cluster["size"],
                cluster["growth_2h"],
                cluster["avg_sentiment"],
                json.dumps(cluster["keywords"], ensure_ascii=False),
                json.dumps(cluster["post_ids"], ensure_ascii=False),
                cluster["severity"],
            ),
        )
        return int(cursor.lastrowid)


def list_clusters(game_id: str = "zzz", limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM issue_clusters
            WHERE game_id = ?
            ORDER BY severity DESC, size DESC, updated_at DESC
            LIMIT ?
            """,
            (game_id, limit),
        ).fetchall()
    clusters = []
    for row in rows:
        item = dict(row)
        item["keywords"] = json.loads(item.pop("keywords_json") or "[]")
        item["post_ids"] = json.loads(item.pop("post_ids_json") or "[]")
        clusters.append(item)
    return clusters


def create_alert(alert: dict[str, Any]) -> int:
    with connect() as conn:
        existing = conn.execute(
            """
            SELECT id FROM alerts
            WHERE status = 'open' AND game_id = ? AND title = ? AND level = ?
            """,
            (alert.get("game_id", "zzz"), alert["title"], alert["level"]),
        ).fetchone()
        if existing:
            return int(existing["id"])
        cursor = conn.execute(
            """
            INSERT INTO alerts(game_id, level, title, reason, platform, category, keyword, cluster_id, push_channel)
            VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                alert.get("game_id", "zzz"),
                alert["level"],
                alert["title"],
                alert["reason"],
                alert.get("platform"),
                alert.get("category"),
                alert.get("keyword"),
                alert.get("cluster_id"),
                alert.get("push_channel", "mock"),
            ),
        )
        return int(cursor.lastrowid)


def list_alerts(game_id: str = "zzz", status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    clauses = ["game_id = :game_id"]
    params: dict[str, Any] = {"game_id": game_id, "limit": limit}
    if status:
        clauses.append("status = :status")
        params["status"] = status
    where_sql = " AND ".join(clauses)
    with connect() as conn:
        rows = conn.execute(
            f"""
            SELECT * FROM alerts
            WHERE {where_sql}
            ORDER BY level DESC, created_at DESC
            LIMIT :limit
            """,
            params,
        ).fetchall()
    return [dict(row) for row in rows]


def create_work_order(alert_id: int, title: str, priority: str = "P1", assignee: str = "发行运营值班") -> int:
    external_ref = f"MOCK-JIRA-{datetime.utcnow().strftime('%Y%m%d')}-{alert_id}"
    with connect() as conn:
        existing = conn.execute(
            "SELECT id FROM work_orders WHERE alert_id = ?",
            (alert_id,),
        ).fetchone()
        if existing:
            return int(existing["id"])
        cursor = conn.execute(
            """
            INSERT INTO work_orders(alert_id, title, priority, assignee, external_ref)
            VALUES(?, ?, ?, ?, ?)
            """,
            (alert_id, title, priority, assignee, external_ref),
        )
        return int(cursor.lastrowid)


def list_work_orders(limit: int = 50) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM work_orders ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def save_agent_report(report_type: str, game_id: str, title: str, markdown: str) -> int:
    with connect() as conn:
        cursor = conn.execute(
            """
            INSERT INTO agent_reports(report_type, game_id, title, markdown)
            VALUES(?, ?, ?, ?)
            """,
            (report_type, game_id, title, markdown),
        )
        return int(cursor.lastrowid)


def list_agent_reports(game_id: str = "zzz", limit: int = 20) -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT * FROM agent_reports
            WHERE game_id = ?
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (game_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def update_collector_offset(platform: str, last_post_id: str, last_timestamp: int, success: bool, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            """
            INSERT INTO collector_offsets(
                platform, last_post_id, last_timestamp, success_count, failure_count, last_success_at, last_error
            )
            VALUES(?, ?, ?, ?, ?, CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END, ?)
            ON CONFLICT(platform) DO UPDATE SET
                last_post_id = excluded.last_post_id,
                last_timestamp = MAX(collector_offsets.last_timestamp, excluded.last_timestamp),
                success_count = collector_offsets.success_count + excluded.success_count,
                failure_count = collector_offsets.failure_count + excluded.failure_count,
                last_success_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE collector_offsets.last_success_at END,
                last_error = excluded.last_error
            """,
            (
                platform,
                last_post_id,
                last_timestamp,
                1 if success else 0,
                0 if success else 1,
                success,
                error,
                success,
            ),
        )


def list_collector_offsets() -> list[dict[str, Any]]:
    with connect() as conn:
        rows = conn.execute("SELECT * FROM collector_offsets ORDER BY platform").fetchall()
    return [dict(row) for row in rows]
