from __future__ import annotations

import asyncio
from typing import Any

from app.collectors.api_collectors import BilibiliCollector, MiyousheCollector, RedditCollector
from app.collectors.browser_collectors import BROWSER_COLLECTORS
from app.database import insert_posts
from app.services.analysis import analyse_and_normalize


API_COLLECTORS = [MiyousheCollector(), BilibiliCollector(), RedditCollector()]


async def run_collection(keyword: str = "绝区零", include_browser: bool = False) -> dict[str, Any]:
    collectors = list(API_COLLECTORS)
    if include_browser:
        collectors.extend(BROWSER_COLLECTORS)

    results = await asyncio.gather(
        *(safe_fetch(collector, keyword) for collector in collectors),
        return_exceptions=False,
    )
    raw_posts = [post for batch in results for post in batch["posts"]]
    normalized = [analyse_and_normalize(post) for post in raw_posts]
    inserted = insert_posts(normalized)
    return {
        "keyword": keyword,
        "collector_count": len(collectors),
        "fetched": len(raw_posts),
        "inserted": inserted,
        "collectors": results,
    }


async def safe_fetch(collector: Any, keyword: str) -> dict[str, Any]:
    try:
        posts = await collector.fetch(keyword)
        return {
            "platform": collector.platform,
            "platform_name": collector.platform_name,
            "status": "ok",
            "count": len(posts),
            "posts": posts,
        }
    except Exception as exc:  # pragma: no cover - external platform failures are expected.
        return {
            "platform": collector.platform,
            "platform_name": collector.platform_name,
            "status": "failed",
            "error": str(exc),
            "count": 0,
            "posts": [],
        }
