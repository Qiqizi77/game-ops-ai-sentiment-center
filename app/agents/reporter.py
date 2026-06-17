from __future__ import annotations

from datetime import date

from app.agents.base import Agent
from app.agents.bus import consume_messages, mark_message
from app.database import fetch_all_posts
from app.services.metrics import daily_report
from app.services.v2.nlp import predict_version_reputation, tfidf_keywords
from app.services.v2.repository import list_alerts, list_clusters, save_agent_report


class ReporterAgent(Agent):
    agent_type = "reporter"

    async def execute(self) -> dict[str, object]:
        messages = consume_messages(self.agent_id)
        base_report = daily_report()
        posts = fetch_all_posts(game_id="zzz")
        clusters = list_clusters("zzz", limit=5)
        alerts = list_alerts("zzz", status="open", limit=5)
        keywords = tfidf_keywords(posts, top_k=8)
        prediction = predict_version_reputation(posts, "3.0")
        markdown = render_v2_report(base_report["markdown"], clusters, alerts, keywords, prediction)
        report_id = save_agent_report(
            "daily_v2",
            "zzz",
            f"游戏发行运营 AI Agent 舆情中台日报 {date.today().isoformat()}",
            markdown,
        )
        for message in messages:
            mark_message(int(message["id"]), "done")
        return {
            "messages_consumed": len(messages),
            "report_id": report_id,
            "clusters": len(clusters),
            "alerts": len(alerts),
            "prediction": prediction,
        }


def render_v2_report(
    base_markdown: str,
    clusters: list[dict[str, object]],
    alerts: list[dict[str, object]],
    keywords: list[dict[str, object]],
    prediction: dict[str, object],
) -> str:
    cluster_lines = "\n".join(
        f"- {item['label']}：{item['size']}条，近2小时新增{item['growth_2h']}条，平均情绪{item['avg_sentiment']}"
        for item in clusters
    ) or "- 暂无稳定聚类"
    alert_lines = "\n".join(
        f"- Level {item['level']}｜{item['title']}：{item['reason']}"
        for item in alerts
    ) or "- 暂无开放告警"
    keyword_lines = "、".join(str(item["keyword"]) for item in keywords) or "暂无"
    return f"""{base_markdown}

## V2 Agent 中台洞察

### 语义聚类
{cluster_lines}

### 实时风险防控
{alert_lines}

### TF-IDF 热词
{keyword_lines}

### 版本口碑预测
- 版本：{prediction['version']}
- 预测最终好评率：{prediction['predicted_positive_rate']}% ±{prediction['margin']}%
- 风险等级：{prediction['risk']}，置信度：{prediction['confidence']}

### 双语运营摘要
- 中文：请优先处理 Level 2 聚类问题，并跟踪官方回应后的情绪回落情况。
- EN: Prioritize Level 2 clustered issues and monitor sentiment recovery after official responses.
"""
