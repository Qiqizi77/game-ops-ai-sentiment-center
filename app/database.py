from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from contextlib import contextmanager
from datetime import date
from typing import Any

from app.config import AGENT_CONFIG, DATA_DIR, DB_PATH, GAMES, VERSIONS


@contextmanager
def connect() -> Iterable[sqlite3.Connection]:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db() -> None:
    with connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS versions (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                release_date TEXT NOT NULL,
                end_date TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                platform TEXT NOT NULL,
                platform_name TEXT NOT NULL,
                game_version TEXT NOT NULL,
                post_id TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                author TEXT NOT NULL,
                like_count INTEGER NOT NULL DEFAULT 0,
                reply_count INTEGER NOT NULL DEFAULT 0,
                publish_time TEXT NOT NULL,
                timestamp INTEGER NOT NULL,
                url TEXT NOT NULL,
                category TEXT NOT NULL,
                sentiment_score REAL NOT NULL,
                keywords TEXT NOT NULL,
                warning_level INTEGER NOT NULL DEFAULT 0,
                is_early_feedback INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );

            CREATE INDEX IF NOT EXISTS idx_posts_version ON posts(game_version);
            CREATE INDEX IF NOT EXISTS idx_posts_platform ON posts(platform);
            CREATE INDEX IF NOT EXISTS idx_posts_category ON posts(category);
            CREATE INDEX IF NOT EXISTS idx_posts_publish_time ON posts(publish_time);
            CREATE INDEX IF NOT EXISTS idx_posts_warning ON posts(warning_level);
            """
        )
        ensure_column(conn, "versions", "end_date", "TEXT")
        ensure_column(conn, "posts", "game_id", "TEXT NOT NULL DEFAULT 'zzz'")
        conn.executemany(
            """
            INSERT INTO versions(version, name, release_date, end_date)
            VALUES(:version, :name, :release_date, :end_date)
            ON CONFLICT(version) DO UPDATE SET
                name = excluded.name,
                release_date = excluded.release_date,
                end_date = excluded.end_date
            """,
            VERSIONS,
        )
        placeholders = ",".join("?" for _ in VERSIONS)
        conn.execute(
            f"DELETE FROM versions WHERE version NOT IN ({placeholders})",
            [item["version"] for item in VERSIONS],
        )
        init_v2_tables(conn)


def post_count() -> int:
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0])


def insert_posts(posts: list[dict[str, Any]]) -> int:
    if not posts:
        return 0

    normalized = []
    for post in posts:
        item = dict(post)
        keywords = item.get("keywords", [])
        item["keywords"] = json.dumps(keywords, ensure_ascii=False)
        item["game_id"] = item.get("game_id") or "zzz"
        normalized.append(item)

    with connect() as conn:
        before = conn.total_changes
        conn.executemany(
            """
            INSERT OR IGNORE INTO posts (
                id, platform, platform_name, game_version, post_id, title, content,
                author, like_count, reply_count, publish_time, timestamp, url,
                category, sentiment_score, keywords, warning_level, is_early_feedback,
                game_id
            )
            VALUES (
                :id, :platform, :platform_name, :game_version, :post_id, :title,
                :content, :author, :like_count, :reply_count, :publish_time,
                :timestamp, :url, :category, :sentiment_score, :keywords,
                :warning_level, :is_early_feedback, :game_id
            )
            """,
            normalized,
        )
        return conn.total_changes - before


def list_versions() -> list[dict[str, Any]]:
    today = date.today()
    with connect() as conn:
        rows = conn.execute(
            "SELECT version, name, release_date, end_date FROM versions ORDER BY release_date DESC"
        ).fetchall()
    versions = []
    for row in rows:
        release = date.fromisoformat(row["release_date"])
        versions.append(
            {
                "version": row["version"],
                "name": row["name"],
                "release_date": row["release_date"],
                "end_date": row["end_date"],
                "days_since_release": max((today - release).days, 0),
            }
        )
    return versions


def fetch_posts(
    game_id: str | None = None,
    version: str | None = None,
    platform: str | None = None,
    category: str | None = None,
    warning_level: int | None = None,
    query: str | None = None,
    start_date: str | None = None,
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    params: dict[str, Any] = {"limit": limit, "offset": offset}

    if game_id and game_id != "all":
        clauses.append("game_id = :game_id")
        params["game_id"] = game_id
    if version and version != "all":
        clauses.append("game_version = :version")
        params["version"] = version
    if platform and platform != "all":
        clauses.append("platform = :platform")
        params["platform"] = platform
    if category and category != "all":
        clauses.append("category = :category")
        params["category"] = category
    if warning_level is not None:
        clauses.append("warning_level >= :warning_level")
        params["warning_level"] = warning_level
    if start_date:
        clauses.append("date(publish_time) >= date(:start_date)")
        params["start_date"] = start_date
    if query:
        clauses.append("(title LIKE :query OR content LIKE :query OR author LIKE :query)")
        params["query"] = f"%{query}%"

    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = f"""
        SELECT * FROM posts
        {where_sql}
        ORDER BY publish_time DESC, warning_level DESC
        LIMIT :limit OFFSET :offset
    """
    with connect() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [_row_to_post(row) for row in rows]


def fetch_all_posts(start_date: str | None = None, game_id: str | None = None) -> list[dict[str, Any]]:
    params: dict[str, Any] = {}
    clauses: list[str] = []
    if start_date:
        clauses.append("date(publish_time) >= date(:start_date)")
        params["start_date"] = start_date
    if game_id and game_id != "all":
        clauses.append("game_id = :game_id")
        params["game_id"] = game_id
    where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    with connect() as conn:
        rows = conn.execute(
            f"SELECT * FROM posts {where_sql} ORDER BY publish_time DESC",
            params,
        ).fetchall()
    return [_row_to_post(row) for row in rows]


def init_v2_tables(conn: sqlite3.Connection) -> None:
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS games (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            developer TEXT NOT NULL,
            active INTEGER NOT NULL DEFAULT 0,
            config_json TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agent_states (
            agent_id TEXT PRIMARY KEY,
            agent_type TEXT NOT NULL,
            status TEXT NOT NULL,
            enabled INTEGER NOT NULL DEFAULT 1,
            last_heartbeat TEXT,
            last_run_at TEXT,
            next_run_at TEXT,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            avg_latency_ms REAL NOT NULL DEFAULT 0,
            success_rate REAL NOT NULL DEFAULT 1,
            config_json TEXT NOT NULL,
            last_error TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_agent TEXT NOT NULL,
            target_agent TEXT NOT NULL,
            message_type TEXT NOT NULL,
            payload_json TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            processed_at TEXT
        );

        CREATE TABLE IF NOT EXISTS agent_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            latency_ms REAL NOT NULL DEFAULT 0,
            metrics_json TEXT NOT NULL DEFAULT '{}',
            error TEXT
        );

        CREATE TABLE IF NOT EXISTS collector_offsets (
            platform TEXT PRIMARY KEY,
            last_post_id TEXT,
            last_timestamp INTEGER NOT NULL DEFAULT 0,
            success_count INTEGER NOT NULL DEFAULT 0,
            failure_count INTEGER NOT NULL DEFAULT 0,
            last_success_at TEXT,
            last_error TEXT,
            circuit_open_until TEXT
        );

        CREATE TABLE IF NOT EXISTS analysis_insights (
            post_id TEXT PRIMARY KEY,
            emotion TEXT NOT NULL,
            intent TEXT NOT NULL,
            entities_json TEXT NOT NULL,
            relevance TEXT NOT NULL,
            confidence REAL NOT NULL,
            llm_provider TEXT NOT NULL,
            prompt_version TEXT NOT NULL,
            bilingual_summary TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS issue_clusters (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL DEFAULT 'zzz',
            cluster_key TEXT NOT NULL,
            label TEXT NOT NULL,
            size INTEGER NOT NULL,
            growth_2h INTEGER NOT NULL DEFAULT 0,
            avg_sentiment REAL NOT NULL,
            keywords_json TEXT NOT NULL,
            post_ids_json TEXT NOT NULL,
            severity INTEGER NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            game_id TEXT NOT NULL DEFAULT 'zzz',
            level INTEGER NOT NULL,
            title TEXT NOT NULL,
            reason TEXT NOT NULL,
            platform TEXT,
            category TEXT,
            keyword TEXT,
            cluster_id INTEGER,
            status TEXT NOT NULL DEFAULT 'open',
            push_channel TEXT NOT NULL DEFAULT 'mock',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            resolved_at TEXT
        );

        CREATE TABLE IF NOT EXISTS work_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            alert_id INTEGER,
            title TEXT NOT NULL,
            priority TEXT NOT NULL,
            assignee TEXT NOT NULL,
            external_ref TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'created',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS agent_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            report_type TEXT NOT NULL,
            game_id TEXT NOT NULL DEFAULT 'zzz',
            title TEXT NOT NULL,
            markdown TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS audit_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            actor TEXT NOT NULL,
            role TEXT NOT NULL,
            action TEXT NOT NULL,
            target TEXT NOT NULL,
            detail_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        );

        CREATE TABLE IF NOT EXISTS api_rate_limits (
            api_key TEXT NOT NULL,
            window_start TEXT NOT NULL,
            request_count INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY(api_key, window_start)
        );

        CREATE INDEX IF NOT EXISTS idx_agent_messages_status ON agent_messages(status, target_agent);
        CREATE INDEX IF NOT EXISTS idx_agent_runs_agent ON agent_runs(agent_id, started_at);
        CREATE INDEX IF NOT EXISTS idx_alerts_status ON alerts(status, level);
        CREATE INDEX IF NOT EXISTS idx_clusters_game ON issue_clusters(game_id, updated_at);
        CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_logs(created_at);
        """
    )
    conn.executemany(
        """
        INSERT INTO games(id, name, developer, active, config_json)
        VALUES(:id, :name, :developer, :active, :config_json)
        ON CONFLICT(id) DO UPDATE SET
            name = excluded.name,
            developer = excluded.developer,
            active = excluded.active,
            config_json = excluded.config_json,
            updated_at = CURRENT_TIMESTAMP
        """,
        [
            {
                "id": game_id,
                "name": game["name"],
                "developer": game["developer"],
                "active": 1 if game["active"] else 0,
                "config_json": json.dumps(game, ensure_ascii=False),
            }
            for game_id, game in GAMES.items()
        ],
    )
    game_placeholders = ",".join("?" for _ in GAMES)
    conn.execute(
        f"DELETE FROM games WHERE id NOT IN ({game_placeholders})",
        list(GAMES.keys()),
    )
    conn.executemany(
        """
        INSERT INTO agent_states(agent_id, agent_type, status, enabled, config_json)
        VALUES(:agent_id, :agent_type, 'idle', :enabled, :config_json)
        ON CONFLICT(agent_id) DO UPDATE SET
            enabled = excluded.enabled,
            config_json = excluded.config_json
        """,
        [
            {
                "agent_id": f"{agent_type}_agent",
                "agent_type": agent_type,
                "enabled": 1 if config.get("enabled", True) else 0,
                "config_json": json.dumps(config, ensure_ascii=False),
            }
            for agent_type, config in AGENT_CONFIG.items()
        ],
    )


def ensure_column(conn: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    existing = {row["name"] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
    if column not in existing:
        conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def _row_to_post(row: sqlite3.Row) -> dict[str, Any]:
    item = dict(row)
    item["keywords"] = json.loads(item.get("keywords") or "[]")
    item["is_early_feedback"] = bool(item["is_early_feedback"])
    return item
