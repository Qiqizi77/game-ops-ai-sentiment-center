from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query

from app.agents.orchestrator import agent_dashboard, run_agent, run_all_agents
from app.config import AGENT_CONFIG, API_GATEWAY, FEATURE_FLAGS, GAMES, NLP_CONFIG
from app.database import fetch_all_posts
from app.services.v2.audit import list_audit_logs
from app.services.v2.gateway import gateway_context
from app.services.v2.nlp import (
    detect_anomalies,
    discover_new_terms,
    predict_version_reputation,
    tfidf_keywords,
)
from app.services.v2.repository import (
    list_agent_reports,
    list_alerts,
    list_analysis_insights,
    list_clusters,
    list_collector_offsets,
    list_work_orders,
)


router = APIRouter(prefix="/api/v2", tags=["V2 AI Agent Center"])
Gateway = Annotated[dict[str, str], Depends(gateway_context)]


@router.get("/meta")
async def v2_meta(_: Gateway) -> dict[str, object]:
    return {
        "name": "游戏发行运营 AI Agent 舆情中台 V2.0",
        "feature_flags": FEATURE_FLAGS,
        "agent_config": AGENT_CONFIG,
        "nlp_config": NLP_CONFIG,
        "api_gateway": {
            "enabled": API_GATEWAY["enabled"],
            "auth_enabled": FEATURE_FLAGS["api_gateway_auth"],
            "rate_limit_per_minute": API_GATEWAY["rate_limit_per_minute"],
            "roles": API_GATEWAY["roles"],
        },
        "games": GAMES,
    }


@router.get("/agents")
async def agents(_: Gateway) -> dict[str, object]:
    return agent_dashboard()


@router.post("/agents/run")
async def agents_run(
    _: Gateway,
    live_collection: bool = False,
) -> dict[str, object]:
    return await run_all_agents(live_collection=live_collection)


@router.post("/agents/{agent_type}/run")
async def single_agent_run(
    agent_type: str,
    _: Gateway,
    live_collection: bool = False,
) -> dict[str, object]:
    try:
        return await run_agent(agent_type, live_collection=live_collection)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/collector/offsets")
async def collector_offsets(_: Gateway) -> list[dict[str, object]]:
    return list_collector_offsets()


@router.get("/analysis/insights")
async def analysis_insights(
    _: Gateway,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, object]]:
    return list_analysis_insights(limit=limit)


@router.get("/nlp/keywords")
async def nlp_keywords(
    _: Gateway,
    game_id: str = "zzz",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> dict[str, object]:
    posts = fetch_all_posts(game_id=game_id)
    return {
        "keywords": tfidf_keywords(posts, top_k=limit),
        "new_terms": discover_new_terms(posts),
    }


@router.get("/nlp/clusters")
async def nlp_clusters(
    _: Gateway,
    game_id: str = "zzz",
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
) -> list[dict[str, object]]:
    return list_clusters(game_id=game_id, limit=limit)


@router.get("/nlp/anomalies")
async def nlp_anomalies(
    _: Gateway,
    game_id: str = "zzz",
) -> dict[str, object]:
    posts = fetch_all_posts(game_id=game_id)
    return {"anomalies": detect_anomalies(posts)}


@router.get("/prediction/version/{version}")
async def prediction(version: str, _: Gateway, game_id: str = "zzz") -> dict[str, object]:
    posts = fetch_all_posts(game_id=game_id)
    return predict_version_reputation(posts, version)


@router.get("/alerts")
async def alerts(
    _: Gateway,
    game_id: str = "zzz",
    status: str | None = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[dict[str, object]]:
    return list_alerts(game_id=game_id, status=status, limit=limit)


@router.get("/work-orders")
async def work_orders(_: Gateway) -> list[dict[str, object]]:
    return list_work_orders()


@router.get("/reports")
async def reports(
    _: Gateway,
    game_id: str = "zzz",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> list[dict[str, object]]:
    return list_agent_reports(game_id=game_id, limit=limit)


@router.get("/games")
async def games(_: Gateway) -> dict[str, object]:
    return GAMES


@router.get("/varsapura")
async def varsapura(_: Gateway) -> dict[str, object]:
    game = GAMES["varsapura"]
    return {
        "game": game,
        "special_dimensions": game["domain_dimensions"],
        "global_launch": {
            "languages": ["简中", "繁中", "英", "日", "韩"],
            "regions": game["regions"],
            "culture_analysis": [
                "中国区偏重性能、抽卡、活动福利",
                "北美/欧洲偏重开放世界自由度、联机稳定性、本地化表达",
                "日本/韩国偏重角色塑造、移动端表现、长线养成节奏",
            ],
        },
        "ai_workflows": [
            "严重BUG自动创建JIRA/飞书任务",
            "基于FAQ库生成标准回复草稿",
            "AI建议官方回应措辞",
            "回应后玩家情绪变化追踪",
        ],
    }


@router.get("/monitoring")
async def monitoring(_: Gateway) -> dict[str, object]:
    dashboard = agent_dashboard()
    offsets = list_collector_offsets()
    alerts_open = list_alerts(status="open")
    posts = fetch_all_posts()
    duplicate_rate = estimate_duplicate_rate(posts)
    empty_rate = estimate_empty_rate(posts)
    return {
        "agents": dashboard["agents"],
        "collector_offsets": offsets,
        "open_alerts": len(alerts_open),
        "data_quality": {
            "post_count": len(posts),
            "duplicate_rate": duplicate_rate,
            "empty_content_rate": empty_rate,
        },
        "system_health": "degraded" if alerts_open else "healthy",
    }


@router.get("/audit")
async def audit(
    _: Gateway,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[dict[str, object]]:
    return list_audit_logs(limit=limit)


def estimate_duplicate_rate(posts: list[dict[str, object]]) -> float:
    if not posts:
        return 0.0
    signatures = [f"{post.get('title')}|{post.get('content')}" for post in posts]
    duplicates = len(signatures) - len(set(signatures))
    return round(duplicates / len(posts) * 100, 2)


def estimate_empty_rate(posts: list[dict[str, object]]) -> float:
    if not posts:
        return 0.0
    empty = sum(1 for post in posts if not str(post.get("content") or "").strip())
    return round(empty / len(posts) * 100, 2)
