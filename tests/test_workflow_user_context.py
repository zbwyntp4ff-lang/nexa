from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.workflows.executor as workflow_executor
from app.workflows.executor import WorkflowExecutor
from app.workflows.models import Workflow, WorkflowTask


@pytest.mark.asyncio
async def test_workflow_agent_receives_authenticated_owner_metadata(monkeypatch):
    captured = {}

    class FakeAgent:
        async def run(self, task, *, cancel_event=None):
            captured["task"] = task
            return SimpleNamespace(steps=[], final_answer="completed", success=True)

    def fake_make_agent(*args, **kwargs):
        return FakeAgent()

    monkeypatch.setattr(workflow_executor, "make_agent", fake_make_agent)
    workflow = Workflow(
        user_id="authenticated-user-123",
        name="Private workspace task",
        description="Write a file in the user's workspace",
        goal="Create a private file",
    )
    task = WorkflowTask(
        name="Create file",
        description="Create a file",
        agent="coding",
    )

    outcome = await WorkflowExecutor(registry=object())._run_agent(workflow, task, None)

    assert outcome.output == "completed"
    assert captured["task"].metadata["user_id"] == "authenticated-user-123"
    assert captured["task"].metadata["workflow_id"] == workflow.id


@pytest.mark.asyncio
async def test_workflow_agent_does_not_invent_owner_for_anonymous_workflow(monkeypatch):
    captured = {}

    class FakeAgent:
        async def run(self, task, *, cancel_event=None):
            captured["task"] = task
            return SimpleNamespace(steps=[], final_answer="completed", success=True)

    monkeypatch.setattr(workflow_executor, "make_agent", lambda *args, **kwargs: FakeAgent())
    workflow = Workflow(
        user_id=None,
        name="Local workflow",
        description="Local task",
        goal="Run locally",
    )
    task = WorkflowTask(name="Plan", description="Plan", agent="planning")

    await WorkflowExecutor(registry=object())._run_agent(workflow, task, None)

    assert captured["task"].metadata["user_id"] is None
