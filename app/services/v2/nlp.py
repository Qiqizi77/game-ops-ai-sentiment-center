from __future__ import annotations

import math
import re
import hashlib
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from statistics import mean, pstdev
from typing import Any

from app.config import CATEGORIES, MASKING_RULES, NLP_CONFIG


EMOTIONS = ["愤怒", "失望", "无奈", "中立", "满意", "惊喜", "期待"]
INTENTS = ["报告BUG", "寻求帮助", "提出建议", "表达不满", "分享喜悦", "灌水闲聊"]

STOPWORDS = {
    "一个",
    "一下",
    "这个",
    "那个",
    "已经",
    "真的",
    "感觉",
    "还是",
    "没有",
    "就是",
    "可以",
    "不是",
    "因为",
    "所以",
    "但是",
    "然后",
    "玩家",
    "版本",
    "绝区零",
    "游戏",
    "我们",
    "你们",
    "他们",
    "自己",
}

ENTITY_PATTERNS = {
    "角色名": ["耀嘉音", "简", "伊芙琳", "月城柳", "安东", "莱卡恩", "妮可", "安比", "比利"],
    "关卡名": ["深渊", "零号空洞", "活动关卡", "支线任务", "训练场", "新地图"],
    "系统名": ["抽卡", "驱动盘", "UI", "匹配"],
    "BUG类型": ["闪退", "卡顿", "掉帧", "黑屏", "断线", "穿模", "加载", "贴图", "空气墙", "发热"],
}

def enrich_post_semantics(post: dict[str, Any]) -> dict[str, Any]:
    text = f"{post.get('title', '')} {post.get('content', '')}"
    emotion = detect_emotion(text, float(post.get("sentiment_score") or 5))
    intent = detect_intent(text, str(post.get("category") or ""))
    entities = extract_entities(text)
    relevance = detect_relevance(text)
    confidence = estimate_confidence(text, emotion, intent, entities)
    return {
        "post_id": post["id"],
        "emotion": emotion,
        "intent": intent,
        "entities": entities,
        "relevance": relevance,
        "confidence": confidence,
        "llm_provider": "rules-first-compatible",
        "prompt_version": "v2-agent-semantic-2026-06",
        "bilingual_summary": bilingual_summary(post, emotion, intent, entities),
    }


def detect_emotion(text: str, sentiment_score: float) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ["炸", "恶心", "骂", "骗氪", "退坑", "大规模"]):
        return "愤怒"
    if any(word in lowered for word in ["失望", "劝退", "不满", "差评"]):
        return "失望"
    if any(word in lowered for word in ["坐牢", "无奈", "没办法", "难受"]):
        return "无奈"
    if any(word in lowered for word in ["期待", "希望", "等一个", "快出"]):
        return "期待"
    if any(word in lowered for word in ["惊喜", "神", "太爽", "超出预期"]):
        return "惊喜"
    if sentiment_score >= 7:
        return "满意"
    if sentiment_score <= 3:
        return "失望"
    return "中立"


def detect_intent(text: str, category: str) -> str:
    if category == CATEGORIES["CLASS_0_BUG"] or any(term in text for term in ["闪退", "BUG", "异常", "黑屏"]):
        return "报告BUG"
    if any(term in text for term in ["求助", "有没有", "怎么", "如何", "萌新"]):
        return "寻求帮助"
    if category == CATEGORIES["CLASS_1_SUGGESTION"] or any(term in text for term in ["建议", "希望", "优化"]):
        return "提出建议"
    if category == CATEGORIES["CLASS_2_COMPLAINT"] or any(term in text for term in ["不满", "退坑", "骗氪"]):
        return "表达不满"
    if category == CATEGORIES["CLASS_3_POSITIVE"] or any(term in text for term in ["安利", "喜欢", "好玩"]):
        return "分享喜悦"
    return "灌水闲聊"


def extract_entities(text: str) -> dict[str, list[str]]:
    entities: dict[str, list[str]] = {}
    for label, terms in ENTITY_PATTERNS.items():
        hits = [term for term in terms if term.lower() in text.lower()]
        if hits:
            entities[label] = hits
    return entities


def detect_relevance(text: str) -> str:
    if any(term in text for term in ["闪退", "黑屏", "崩溃", "穿模", "掉帧", "断线", "异常", "空气墙"]):
        return "真BUG"
    if any(term in text for term in ["不会", "怎么", "求助", "操作", "教程"]):
        return "玩家操作问题"
    if any(term in text for term in ["网络", "延迟", "掉线", "WiFi", "服务器", "排队"]):
        return "网络问题"
    return "舆情反馈"


def estimate_confidence(text: str, emotion: str, intent: str, entities: dict[str, list[str]]) -> float:
    signal = 0.55
    signal += 0.08 if emotion != "中立" else 0
    signal += 0.1 if intent != "灌水闲聊" else 0
    signal += 0.1 if entities else 0
    signal += min(len(tokenize(text)) / 80, 0.15)
    return round(min(signal, 0.96), 2)


def bilingual_summary(post: dict[str, Any], emotion: str, intent: str, entities: dict[str, list[str]]) -> str:
    title = post.get("title") or "玩家反馈"
    entity_text = "、".join(term for terms in entities.values() for term in terms[:3]) or "未识别核心实体"
    return f"中文：{title}；情绪={emotion}，意图={intent}，实体={entity_text}。\nEN: {title}; emotion={emotion}, intent={intent}, entities={entity_text}."


def tokenize(text: str) -> list[str]:
    normalized = re.sub(r"[^\w\u4e00-\u9fa5]+", " ", text.lower())
    candidates = re.findall(r"[a-zA-Z][a-zA-Z0-9_]{1,}|[\u4e00-\u9fa5]{2,6}", normalized)
    return [token for token in candidates if token not in STOPWORDS and len(token) >= NLP_CONFIG["keywords"]["min_token_len"]]


def tfidf_keywords(posts: list[dict[str, Any]], top_k: int | None = None) -> list[dict[str, Any]]:
    top_k = top_k or NLP_CONFIG["keywords"]["top_k"]
    docs = [tokenize(f"{post.get('title', '')} {post.get('content', '')}") for post in posts]
    doc_count = max(len(docs), 1)
    df: Counter[str] = Counter()
    for doc in docs:
        df.update(set(doc))
    scores: Counter[str] = Counter()
    for doc in docs:
        tf = Counter(doc)
        for token, count in tf.items():
            idf = math.log((doc_count + 1) / (df[token] + 1)) + 1
            scores[token] += count * idf
    return [
        {"keyword": token, "score": round(score, 3), "document_frequency": df[token]}
        for token, score in scores.most_common(top_k)
    ]


def discover_new_terms(posts: list[dict[str, Any]], known_terms: set[str] | None = None) -> list[dict[str, Any]]:
    known_terms = known_terms or set()
    candidates = tfidf_keywords(posts, top_k=80)
    return [
        item
        for item in candidates
        if item["keyword"] not in known_terms and item["document_frequency"] >= 2
    ][:12]


def vectorize_documents(posts: list[dict[str, Any]]) -> tuple[list[list[float]], list[str]]:
    docs = [tokenize(f"{post.get('title', '')} {post.get('content', '')}") for post in posts]
    vocabulary = sorted({token for doc in docs for token in doc})
    if not vocabulary:
        return [[] for _ in posts], []
    index = {token: idx for idx, token in enumerate(vocabulary)}
    df = Counter(token for doc in docs for token in set(doc))
    vectors = []
    doc_count = len(docs)
    for doc in docs:
        tf = Counter(doc)
        vector = [0.0] * len(vocabulary)
        for token, count in tf.items():
            idf = math.log((doc_count + 1) / (df[token] + 1)) + 1
            vector[index[token]] = count * idf
        vectors.append(normalize(vector))
    return vectors, vocabulary


def normalize(vector: list[float]) -> list[float]:
    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 0.0
    return sum(a * b for a, b in zip(left, right))


def cluster_posts(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    max_posts = NLP_CONFIG["cluster"]["max_posts"]
    posts = posts[:max_posts]
    min_similarity = float(NLP_CONFIG["cluster"]["min_similarity"])
    min_samples = int(NLP_CONFIG["cluster"]["min_samples"])
    vectors, _ = vectorize_documents(posts)
    visited: set[int] = set()
    clusters: list[list[int]] = []

    for idx in range(len(posts)):
        if idx in visited:
            continue
        neighbours = [other for other in range(len(posts)) if cosine(vectors[idx], vectors[other]) >= min_similarity]
        if len(neighbours) < min_samples:
            visited.add(idx)
            continue
        cluster = set(neighbours)
        queue = list(neighbours)
        while queue:
            current = queue.pop()
            if current in visited:
                continue
            visited.add(current)
            current_neighbours = [
                other for other in range(len(posts)) if cosine(vectors[current], vectors[other]) >= min_similarity
            ]
            if len(current_neighbours) >= min_samples:
                for other in current_neighbours:
                    if other not in cluster:
                        cluster.add(other)
                        queue.append(other)
        clusters.append(sorted(cluster))

    results = []
    now = datetime.utcnow()
    for indices in clusters:
        items = [posts[index] for index in indices]
        keywords = tfidf_keywords(items, top_k=5)
        label = keywords[0]["keyword"] if keywords else items[0].get("title", "舆情聚类")
        growth_2h = sum(
            1
            for item in items
            if safe_datetime(item.get("publish_time")) >= now - timedelta(hours=2)
        )
        avg_sentiment = mean(float(item.get("sentiment_score") or 0) for item in items)
        severity = 2 if len(items) >= 5 and avg_sentiment <= 4 else 1 if len(items) >= 2 and avg_sentiment <= 5 else 0
        results.append(
            {
                "cluster_key": stable_cluster_key(items),
                "label": label,
                "size": len(items),
                "growth_2h": growth_2h,
                "avg_sentiment": round(avg_sentiment, 1),
                "keywords": [item["keyword"] for item in keywords],
                "post_ids": [item["id"] for item in items],
                "severity": severity,
            }
        )
    results.sort(key=lambda item: (-item["severity"], -item["size"], item["avg_sentiment"]))
    return results


def detect_anomalies(posts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str], Counter[str]] = defaultdict(Counter)
    for post in posts:
        dt = safe_datetime(post.get("publish_time"))
        hour_key = dt.strftime("%Y-%m-%d %H:00")
        buckets[(post.get("platform_name", "unknown"), post.get("category", "unknown"), hour_key)].update(["count"])

    series: dict[tuple[str, str], list[tuple[str, int]]] = defaultdict(list)
    for (platform, category, hour_key), counter in buckets.items():
        series[(platform, category)].append((hour_key, counter["count"]))

    anomalies = []
    multiplier = float(NLP_CONFIG.get("surge_multiplier", 3.0))
    for (platform, category), points in series.items():
        points.sort()
        counts = [count for _, count in points]
        if len(counts) < 3:
            continue
        baseline = mean(counts[:-1]) if len(counts) > 1 else counts[0]
        sigma = pstdev(counts[:-1]) if len(counts) > 2 else 0
        latest_hour, latest_count = points[-1]
        threshold = baseline + 3 * sigma
        if latest_count >= max(threshold, baseline * multiplier, 2):
            anomalies.append(
                {
                    "platform": platform,
                    "category": category,
                    "hour": latest_hour,
                    "count": latest_count,
                    "baseline": round(baseline, 2),
                    "sigma": round(sigma, 2),
                    "reason": f"{platform}/{category} 1小时内突增，当前 {latest_count}，基线 {round(baseline, 2)}",
                }
            )
    return anomalies


def predict_version_reputation(posts: list[dict[str, Any]], version: str) -> dict[str, Any]:
    release_posts = [post for post in posts if post.get("game_version") == version]
    if not release_posts:
        return {"version": version, "predicted_positive_rate": 0, "risk": "无数据", "confidence": 0}
    release_posts.sort(key=lambda item: item.get("publish_time", ""))
    early = release_posts[: max(3, min(len(release_posts), 12))]
    positive_rate = sum(1 for post in early if float(post.get("sentiment_score") or 0) >= 7) / len(early) * 100
    warning_rate = sum(1 for post in early if int(post.get("warning_level") or 0) >= 1) / len(early) * 100
    adjustment = -min(warning_rate * 0.18, 18)
    prediction = round(max(0, min(100, positive_rate + adjustment)), 1)
    risk = "高风险" if prediction < 35 or warning_rate > 45 else "中风险" if prediction < 55 else "低风险"
    return {
        "version": version,
        "predicted_positive_rate": prediction,
        "margin": NLP_CONFIG["prediction"]["positive_rate_margin"],
        "risk": risk,
        "early_sample_size": len(early),
        "warning_rate": round(warning_rate, 1),
        "confidence": round(min(0.5 + len(early) / 30, 0.9), 2),
    }


def mask_sensitive_text(text: str) -> str:
    masked = text
    for pattern in MASKING_RULES.values():
        masked = re.sub(pattern, "***", masked)
    return masked


def safe_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return datetime.utcnow()


def stable_cluster_key(items: list[dict[str, Any]]) -> str:
    ids = sorted(str(item.get("id")) for item in items)
    return hashlib.sha1("|".join(ids).encode("utf-8")).hexdigest()[:16]
