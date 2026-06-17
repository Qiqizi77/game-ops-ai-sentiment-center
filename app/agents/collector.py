from __future__ import annotations

from collections import defaultdict
from typing import Any

from app.agents.base import Agent
from app.database import fetch_all_posts
from app.services.v2.repository import update_collector_offset
from app.tasks import run_collection


class CollectorAgent(Agent):
    agent_type = "collector"

    async def execute(self) -> dict[str, Any]:
        live_collection = bool(self.config.get("live_collection", False))
        inserted = 0
        fetched = 0
        collectors: list[dict[str, Any]] = []
        if live_collection:
            result = await run_collection(keyword=self.config.get("keyword", "绝区零"), include_browser=False)
            inserted = int(result.get("inserted") or 0)
            fetched = int(result.get("fetched") or 0)
            collectors = result.get("collectors", [])

        posts = fetch_all_posts()
        latest_by_platform: dict[str, dict[str, Any]] = {}
        quality: dict[str, list[int]] = defaultdict(list)
        for post in posts:
            platform = post["platform"]
            quality[platform].append(1 if len(post.get("content") or "") >= self.config["quality_min_content_length"] else 0)
            if platform not in latest_by_platform or post["timestamp"] > latest_by_platform[platform]["timestamp"]:
                latest_by_platform[platform] = post
        for platform, post in latest_by_platform.items():
            update_collector_offset(platform, post["post_id"], int(post["timestamp"]), True)

        platform_quality = {
            platform: round(sum(values) / len(values), 3)
            for platform, values in quality.items()
            if values
        }
        self.publish(
            "analyzer_agent",
            "collection.completed",
            {"inserted": inserted, "fetched": fetched, "platform_quality": platform_quality},
        )
        return {
            "mode": "live" if live_collection else "incremental-state-sync",
            "fetched": fetched,
            "inserted": inserted,
            "collector_results": collectors,
            "platform_count": len(latest_by_platform),
            "platform_quality": platform_quality,
        }
