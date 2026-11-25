"""Workflow executor must preserve authenticated tenant ownership."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.workflows.executor import WorkflowExecutor
from app.workflows.models import Workflow, WorkflowTask


@pytest.mark.asyncio
async def test_workflow_owner_is_propagated_to_agent_task(monkeypatch):
    captured = {}

    class FakeAgent:
        async def run(self, task, cancel_event=None):
            captured["task"] = task
            return SimpleNamespace(
                success=True,
                final_answer="completed",
                steps=[],
                provider=None,
                model=None,
            )

    def fake_make_agent(*args, **kwargs):
        return FakeAgent()

    monkeypatch.setattr("app.workflows.executor.make_agent", fake_make_agent)

    workflow = Workflow(
        user_id="account-123",
        name="Private workflow",
        description="Test workflow",
        goal="Create a private report",
    )
    task = WorkflowTask(
        name="Create report",
        description="Create a report",
        agent="planning",
    )

    outcome = await WorkflowExecutor(registry=object()).run(workflow, task)

    assert outcome.output == "completed"
    assert captured["task"].metadata == {"user_id": "account-123"}
