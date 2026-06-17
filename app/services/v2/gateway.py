from __future__ import annotations

from datetime import datetime

from fastapi import Header, HTTPException, Request

from app.config import API_GATEWAY, FEATURE_FLAGS
from app.database import connect
from app.services.v2.audit import record_audit


def current_minute() -> str:
    return datetime.utcnow().strftime("%Y-%m-%dT%H:%M")


async def gateway_context(
    request: Request,
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    x_user_role: str | None = Header(default="admin", alias="X-User-Role"),
    x_user: str | None = Header(default="local-demo", alias="X-User"),
) -> dict[str, str]:
    role = x_user_role or "admin"
    actor = x_user or "local-demo"
    if FEATURE_FLAGS.get("api_gateway_auth") and x_api_key != API_GATEWAY["default_api_key"]:
        raise HTTPException(status_code=401, detail="Invalid API key")
    if x_api_key:
        enforce_rate_limit(x_api_key)
    record_audit(
        actor=actor,
        role=role,
        action=f"{request.method} {request.url.path}",
        target=request.url.path,
        detail={"query": dict(request.query_params)},
    )
    return {"actor": actor, "role": role}


def enforce_rate_limit(api_key: str) -> None:
    window = current_minute()
    limit = int(API_GATEWAY["rate_limit_per_minute"])
    with connect() as conn:
        row = conn.execute(
            "SELECT request_count FROM api_rate_limits WHERE api_key = ? AND window_start = ?",
            (api_key, window),
        ).fetchone()
        count = int(row["request_count"]) + 1 if row else 1
        if count > limit:
            raise HTTPException(status_code=429, detail="API rate limit exceeded")
        conn.execute(
            """
            INSERT INTO api_rate_limits(api_key, window_start, request_count)
            VALUES(?, ?, ?)
            ON CONFLICT(api_key, window_start) DO UPDATE SET request_count = excluded.request_count
            """,
            (api_key, window, count),
        )
