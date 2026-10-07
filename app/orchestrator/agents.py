"""Specialized agents for the Multi-Agent Orchestrator (Part 7).
Each agent wraps the existing ``Agent`` class with a pre-configured
``ToolSelector`` that only grants the permissions that agent needs
(minimum-context principle). Agents use the *same* real tools and
AI provider — no mock substitution.
"""
from __future__ import annotations
from app.agent.agent import Agent
from app.agent.executor import Executor
from app.agent.planner import RuleBasedPlanner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.tools.registry import ToolRegistry
# Permission sets per agent type (least-privilege).
PERMISSIONS = {
    "research": frozenset({"network:read"}),
    "coding": frozenset({"filesystem:read", "filesystem:write", "compute"}),
    "planning": frozenset(),  # planning needs no tools, just decomposes
    "desktop": frozenset({"filesystem:read", "filesystem:write"}),
    "review": frozenset({"filesystem:read"}),
}
def make_agent(agent_type: str, registry: ToolRegistry, model_gateway=None, **agent_kwargs) -> Agent:
    """Create a specialized agent with only the permissions it needs.
    ``model_gateway`` is optional. When present, free-form answers go through
    the Model Gateway. The agent still does not know which provider that is.
    """
    return Agent(
        planner=RuleBasedPlanner(),
        tool_selector=ToolSelector(registry, allowed_permissions=PERMISSIONS.get(agent_type, frozenset())),
        executor=Executor(registry),
        verifier=Verifier(registry),
        model_gateway=model_gateway,
        **agent_kwargs,
    )
