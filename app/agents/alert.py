from __future__ import annotations

from app.agents.base import Agent
from app.agents.bus import consume_messages, mark_message
from app.config import AGENT_CONFIG
from app.database import fetch_all_posts
from app.services.v2.nlp import cluster_posts, detect_anomalies
from app.services.v2.repository import create_alert, create_work_order, upsert_cluster


class AlertAgent(Agent):
    agent_type = "alert"

    async def execute(self) -> dict[str, object]:
        messages = consume_messages(self.agent_id)
        posts = fetch_all_posts(game_id="zzz")
        clusters = cluster_posts(posts)
        anomalies = detect_anomalies(posts)
        alert_ids = []
        work_orders = []

        for cluster in clusters:
            cluster_id = upsert_cluster("zzz", cluster)
            if cluster["severity"] <= 0:
                continue
            level = 2 if cluster["severity"] >= 2 else 1
            alert_id = create_alert(
                {
                    "game_id": "zzz",
                    "level": level,
                    "title": f"{cluster['label']}问题聚类增长",
                    "reason": f"相似反馈 {cluster['size']} 条，近2小时新增 {cluster['growth_2h']} 条，平均情绪 {cluster['avg_sentiment']}",
                    "keyword": cluster["label"],
                    "cluster_id": cluster_id,
                    "push_channel": "电话/短信+工单" if level == 2 else "运营群@提醒",
                }
            )
            alert_ids.append(alert_id)
            if level == 2 and AGENT_CONFIG["alert"]["auto_work_order"]:
                work_orders.append(create_work_order(alert_id, f"紧急处理：{cluster['label']}问题聚类"))

        for anomaly in anomalies:
            alert_id = create_alert(
                {
                    "game_id": "zzz",
                    "level": 2,
                    "title": f"{anomaly['platform']} {anomaly['category']}异常突增",
                    "reason": anomaly["reason"],
                    "platform": anomaly["platform"],
                    "category": anomaly["category"],
                    "push_channel": "电话/短信+工单",
                }
            )
            alert_ids.append(alert_id)
            work_orders.append(create_work_order(alert_id, f"异常突增排查：{anomaly['platform']} {anomaly['category']}"))

        for message in messages:
            mark_message(int(message["id"]), "done")

        self.publish(
            "reporter_agent",
            "alerts.updated",
            {"alerts": len(alert_ids), "work_orders": len(work_orders), "clusters": len(clusters)},
        )
        return {
            "messages_consumed": len(messages),
            "clusters": len(clusters),
            "anomalies": len(anomalies),
            "alerts": len(set(alert_ids)),
            "work_orders": len(set(work_orders)),
        }
