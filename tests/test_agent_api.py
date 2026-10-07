"""Tests for the POST /api/v1/agent HTTP endpoint (Part 4 addition to Part 2's Agent)."""
from __future__ import annotations
import pytest
from fastapi.testclient import TestClient
from app.agent.agent import Agent
from app.agent.executor import Executor
from app.agent.planner import RuleBasedPlanner
from app.agent.tool_selector import ToolSelector
from app.agent.verifier import Verifier
from app.api.deps import get_agent
from app.main import app
from app.tools.calculator import CalculatorTool
from app.tools.current_time import CurrentTimeTool
from app.tools.directory_list import DirectoryListTool
from app.tools.file_read import FileReadTool
from app.tools.file_write import FileWriteTool
from app.tools.registry import ToolRegistry
def _build_agent(tmp_path) -> Agent:
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(CurrentTimeTool())
    registry.register(FileReadTool(tmp_path))
    registry.register(FileWriteTool(tmp_path))
    registry.register(DirectoryListTool(tmp_path))
    return Agent(
        planner=RuleBasedPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
    )
@pytest.fixture
def client(tmp_path):
    app.dependency_overrides[get_agent] = lambda: _build_agent(tmp_path)
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
def test_agent_endpoint_runs_demo_task(client: TestClient):
    response = client.post(
        "/api/v1/agent", json={"task": "Посчитай 25 * 37 и сохрани результат в файл."}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["success"] is True
    tool_names = [s["tool_name"] for s in body["steps"] if s["tool_name"]]
    assert tool_names == ["calculator", "file_write"]
def test_agent_endpoint_dry_run_has_no_side_effects(client: TestClient, tmp_path):
    response = client.post(
        "/api/v1/agent",
        json={"task": "Посчитай 25 * 37 и сохрани результат в файл.", "dry_run": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["dry_run"] is True
    assert not (tmp_path / "result.txt").exists()
def test_agent_endpoint_rejects_empty_task(client: TestClient):
    response = client.post("/api/v1/agent", json={"task": "   "})
    assert response.status_code == 400
    assert response.json()["error"] == "AgentTaskError"
def test_agent_endpoint_missing_task_field_returns_422(client: TestClient):
    response = client.post("/api/v1/agent", json={})
    assert response.status_code == 422
