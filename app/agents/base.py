from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import Any

from app.agents.bus import publish_message, record_agent_run, update_agent_state, utc_now


class Agent(ABC):
    agent_type: str

    def __init__(self, agent_id: str, config: dict[str, Any]) -> None:
        self.agent_id = agent_id
        self.config = config

    async def run(self) -> dict[str, Any]:
        started = utc_now()
        start = time.perf_counter()
        update_agent_state(self.agent_id, "running")
        try:
            metrics = await self.execute()
            latency = round((time.perf_counter() - start) * 1000, 2)
            update_agent_state(
                self.agent_id,
                "idle",
                success=True,
                latency_ms=latency,
                schedule_minutes=self.config.get("schedule_minutes"),
            )
            record_agent_run(self.agent_id, "success", started, latency, metrics)
            return {"agent_id": self.agent_id, "status": "success", "latency_ms": latency, "metrics": metrics}
        except Exception as exc:
            latency = round((time.perf_counter() - start) * 1000, 2)
            update_agent_state(
                self.agent_id,
                "degraded",
                success=False,
                latency_ms=latency,
                error=str(exc),
                schedule_minutes=self.config.get("schedule_minutes"),
            )
            record_agent_run(self.agent_id, "failed", started, latency, {}, str(exc))
            raise

    def publish(self, target_agent: str, message_type: str, payload: dict[str, Any]) -> int:
        return publish_message(self.agent_id, target_agent, message_type, payload)

    @abstractmethod
    async def execute(self) -> dict[str, Any]:
        """Run one agent tick."""
