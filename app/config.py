from __future__ import annotations

from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = DATA_DIR / "sentiment.db"

APP_NAME = "游戏发行运营 AI Agent 舆情中台 V2.0"
V1_APP_NAME = "绝区零 游戏社区舆情AI监控系统 V1.0"

VERSIONS = [
    {"version": "3.0", "name": "某个梦游者的自白", "release_date": "2026-06-17", "end_date": "2026-07-28"},
    {"version": "2.8", "name": "新·艾利都日落时", "release_date": "2026-05-06", "end_date": "2026-06-16"},
    {"version": "2.7", "name": "英雄不死于往昔", "release_date": "2026-03-24", "end_date": "2026-05-05"},
    {"version": "2.6", "name": "旧梦的安可曲", "release_date": "2026-02-06", "end_date": "2026-03-23"},
    {"version": "2.5", "name": "微光引灯时", "release_date": "2025-12-30", "end_date": "2026-02-06"},
    {"version": "2.4", "name": "将临未抵的深渊", "release_date": "2025-11-26", "end_date": "2025-12-29"},
    {"version": "2.3", "name": "可曾记得梦", "release_date": "2025-10-15", "end_date": "2025-11-25"},
    {"version": "2.2", "name": "不要温和地走入那良夜", "release_date": "2025-09-04", "end_date": "2025-10-14"},
    {"version": "2.1", "name": "迟吟的浪涌", "release_date": "2025-07-16", "end_date": "2025-09-03"},
    {"version": "2.0", "name": "云霞同归处", "release_date": "2025-06-06", "end_date": "2025-07-15"},
    {"version": "1.7", "name": "将眼泪与过往一同埋葬", "release_date": "2025-04-23", "end_date": "2025-06-05"},
    {"version": "1.6", "name": "在被遗忘的废墟之上", "release_date": "2025-03-12", "end_date": "2025-04-22"},
    {"version": "1.5", "name": "闪耀的此刻", "release_date": "2025-01-22", "end_date": "2025-03-11"},
    {"version": "1.4", "name": "星流霆击", "release_date": "2024-12-18", "end_date": "2025-01-21"},
    {"version": "1.3", "name": "虚拟杀机", "release_date": "2024-11-06", "end_date": "2024-12-17"},
    {"version": "1.2", "name": "火狱骑行", "release_date": "2024-09-25", "end_date": "2024-11-05"},
    {"version": "1.1", "name": "卧底蓝调", "release_date": "2024-08-14", "end_date": "2024-09-24"},
    {"version": "1.0", "name": "欢迎来到新艾利都", "release_date": "2024-07-04", "end_date": "2024-08-13"},
]

PLATFORM_NAMES = {
    "miyoushe": "米游社",
    "bilibili": "B站",
    "reddit": "Reddit",
    "taptap": "TapTap",
    "nga": "NGA",
    "hoyolab": "HoYoLAB",
    "twitter": "Twitter/X",
}

CATEGORIES = {
    "CLASS_0_BUG": "BUG反馈",
    "CLASS_1_SUGGESTION": "优化建议",
    "CLASS_2_COMPLAINT": "玩家吐槽",
    "CLASS_3_POSITIVE": "正面评价",
    "CLASS_4_WATER": "水贴",
}

DEFAULT_COMPARE_VERSIONS = ["3.0", "2.8", "2.1"]

FEATURE_FLAGS = {
    "v2_agents": True,
    "llm_prompts": True,
    "semantic_clustering": True,
    "anomaly_detection": True,
    "api_gateway_auth": False,
    "enterprise_audit": True,
    "external_push_mock": True,
}

AGENT_CONFIG = {
    "collector": {
        "enabled": True,
        "schedule_minutes": 15,
        "batch_size": 50,
        "max_retries": 3,
        "backoff_base_seconds": 2,
        "circuit_breaker_failures": 5,
        "api_to_browser_fallback": True,
        "quality_min_content_length": 8,
    },
    "analyzer": {
        "enabled": True,
        "schedule_minutes": 10,
        "llm_provider": "rules-first",
        "llm_templates": ["gpt-4o-mini", "claude-3-haiku"],
        "confidence_threshold": 0.68,
    },
    "alert": {
        "enabled": True,
        "schedule_minutes": 5,
        "surge_multiplier": 3.0,
        "sigma_threshold": 3.0,
        "level2_cluster_size": 5,
        "level1_cluster_size": 2,
        "auto_work_order": True,
    },
    "reporter": {
        "enabled": True,
        "schedule_minutes": 60,
        "bilingual": True,
        "version_review_day": 7,
    },
}

NLP_CONFIG = {
    "cluster": {
        "min_similarity": 0.32,
        "min_samples": 2,
        "max_posts": 600,
    },
    "keywords": {
        "top_k": 30,
        "min_token_len": 2,
    },
    "prediction": {
        "early_days": 3,
        "positive_rate_margin": 5,
    },
}

GAMES = {
    "zzz": {
        "id": "zzz",
        "name": "绝区零",
        "developer": "miHoYo",
        "active": True,
        "default_locale": "zh-CN",
        "regions": ["中国", "北美", "欧洲", "日本", "韩国", "东南亚"],
        "versions": VERSIONS,
        "platforms": PLATFORM_NAMES,
        "domain_dimensions": ["抽卡", "角色", "剧情", "战斗", "活动", "性能", "社区情绪"],
    },
    "varsapura": {
        "id": "varsapura",
        "name": "Varsapura",
        "developer": "Varsapura Studio",
        "active": False,
        "default_locale": "zh-CN",
        "regions": ["中国", "新加坡", "北美", "欧洲", "日本", "韩国"],
        "versions": [
            {"version": "0.3", "name": "雨之城技术测试", "release_date": "2026-05-20"},
            {"version": "0.2", "name": "开放世界联机测试", "release_date": "2026-03-15"},
            {"version": "0.1", "name": "UE5首测", "release_date": "2026-01-08"},
        ],
        "platforms": PLATFORM_NAMES,
        "domain_dimensions": [
            "世界探索",
            "加载贴图",
            "穿模掉落",
            "空气墙",
            "移动端帧率",
            "发热内存",
            "联机匹配",
            "AI NPC",
            "昼夜天气",
            "本地化",
        ],
    },
}

API_GATEWAY = {
    "enabled": True,
    "default_api_key": "demo-v2-local-key",
    "rate_limit_per_minute": 120,
    "roles": {
        "admin": ["read", "write", "export", "manage"],
        "operator": ["read", "write", "export"],
        "analyst": ["read", "export"],
        "readonly": ["read"],
    },
}

MASKING_RULES = {
    "phone": r"(?<!\d)1[3-9]\d{9}(?!\d)",
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "qq": r"QQ[:：]?\s*\d{5,12}",
}
