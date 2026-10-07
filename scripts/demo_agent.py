#!/usr/bin/env python3
"""NEXA Agent demo (Part 2).
Runs the required Part 2 demo task end-to-end:
    "Посчитай 25 * 37 и сохрани результат в файл."
The agent should: select Calculator -> get the result -> select FileWrite ->
write the result -> verify the file -> return the final answer.
Usage:
    python scripts/demo_agent.py            # real run
    python scripts/demo_agent.py --dry-run  # simulate without side effects
"""
from __future__ import annotations
import argparse
import asyncio
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.agent.agent import Agent  # noqa: E402
from app.agent.executor import Executor  # noqa: E402
from app.agent.models import AgentTask  # noqa: E402
from app.agent.planner import RuleBasedPlanner  # noqa: E402
from app.agent.tool_selector import ToolSelector  # noqa: E402
from app.agent.verifier import Verifier  # noqa: E402
from app.config.settings import get_settings  # noqa: E402
from app.tools.registry import build_default_registry  # noqa: E402
DEMO_TASK = "Посчитай 25 * 37 и сохрани результат в файл."
async def main(dry_run: bool) -> int:
    settings = get_settings()
    registry = build_default_registry()
    agent = Agent(
        planner=RuleBasedPlanner(),
        tool_selector=ToolSelector(registry),
        executor=Executor(registry),
        verifier=Verifier(registry),
        max_steps=settings.agent_max_steps,
        timeout_seconds=settings.agent_timeout_seconds,
        error_limit=settings.agent_error_limit,
    )
    task = AgentTask(description=DEMO_TASK, dry_run=dry_run)
    print(f"Task: {task.description}")
    print(f"Dry run: {dry_run}\n")
    result = await agent.run(task)
    for step in result.steps:
        marker = "OK " if step.success else "ERR"
        dry_marker = " (dry-run)" if step.dry_run else ""
        print(f"[{marker}] step {step.index} {step.step_type.value}{dry_marker}: "
              f"tool={step.tool_name} input={step.tool_input} -> {step.output or step.error}")
    print("\n--- Result ---")
    print(json.dumps(result.model_dump(mode="json"), indent=2, ensure_ascii=False))
    return 0 if result.success else 1
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Simulate the plan without side effects.")
    args = parser.parse_args()
    raise SystemExit(asyncio.run(main(args.dry_run)))
