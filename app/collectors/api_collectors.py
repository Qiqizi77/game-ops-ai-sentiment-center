from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import httpx

from app.collectors.base import Collector
from app.config import PLATFORM_NAMES


DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 Codex-ZZZ-Sentiment-Monitor/1.0",
    "Accept": "application/json,text/plain,*/*",
}


class MiyousheCollector(Collector):
    platform = "miyoushe"
    platform_name = PLATFORM_NAMES[platform]
    endpoint = "https://bbs-api.miyoushe.com/post/wapi/getForumPostList"

    async def fetch(self, keyword: str = "绝区零") -> list[dict[str, Any]]:
        params = {"forum_id": 58, "gids": 8, "page_size": 50, "sort_type": 2}
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=12) as client:
            response = await client.get(self.endpoint, params=params)
            response.raise_for_status()
            payload = response.json()

        posts = payload.get("data", {}).get("list", [])
        result = []
        for item in posts:
            post = item.get("post", item)
            stat = item.get("stat", {})
            subject = post.get("subject") or post.get("title") or "米游社反馈"
            content = post.get("content") or post.get("structured_content") or subject
            created_at = post.get("created_at") or post.get("created_time")
            result.append(
                {
                    "platform": self.platform,
                    "platform_name": self.platform_name,
                    "post_id": str(post.get("post_id") or post.get("id") or subject),
                    "title": subject,
                    "content": content,
                    "author": post.get("user", {}).get("nickname") or post.get("uid") or "米游社玩家",
                    "like_count": stat.get("like_num") or stat.get("upvote_count") or 0,
                    "reply_count": stat.get("reply_num") or stat.get("view_num") or 0,
                    "publish_time": timestamp_to_iso(created_at),
                    "url": f"https://www.miyoushe.com/zzz/article/{post.get('post_id', '')}",
                }
            )
        return result


class BilibiliCollector(Collector):
    platform = "bilibili"
    platform_name = PLATFORM_NAMES[platform]
    search_endpoint = "https://api.bilibili.com/x/web-interface/search/all/v2"
    reply_endpoint = "https://api.bilibili.com/x/v2/reply"

    async def fetch(self, keyword: str = "绝区零") -> list[dict[str, Any]]:
        async with httpx.AsyncClient(headers=DEFAULT_HEADERS, timeout=12) as client:
            search_response = await client.get(self.search_endpoint, params={"keyword": keyword})
            search_response.raise_for_status()
            search_payload = search_response.json()
            videos = self._extract_videos(search_payload)[:5]

            results: list[dict[str, Any]] = []
            for video in videos:
                aid = video.get("aid")
                if not aid:
                    continue
                reply_response = await client.get(
                    self.reply_endpoint,
                    params={"type": 1, "oid": aid, "ps": 50},
                )
                if reply_response.status_code >= 400:
                    continue
                replies = reply_response.json().get("data", {}).get("replies") or []
                for reply in replies:
                    member = reply.get("member", {})
                    content = reply.get("content", {}).get("message") or ""
                    results.append(
                        {
                            "platform": self.platform,
                            "platform_name": self.platform_name,
                            "post_id": str(reply.get("rpid") or f"{aid}-{len(results)}"),
                            "title": video.get("title") or "B站评论",
                            "content": content,
                            "author": member.get("uname") or "B站用户",
                            "like_count": reply.get("like") or 0,
                            "reply_count": reply.get("rcount") or 0,
                            "publish_time": timestamp_to_iso(reply.get("ctime")),
                            "url": f"https://www.bilibili.com/video/av{aid}",
                        }
                    )
        return results

    def _extract_videos(self, payload: dict[str, Any]) -> list[dict[str, Any]]:
        videos: list[dict[str, Any]] = []
        for group in payload.get("data", {}).get("result", []):
            if group.get("result_type") != "video":
                continue
            for item in group.get("data") or []:
                videos.append(item)
        return videos


class RedditCollector(Collector):
    platform = "reddit"
    platform_name = PLATFORM_NAMES[platform]
    endpoint = "https://old.reddit.com/r/ZZZero/hot.json"

    async def fetch(self, keyword: str = "Zenless Zone Zero") -> list[dict[str, Any]]:
        headers = dict(DEFAULT_HEADERS)
        headers["User-Agent"] = "Codex ZZZ sentiment monitor by /u/community-ops"
        async with httpx.AsyncClient(headers=headers, timeout=12, follow_redirects=True) as client:
            response = await client.get(self.endpoint, params={"limit": 50})
            response.raise_for_status()
            payload = response.json()

        children = payload.get("data", {}).get("children", [])
        results = []
        for child in children:
            item = child.get("data", {})
            results.append(
                {
                    "platform": self.platform,
                    "platform_name": self.platform_name,
                    "post_id": item.get("id") or item.get("name"),
                    "title": item.get("title") or "Reddit post",
                    "content": item.get("selftext") or item.get("title") or "",
                    "author": item.get("author") or "reddit user",
                    "like_count": item.get("ups") or item.get("score") or 0,
                    "reply_count": item.get("num_comments") or 0,
                    "publish_time": timestamp_to_iso(item.get("created_utc")),
                    "url": f"https://old.reddit.com{item.get('permalink', '')}",
                }
            )
        return results


def timestamp_to_iso(value: Any) -> str:
    if value is None:
        return datetime.now(timezone.utc).isoformat()
    try:
        timestamp = int(float(value))
        return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return datetime.now(timezone.utc).isoformat()
