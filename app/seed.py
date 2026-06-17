from __future__ import annotations

import random
from datetime import date, datetime, timedelta
from typing import Any
from urllib.parse import quote

from app.config import CATEGORIES, PLATFORM_NAMES, VERSIONS
from app.database import connect, insert_posts, post_count
from app.services.analysis import analyse_and_normalize


SAMPLE_SIZE_PER_VERSION = 40

TEMPLATES = {
    CATEGORIES["CLASS_0_BUG"]: [
        ("版本{version}更新后闪退", "打完活动关卡结算时闪退，重进还会黑屏，希望尽快修复严重BUG。"),
        ("移动端发热和掉帧", "手机玩半小时明显发热，战斗特效多时掉帧卡顿，优化还要继续做。"),
        ("服务器排队进不去", "开服排队太久，还遇到断线和登录异常，首日体验很不稳定。"),
        ("地图加载和贴图异常", "新地图加载偶尔卡住，贴图延迟出现，跑图时有穿模问题。"),
    ],
    CATEGORIES["CLASS_1_SUGGESTION"]: [
        ("建议优化{version}活动节奏", "活动奖励不错，但流程有点重复，希望降低日常肝度，增加一键扫荡。"),
        ("减负诉求很集中", "材料本和日常任务可以再减负，老玩家希望把时间留给剧情和角色养成。"),
        ("UI筛选可以再细一点", "驱动盘筛选建议增加副词条锁定和套装预设，养成效率会高很多。"),
        ("希望补充战斗教学", "新角色机制很有趣，但说明不够直观，建议加训练场演示。"),
    ],
    CATEGORIES["CLASS_2_COMPLAINT"]: [
        ("抽卡体验有点劝退", "限定池连续歪，保底压力太大，玩家吐槽氪金成本越来越高。"),
        ("福利讨论分歧很大", "周年庆福利有人夸大方，也有人觉得不如预期，社区吵得很厉害。"),
        ("深渊难度太跳", "这期敌人血量和控制太夸张，手残党真的坐牢，体验不太好。"),
        ("版本初期问题集中", "刚更新就遇到排队和断线，社区里很多人不满，希望有补偿说明。"),
    ],
    CATEGORIES["CLASS_3_POSITIVE"]: [
        ("{version}剧情演出很惊喜", "角色塑造、音乐和打击感都在线，这次剧情讨论热烈，已经安利朋友回坑。"),
        ("周年庆剧情很有记忆点", "福利之外剧情和演出都很稳，角色关系写得好，整体很满意。"),
        ("新角色手感优秀", "连招流畅，动作反馈爽，音画表现也很漂亮，整体满意。"),
        ("福利比预期好", "活动奖励给得舒服，美术质量稳定，海外玩家也在夸。"),
    ],
    CATEGORIES["CLASS_4_WATER"]: [
        ("晒一下今天的抽卡", "十连出了想要的角色，开心打卡，顺便求配队建议。"),
        ("萌新求助", "刚入坑绝区零，有没有适合新人的养成路线和体力规划？"),
        ("日常闲聊", "今天也在刷材料，大家{version}版本最喜欢哪个角色？"),
        ("剧情党集合", "想聊聊这次剧情里的伏笔，大家觉得后面会怎么展开？"),
    ],
}

NORMAL_WEIGHTS = {
    CATEGORIES["CLASS_0_BUG"]: 0.18,
    CATEGORIES["CLASS_1_SUGGESTION"]: 0.24,
    CATEGORIES["CLASS_2_COMPLAINT"]: 0.22,
    CATEGORIES["CLASS_3_POSITIVE"]: 0.28,
    CATEGORIES["CLASS_4_WATER"]: 0.08,
}

SPECIAL_WEIGHTS = {
    "1.0": {
        CATEGORIES["CLASS_0_BUG"]: 0.36,
        CATEGORIES["CLASS_1_SUGGESTION"]: 0.16,
        CATEGORIES["CLASS_2_COMPLAINT"]: 0.18,
        CATEGORIES["CLASS_3_POSITIVE"]: 0.12,
        CATEGORIES["CLASS_4_WATER"]: 0.18,
    },
    "2.0": {
        CATEGORIES["CLASS_0_BUG"]: 0.10,
        CATEGORIES["CLASS_1_SUGGESTION"]: 0.16,
        CATEGORIES["CLASS_2_COMPLAINT"]: 0.28,
        CATEGORIES["CLASS_3_POSITIVE"]: 0.38,
        CATEGORIES["CLASS_4_WATER"]: 0.08,
    },
    "3.0": {
        CATEGORIES["CLASS_0_BUG"]: 0.18,
        CATEGORIES["CLASS_1_SUGGESTION"]: 0.30,
        CATEGORIES["CLASS_2_COMPLAINT"]: 0.16,
        CATEGORIES["CLASS_3_POSITIVE"]: 0.30,
        CATEGORIES["CLASS_4_WATER"]: 0.06,
    },
}


def seed_if_empty() -> int:
    expected_seed_posts = len(VERSIONS) * SAMPLE_SIZE_PER_VERSION
    seed_count = current_seed_count()
    if post_count() > 0 and seed_count == 0:
        return 0
    if seed_count == expected_seed_posts and seed_versions_are_current():
        return 0
    if seed_count:
        clear_demo_seed_data()

    rng = random.Random(20260616)
    raw_posts: list[dict[str, Any]] = []
    platforms = list(PLATFORM_NAMES.items())

    for version_info in VERSIONS:
        version = version_info["version"]
        release_date = date.fromisoformat(version_info["release_date"])
        end_date = date.fromisoformat(version_info["end_date"])
        categories = category_plan(version, rng)
        for index, category in enumerate(categories):
            platform, platform_name = platforms[index % len(platforms)]
            title_template, content_template = choose_template(version, category, rng, index)
            publish_date = choose_publish_date(version, release_date, end_date, index, rng)
            publish_time = datetime.combine(publish_date, datetime.min.time()).replace(
                hour=8 + index % 15,
                minute=(index * 7) % 60,
            )
            title = title_template.format(version=version, version_name=version_info["name"])
            content = content_template.format(version=version, version_name=version_info["name"])
            raw_posts.append(
                {
                    "platform": platform,
                    "platform_name": platform_name,
                    "game_version": version,
                    "post_id": f"seed-{version}-{index:02d}",
                    "title": title,
                    "content": content,
                    "author": f"{platform_name}玩家{rng.randint(100, 999)}",
                    "like_count": rng.randint(0, 520 if version == "2.0" else 360),
                    "reply_count": rng.randint(10, 160 if version == "2.0" else 90),
                    "publish_time": publish_time.isoformat(timespec="seconds"),
                    "url": real_platform_url(platform, version),
                }
            )

    return insert_posts([analyse_and_normalize(post) for post in raw_posts])


def current_seed_count() -> int:
    with connect() as conn:
        return int(conn.execute("SELECT COUNT(*) FROM posts WHERE post_id LIKE 'seed-%'").fetchone()[0])


def seed_versions_are_current() -> bool:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT game_version, COUNT(*) AS total
            FROM posts
            WHERE post_id LIKE 'seed-%'
            GROUP BY game_version
            """
        ).fetchall()
    expected = {item["version"]: SAMPLE_SIZE_PER_VERSION for item in VERSIONS}
    actual = {row["game_version"]: int(row["total"]) for row in rows}
    return actual == expected


def clear_demo_seed_data() -> None:
    with connect() as conn:
        conn.execute(
            """
            DELETE FROM analysis_insights
            WHERE post_id IN (SELECT id FROM posts WHERE post_id LIKE 'seed-%')
            """
        )
        conn.execute("DELETE FROM posts WHERE post_id LIKE 'seed-%'")
        for table in ["issue_clusters", "alerts", "work_orders", "agent_reports", "agent_messages"]:
            conn.execute(f"DELETE FROM {table}")


def category_plan(version: str, rng: random.Random) -> list[str]:
    if version == "1.0":
        early_negative = [CATEGORIES["CLASS_0_BUG"]] * 8 + [CATEGORIES["CLASS_2_COMPLAINT"]] * 4
        first_week_recovery = [
            CATEGORIES["CLASS_1_SUGGESTION"],
            CATEGORIES["CLASS_3_POSITIVE"],
            CATEGORIES["CLASS_3_POSITIVE"],
            CATEGORIES["CLASS_4_WATER"],
        ] * 3
        tail_mix = [
            CATEGORIES["CLASS_0_BUG"],
            CATEGORIES["CLASS_1_SUGGESTION"],
            CATEGORIES["CLASS_2_COMPLAINT"],
            CATEGORIES["CLASS_3_POSITIVE"],
            CATEGORIES["CLASS_4_WATER"],
        ]
        tail_mix += [weighted_choice(rng, SPECIAL_WEIGHTS["1.0"]) for _ in range(SAMPLE_SIZE_PER_VERSION - len(early_negative) - len(first_week_recovery) - len(tail_mix))]
        rng.shuffle(tail_mix)
        return early_negative + first_week_recovery + tail_mix
    weights = SPECIAL_WEIGHTS.get(version, NORMAL_WEIGHTS)
    base = list(TEMPLATES.keys())
    remaining = SAMPLE_SIZE_PER_VERSION - len(base)
    weighted = [weighted_choice(rng, weights) for _ in range(remaining)]
    categories = base + weighted
    rng.shuffle(categories)
    return categories


def choose_template(version: str, category: str, rng: random.Random, index: int) -> tuple[str, str]:
    if category == CATEGORIES["CLASS_4_WATER"]:
        return TEMPLATES[category][1]
    if version == "1.0" and category == CATEGORIES["CLASS_0_BUG"]:
        return rng.choice(TEMPLATES[category][:3])
    if version == "1.0" and category == CATEGORIES["CLASS_4_WATER"]:
        return TEMPLATES[category][1]
    if version == "2.0" and category in {CATEGORIES["CLASS_2_COMPLAINT"], CATEGORIES["CLASS_3_POSITIVE"]}:
        return rng.choice([TEMPLATES[category][1], TEMPLATES[category][3 % len(TEMPLATES[category])]])
    if version == "3.0" and category in {CATEGORIES["CLASS_1_SUGGESTION"], CATEGORIES["CLASS_3_POSITIVE"]}:
        return rng.choice([TEMPLATES[category][0], TEMPLATES[category][1]])
    return TEMPLATES[category][index % len(TEMPLATES[category])]


def choose_publish_date(
    version: str,
    release_date: date,
    end_date: date,
    index: int,
    rng: random.Random,
) -> date:
    today = date.today()
    if version == "3.0":
        preheat_start = release_date - timedelta(days=7)
        latest = min(today, release_date - timedelta(days=1))
        span = max((latest - preheat_start).days, 0)
        return preheat_start + timedelta(days=index % (span + 1))
    if version == "2.0":
        if index < 24:
            return release_date
        return release_date + timedelta(days=rng.randint(3, min((end_date - release_date).days, 24)))
    if version == "1.0":
        if index < 12:
            return release_date
        if index < 24:
            return release_date + timedelta(days=rng.randint(1, 7))
        return release_date + timedelta(days=rng.randint(8, (end_date - release_date).days))
    return release_date + timedelta(days=rng.randint(0, (end_date - release_date).days))


def weighted_choice(rng: random.Random, weights: dict[str, float]) -> str:
    threshold = rng.random() * sum(weights.values())
    current = 0.0
    for category, weight in weights.items():
        current += weight
        if current >= threshold:
            return category
    return next(reversed(weights))


def real_platform_url(platform: str, version: str) -> str:
    keyword = f"绝区零 {version}"
    encoded_keyword = quote(keyword)
    urls = {
        "miyoushe": "https://www.miyoushe.com/zzz/",
        "bilibili": f"https://search.bilibili.com/all?keyword={encoded_keyword}",
        "reddit": "https://old.reddit.com/r/ZZZero/",
        "taptap": "https://www.taptap.cn/app/230121/review",
        "nga": "https://bbs.nga.cn/thread.php?fid=-895135",
        "hoyolab": "https://www.hoyolab.com/circles/8/39/official",
        "twitter": f"https://x.com/search?q={encoded_keyword}",
    }
    return urls.get(platform, "https://zenless.hoyoverse.com/")
