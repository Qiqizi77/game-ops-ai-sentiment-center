from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from app.config import CATEGORIES, PLATFORM_NAMES
from app.services.versioning import detect_game_version, is_early_feedback


AI_PROMPT_TEMPLATE = """
你是游戏发行运营舆情分析专家。请基于玩家反馈内容，输出 JSON：
category: BUG反馈/优化建议/玩家吐槽/正面评价/水贴
sentiment_score: 0-10
keywords: 3-5个关键词
warning_level: 0/1/2
判断标准：BUG=闪退卡顿功能异常；建议=玩法数值UI改进；吐槽=抽卡肝度难度氪金不满；正面=好评安利喜爱；水贴=闲聊晒卡求助。
"""

BUG_KEYWORDS = ["闪退", "卡顿", "掉帧", "黑屏", "报错", "崩溃", "bug", "BUG", "异常", "进不去", "断线", "穿模", "排队", "发热", "贴图", "加载"]
SUGGESTION_KEYWORDS = ["建议", "希望", "优化", "能不能", "应该", "改进", "调整", "增加", "降低", "提高"]
COMPLAINT_KEYWORDS = ["太肝", "抽卡", "保底", "氪金", "骗氪", "恶心", "难度", "坐牢", "不满", "退坑", "失望", "吵", "骂"]
POSITIVE_KEYWORDS = ["好玩", "喜欢", "安利", "爽", "优秀", "惊喜", "舒服", "神", "满意", "可爱", "漂亮", "推荐"]
WATER_KEYWORDS = ["晒卡", "求助", "有没有", "日常", "闲聊", "打卡", "萌新", "水", "表情包"]

NEGATIVE_KEYWORDS = BUG_KEYWORDS + COMPLAINT_KEYWORDS + ["差评", "严重", "爆炸", "修复", "补偿"]
POSITIVE_SCORE_KEYWORDS = POSITIVE_KEYWORDS + ["流畅", "福利", "剧情", "音乐", "美术", "打击感"]
DOMAIN_KEYWORDS = [
    "抽卡",
    "保底",
    "闪退",
    "卡顿",
    "掉帧",
    "剧情",
    "角色",
    "活动",
    "福利",
    "难度",
    "肝度",
    "UI",
    "数值",
    "优化",
    "音画",
    "打击感",
    "海外",
    "翻译",
    "版本初期",
]


def analyse_and_normalize(raw: dict[str, Any]) -> dict[str, Any]:
    title = clean_text(str(raw.get("title") or ""))
    content = clean_text(str(raw.get("content") or ""))
    merged_text = f"{title}\n{content}"
    publish_time = normalize_publish_time(raw.get("publish_time"))
    game_version = raw.get("game_version") or detect_game_version(merged_text, publish_time)
    category = classify(merged_text)
    sentiment_score = score_sentiment(merged_text, category)
    keywords = extract_keywords(merged_text)
    warning_level = detect_warning_level(merged_text, category, sentiment_score, int(raw.get("reply_count") or 0))
    platform = str(raw.get("platform") or "unknown")
    post_id = str(raw.get("post_id") or raw.get("id") or stable_id(merged_text))

    return {
        "id": f"{platform}:{post_id}",
        "platform": platform,
        "platform_name": raw.get("platform_name") or PLATFORM_NAMES.get(platform, platform),
        "game_version": game_version,
        "post_id": post_id,
        "title": title or content[:30] or "无标题反馈",
        "content": content or title,
        "author": str(raw.get("author") or "匿名玩家"),
        "like_count": int(raw.get("like_count") or 0),
        "reply_count": int(raw.get("reply_count") or 0),
        "publish_time": publish_time,
        "timestamp": int(datetime.fromisoformat(publish_time).timestamp()),
        "url": str(raw.get("url") or ""),
        "category": category,
        "sentiment_score": sentiment_score,
        "keywords": keywords,
        "warning_level": warning_level,
        "is_early_feedback": 1 if is_early_feedback(game_version, publish_time) else 0,
    }


def clean_text(value: str) -> str:
    value = re.sub(r"<[^>]+>", " ", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def normalize_publish_time(value: Any) -> str:
    if isinstance(value, datetime):
        dt = value
    elif value:
        text = str(value)
        try:
            dt = datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            dt = datetime.now(timezone.utc)
    else:
        dt = datetime.now(timezone.utc)

    if dt.tzinfo:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.isoformat(timespec="seconds")


def classify(text: str) -> str:
    scores = {
        CATEGORIES["CLASS_0_BUG"]: keyword_hits(text, BUG_KEYWORDS) * 3,
        CATEGORIES["CLASS_1_SUGGESTION"]: keyword_hits(text, SUGGESTION_KEYWORDS) * 2,
        CATEGORIES["CLASS_2_COMPLAINT"]: keyword_hits(text, COMPLAINT_KEYWORDS) * 2,
        CATEGORIES["CLASS_3_POSITIVE"]: keyword_hits(text, POSITIVE_KEYWORDS) * 2,
        CATEGORIES["CLASS_4_WATER"]: keyword_hits(text, WATER_KEYWORDS),
    }
    best_category, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return CATEGORIES["CLASS_4_WATER"] if len(text) < 30 else CATEGORIES["CLASS_1_SUGGESTION"]
    return best_category


def score_sentiment(text: str, category: str) -> float:
    positive = keyword_hits(text, POSITIVE_SCORE_KEYWORDS)
    negative = keyword_hits(text, NEGATIVE_KEYWORDS)
    base = 5.2 + positive * 0.75 - negative * 0.85
    if category == CATEGORIES["CLASS_0_BUG"]:
        base -= 1.2
    elif category == CATEGORIES["CLASS_2_COMPLAINT"]:
        base -= 1.5
    elif category == CATEGORIES["CLASS_3_POSITIVE"]:
        base += 1.7
    elif category == CATEGORIES["CLASS_1_SUGGESTION"]:
        base += 0.2
    return round(max(0.0, min(10.0, base)), 1)


def extract_keywords(text: str) -> list[str]:
    hits = [keyword for keyword in DOMAIN_KEYWORDS if keyword.lower() in text.lower()]
    if len(hits) >= 5:
        return hits[:5]

    chinese_terms = re.findall(r"[\u4e00-\u9fa5]{2,6}", text)
    for term in chinese_terms:
        if term not in hits and len(term) >= 2:
            hits.append(term)
        if len(hits) >= 5:
            break
    return hits[:5] or ["玩家反馈"]


def detect_warning_level(text: str, category: str, sentiment_score: float, reply_count: int) -> int:
    severe_terms = ["大规模", "炸了", "进不去", "崩溃", "严重BUG", "退坑", "差评", "补偿"]
    if keyword_hits(text, severe_terms) > 0 and (sentiment_score <= 3.5 or reply_count >= 30):
        return 2
    if category in {CATEGORIES["CLASS_0_BUG"], CATEGORIES["CLASS_2_COMPLAINT"]} or sentiment_score < 4:
        return 1
    return 0


def keyword_hits(text: str, keywords: list[str]) -> int:
    lower_text = text.lower()
    return sum(1 for keyword in keywords if keyword.lower() in lower_text)


def stable_id(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]
