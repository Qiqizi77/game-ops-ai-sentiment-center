from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.collectors.base import Collector
from app.config import PLATFORM_NAMES


class PlaywrightReviewCollector(Collector):
    def __init__(self, platform: str, url: str, item_selector: str = "body") -> None:
        self.platform = platform
        self.platform_name = PLATFORM_NAMES[platform]
        self.url = url
        self.item_selector = item_selector

    async def fetch(self, keyword: str = "绝区零") -> list[dict[str, Any]]:
        try:
            from playwright.async_api import async_playwright
        except ImportError:
            return []

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            page = await browser.new_page(user_agent="Codex ZZZ sentiment monitor")
            await page.goto(self.url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(1500)
            texts = await page.locator(self.item_selector).all_inner_texts()
            await browser.close()

        results = []
        for index, text in enumerate(texts[:30]):
            cleaned = " ".join(text.split())
            if len(cleaned) < 12:
                continue
            results.append(
                {
                    "platform": self.platform,
                    "platform_name": self.platform_name,
                    "post_id": f"browser-{index}-{abs(hash(cleaned))}",
                    "title": f"{self.platform_name}玩家反馈",
                    "content": cleaned[:1000],
                    "author": f"{self.platform_name}用户",
                    "like_count": 0,
                    "reply_count": 0,
                    "publish_time": datetime.now(timezone.utc).isoformat(),
                    "url": self.url,
                }
            )
        return results


BROWSER_COLLECTORS = [
    PlaywrightReviewCollector("taptap", "https://www.taptap.cn/app/230121/review", "[class*=review], article, li"),
    PlaywrightReviewCollector("nga", "https://bbs.nga.cn/thread.php?fid=-895135", "tr, .topic, .postrow"),
    PlaywrightReviewCollector("hoyolab", "https://www.hoyolab.com/accountCenter/postList?id=9", "article, [class*=post]"),
]
