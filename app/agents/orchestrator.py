from __future__ import annotations

from app.agents.alert import AlertAgent
from app.agents.analyzer import AnalyzerAgent
from app.agents.bus import list_agent_states, recent_messages
from app.agents.collector import CollectorAgent
from app.agents.reporter import ReporterAgent
from app.config import AGENT_CONFIG


def build_agents(live_collection: bool = False):
    collector_config = dict(AGENT_CONFIG["collector"])
    collector_config["live_collection"] = live_collection
    return [
        CollectorAgent("collector_agent", collector_config),
        AnalyzerAgent("analyzer_agent", AGENT_CONFIG["analyzer"]),
        AlertAgent("alert_agent", AGENT_CONFIG["alert"]),
        ReporterAgent("reporter_agent", AGENT_CONFIG["reporter"]),
    ]


async def run_agent(agent_type: str, live_collection: bool = False) -> dict[str, object]:
    agents = {agent.agent_type: agent for agent in build_agents(live_collection=live_collection)}
    if agent_type not in agents:
        raise ValueError(f"Unknown agent type: {agent_type}")
    return await agents[agent_type].run()


async def run_all_agents(live_collection: bool = False) -> dict[str, object]:
    results = []
    for agent in build_agents(live_collection=live_collection):
        results.append(await agent.run())
    return {"results": results}


def agent_dashboard() -> dict[str, object]:
    return {
        "agents": list_agent_states(),
        "recent_messages": recent_messages(limit=20),
    }
