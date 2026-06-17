from __future__ import annotations

from collections import Counter

from app.agents.base import Agent
from app.agents.bus import consume_messages, mark_message
from app.database import fetch_posts
from app.services.v2.nlp import enrich_post_semantics
from app.services.v2.repository import upsert_analysis_insight


class AnalyzerAgent(Agent):
    agent_type = "analyzer"

    async def execute(self) -> dict[str, object]:
        messages = consume_messages(self.agent_id)
        posts = fetch_posts(limit=300)
        emotion_counter: Counter[str] = Counter()
        intent_counter: Counter[str] = Counter()
        relevance_counter: Counter[str] = Counter()
        processed = 0

        for post in posts:
            insight = enrich_post_semantics(post)
            upsert_analysis_insight(insight)
            emotion_counter.update([insight["emotion"]])
            intent_counter.update([insight["intent"]])
            relevance_counter.update([insight["relevance"]])
            processed += 1

        for message in messages:
            mark_message(int(message["id"]), "done")

        self.publish(
            "alert_agent",
            "analysis.completed",
            {
                "processed": processed,
                "top_emotions": emotion_counter.most_common(5),
                "top_intents": intent_counter.most_common(5),
            },
        )
        return {
            "processed": processed,
            "messages_consumed": len(messages),
            "emotion_distribution": dict(emotion_counter),
            "intent_distribution": dict(intent_counter),
            "relevance_distribution": dict(relevance_counter),
        }
