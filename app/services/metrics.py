from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from statistics import mean
from typing import Any

from app.config import CATEGORIES, DEFAULT_COMPARE_VERSIONS
from app.database import fetch_all_posts, fetch_posts, list_versions
from app.services.versioning import (
    VERSION_BY_ID,
    day_index_since_release,
    days_since_release,
    get_version_days_remaining,
    get_version_duration_days,
    get_version_phase,
)


def range_start(range_name: str | None) -> str | None:
    today = date.today()
    mapping = {
        "day": today,
        "today": today,
        "week": today - timedelta(days=7),
        "7d": today - timedelta(days=7),
        "month": today - timedelta(days=30),
        "30d": today - timedelta(days=30),
    }
    start = mapping.get(range_name or "")
    return start.isoformat() if start else None


def overview(
    version: str | None = None,
    platform: str | None = None,
    category: str | None = None,
    range_name: str | None = None,
) -> dict[str, Any]:
    posts = fetch_posts(
        version=version,
        platform=platform,
        category=category,
        start_date=range_start(range_name),
        limit=5000,
    )
    return {
        "total_comments": len(posts),
        "avg_sentiment": round(avg(post["sentiment_score"] for post in posts), 1),
        "negative_count": sum(1 for post in posts if post["sentiment_score"] <= 3.9),
        "neutral_count": sum(1 for post in posts if 4 <= post["sentiment_score"] <= 6.9),
        "positive_count": sum(1 for post in posts if post["sentiment_score"] >= 7),
        "warning_count": sum(1 for post in posts if post["warning_level"] >= 1),
        "high_warning_count": sum(1 for post in posts if post["warning_level"] >= 2),
        "platform_distribution": distribution(posts, "platform_name"),
        "category_distribution": distribution(posts, "category"),
        "sentiment_trend": date_sentiment_trend(posts),
        "version_distribution": distribution(posts, "game_version"),
    }


def version_metrics(version: str, range_name: str | None = None) -> dict[str, Any]:
    posts = fetch_posts(version=version, start_date=range_start(range_name), limit=5000)
    version_info = VERSION_BY_ID.get(version) or {"name": version, "release_date": date.today().isoformat()}
    category_dist = distribution(posts, "category", percent=True)
    positive = sum(1 for post in posts if post["sentiment_score"] >= 7)
    bug_count = sum(1 for post in posts if post["category"] == CATEGORIES["CLASS_0_BUG"])
    complaint_count = sum(1 for post in posts if post["category"] == CATEGORIES["CLASS_2_COMPLAINT"])
    day1_sentiment = sentiment_on_day(posts, version, 1)
    day7_sentiment = sentiment_on_day(posts, version, 7)
    lifecycle_points = lifecycle_trend(posts, version)
    return {
        "version": version,
        "name": version_info["name"],
        "release_date": version_info["release_date"],
        "end_date": version_info["end_date"],
        "duration_days": get_version_duration_days(version),
        "remaining_days": get_version_days_remaining(version),
        "phase": get_version_phase(version),
        "days_since_release": days_since_release(version),
        "total_comments": len(posts),
        "avg_sentiment": round(avg(post["sentiment_score"] for post in posts), 1),
        "positive_rate": round(positive / len(posts) * 100, 1) if posts else 0,
        "bug_rate": round(bug_count / len(posts) * 100, 1) if posts else 0,
        "complaint_rate": round(complaint_count / len(posts) * 100, 1) if posts else 0,
        "peak_comments": peak_daily_comments(posts),
        "sentiment_day1": day1_sentiment,
        "sentiment_day7": day7_sentiment,
        "trend_label": sentiment_trend_label(day1_sentiment, day7_sentiment, lifecycle_points),
        "sentiment_trend": lifecycle_points,
        "calendar_trend": date_sentiment_trend(posts),
        "category_distribution": category_dist,
        "top_issues": top_issues(posts),
        "hot_topics": hot_topics(posts),
        "platform_comparison": platform_comparison(posts),
        "early_feedback_count": sum(1 for post in posts if post["is_early_feedback"]),
    }


def version_comparison(versions: list[str] | None = None, range_name: str | None = None) -> dict[str, Any]:
    selected = versions or DEFAULT_COMPARE_VERSIONS
    metrics_rows = [version_metrics(version, range_name) for version in selected]
    rows = []
    for item in metrics_rows:
        row = dict(item)
        row["lifecycle_sentiment_trend"] = item["sentiment_trend"]
        row["sentiment_trend"] = item["trend_label"]
        rows.append(row)
    return {
        "versions": rows,
        "lifecycle_curves": [
            {
                "version": item["version"],
                "name": item["name"],
                "points": item["lifecycle_sentiment_trend"],
            }
            for item in rows
        ],
    }


def daily_report(report_date: str | None = None) -> dict[str, Any]:
    target = date.fromisoformat(report_date) if report_date else date.today()
    posts = fetch_all_posts(start_date=target.isoformat())
    posts = [post for post in posts if datetime.fromisoformat(post["publish_time"]).date() == target]
    all_posts = fetch_all_posts()
    latest_version = list_versions()[0]
    current_version_metrics = version_metrics(latest_version["version"])
    overview_data = {
        "total_comments": len(posts),
        "avg_sentiment": round(avg(post["sentiment_score"] for post in posts), 1),
        "platform_distribution": distribution(posts, "platform_name", percent=True),
        "positive_rate": percentage(sum(1 for post in posts if post["sentiment_score"] >= 7), len(posts)),
        "neutral_rate": percentage(sum(1 for post in posts if 4 <= post["sentiment_score"] <= 6.9), len(posts)),
        "negative_rate": percentage(sum(1 for post in posts if post["sentiment_score"] < 4), len(posts)),
    }
    hot = hot_topics(posts or all_posts)[:3]
    warnings = [
        post for post in sorted(posts or all_posts, key=lambda item: (-item["warning_level"], item["sentiment_score"])) if post["warning_level"] > 0
    ][:5]
    markdown = render_daily_markdown(target, overview_data, current_version_metrics, hot, warnings)
    return {
        "date": target.isoformat(),
        "overview": overview_data,
        "current_version": current_version_metrics,
        "hot_topics": hot,
        "warnings": warnings,
        "markdown": markdown,
    }


def render_daily_markdown(
    target: date,
    overview_data: dict[str, Any],
    current_version: dict[str, Any],
    hot: list[str],
    warnings: list[dict[str, Any]],
) -> str:
    warning_lines = "\n".join(
        f"- [{item['platform_name']}] {item['title']}，情绪 {item['sentiment_score']}，预警 Level {item['warning_level']}"
        for item in warnings
    ) or "- 今日暂无高危预警"
    hot_lines = "\n".join(f"{index}. {topic}" for index, topic in enumerate(hot, 1)) or "1. 暂无明显集中热点"
    issues = current_version["top_issues"][:3]
    issue_lines = "\n".join(f"- {issue}" for issue in issues) or "- 暂无集中问题"

    return f"""# 绝区零社区舆情日报 {target.isoformat()}

## 今日概览
- 新增评论：{overview_data['total_comments']}条
- 平均情绪分：{overview_data['avg_sentiment']}
- 情绪分布：正面{overview_data['positive_rate']}% / 中性{overview_data['neutral_rate']}% / 负面{overview_data['negative_rate']}%

## 版本舆情跟踪
### 当前版本：{current_version['version']}（发布第{current_version['days_since_release']}天）
- 版本累计评论：{current_version['total_comments']}条
- 版本平均情绪：{current_version['avg_sentiment']}
- 版本初期反馈：{current_version['early_feedback_count']}条

### 版本核心诉求
{issue_lines}

## 今日热点 TOP 3
{hot_lines}

## 负面预警列表
{warning_lines}

## 海外玩家动态
- Reddit/HoYoLAB/Twitter 样本已纳入统一口径，重点关注翻译、角色强度和版本福利反馈。

## 运营建议
- 对 Level 2 问题优先建立工单，并在版本发布后7天内提高社区回应频次。
"""


def lifecycle_trend(posts: list[dict[str, Any]], version: str) -> list[dict[str, Any]]:
    buckets: dict[int, list[float]] = defaultdict(list)
    for post in posts:
        day = min(day_index_since_release(version, post["publish_time"]), 30)
        buckets[day].append(float(post["sentiment_score"]))
    return [
        {"day": day, "score": round(avg(scores), 1)}
        for day, scores in sorted(buckets.items())
        if day <= 30
    ]


def peak_daily_comments(posts: list[dict[str, Any]]) -> int:
    buckets: dict[str, int] = defaultdict(int)
    for post in posts:
        day = datetime.fromisoformat(post["publish_time"]).date().isoformat()
        buckets[day] += 1
    return max(buckets.values(), default=0)


def sentiment_on_day(posts: list[dict[str, Any]], version: str, target_day: int) -> float:
    scores = [
        float(post["sentiment_score"])
        for post in posts
        if day_index_since_release(version, post["publish_time"]) == target_day
    ]
    return round(avg(scores), 1)


def sentiment_trend_label(day1: float, day7: float, lifecycle_points: list[dict[str, Any]]) -> str:
    if day1 == 0 or day7 == 0:
        if len(lifecycle_points) < 2:
            return "平稳"
        day1 = float(lifecycle_points[0]["score"])
        day7 = float(lifecycle_points[-1]["score"])
    delta = day7 - day1
    if delta >= 0.4:
        return "上升"
    if delta <= -0.4:
        return "下降"
    return "平稳"


def date_sentiment_trend(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        day = datetime.fromisoformat(post["publish_time"]).date().isoformat()
        buckets[day].append(float(post["sentiment_score"]))
    return [{"date": day, "score": round(avg(scores), 1)} for day, scores in sorted(buckets.items())]


def platform_comparison(posts: list[dict[str, Any]]) -> dict[str, float]:
    buckets: dict[str, list[float]] = defaultdict(list)
    for post in posts:
        buckets[post["platform_name"]].append(float(post["sentiment_score"]))
    return {platform: round(avg(scores), 1) for platform, scores in sorted(buckets.items())}


def distribution(posts: list[dict[str, Any]], field: str, percent: bool = False) -> dict[str, Any]:
    counts = Counter(post[field] for post in posts)
    if not percent:
        return dict(counts)
    total = sum(counts.values())
    return {key: percentage(value, total) for key, value in counts.items()}


def top_issues(posts: list[dict[str, Any]]) -> list[str]:
    candidates = [
        post for post in posts if post["category"] in {CATEGORIES["CLASS_0_BUG"], CATEGORIES["CLASS_2_COMPLAINT"]}
    ]
    candidates.sort(key=lambda post: (-post["warning_level"], post["sentiment_score"], -post["reply_count"]))
    return [post["title"] for post in candidates[:3]]


def hot_topics(posts: list[dict[str, Any]]) -> list[str]:
    counter: Counter[str] = Counter()
    for post in posts:
        weight = 1 + int(post["reply_count"] > 20) + int(post["like_count"] > 100)
        for keyword in post["keywords"]:
            counter[keyword] += weight
    return [keyword for keyword, _ in counter.most_common(5)]


def avg(values: Any) -> float:
    values = list(values)
    return mean(values) if values else 0.0


def percentage(value: int, total: int) -> float:
    return round(value / total * 100, 1) if total else 0.0
