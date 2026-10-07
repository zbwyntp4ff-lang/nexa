"""Stop a workflow when a configured limit is reached."""
from __future__ import annotations
from app.workflows.models import Workflow
def limit_reason(workflow: Workflow) -> str | None:
    limits = workflow.limits
    state = workflow.state
    if len(workflow.tasks) > limits.max_tasks:
        return "maximum tasks"
    if state.elapsed_seconds > limits.max_execution_seconds:
        return "maximum execution time"
    if state.tool_calls > limits.max_tool_calls:
        return "maximum tool calls"
    if state.tokens_used > limits.token_budget:
        return "context/token budget"
    if limits.cost_budget is not None and state.cost_used > limits.cost_budget:
        return "cost budget"
    return None
