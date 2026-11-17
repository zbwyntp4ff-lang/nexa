"""Read-only catalogue for NEXA specialist agent roles."""
from __future__ import annotations

from fastapi import APIRouter, Query

from app.orchestrator.catalog import list_agents

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("/catalog")
async def get_agent_catalog(
    category: str | None = Query(default=None, max_length=40),
    q: str = Query(default="", max_length=100),
) -> dict:
    """Return the curated role catalogue; this does not start agent jobs."""
    agents = list_agents()
    if category:
        agents = [agent for agent in agents if agent["category"] == category]
    needle = q.strip().casefold()
    if needle:
        agents = [
            agent for agent in agents
            if needle in str(agent["name"]).casefold()
            or needle in str(agent["description"]).casefold()
            or needle in str(agent["category_name"]).casefold()
        ]
    return {
        "agents": agents,
        "count": len(agents),
        "total": 100,
        "categories": sorted({
            (str(agent["category"]), str(agent["category_name"]))
            for agent in list_agents()
        }),
    }
