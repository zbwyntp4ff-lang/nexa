"""Turn a user goal into a bounded task graph.
The planner never calls a model in a loop and never appends tasks while a
workflow is running. The graph is fixed at creation time.
"""
from __future__ import annotations
from app.workflows.graph import validate_graph
from app.workflows.models import (
    DANGEROUS_AGENTS,
    RiskLevel,
    WorkflowLimits,
    WorkflowTask,
)
_RESEARCH = (
    "research", "investigate", "look up", "report", "sources",
    "исслед", "отчёт", "отчет", "источник", "найди",
)
_DESKTOP = ("file", "folder", "directory", "создай файл", "создай папку", "переименуй")
_CODING = ("code", "implement", "function", "напиши код", "реализуй", "исправь код")
def _matches(text: str, words: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)
class WorkflowPlanner:
    """Rule-based planner. One pass, hard task cap, cycle check."""
    def plan(self, goal: str, limits: WorkflowLimits) -> list[WorkflowTask]:
        goal = goal.strip()
        tasks: list[WorkflowTask] = []
        if _matches(goal, _RESEARCH):
            tasks.extend(self._research_report(goal))
        else:
            tasks.append(
                WorkflowTask(
                    name="Plan",
                    description=f"Break the request into steps: {goal}",
                    agent="planning",
                    input=goal,
                    checkpoint_name="Planning complete",
                )
            )
        if _matches(goal, _CODING):
            tasks.append(
                WorkflowTask(
                    name="Code",
                    description=f"Implement the requested change: {goal}",
                    agent="coding",
                    input=goal,
                    risk=RiskLevel.DANGEROUS,
                    resources=["project files"],
                    consequences="May create or modify files inside the agent workspace.",
                    dependencies=[tasks[-1].id] if tasks else [],
                )
            )
        if _matches(goal, _DESKTOP):
            tasks.append(
                WorkflowTask(
                    name="Desktop",
                    description=f"Apply the requested file change: {goal}",
                    agent="desktop",
                    input=goal,
                    risk=RiskLevel.DANGEROUS,
                    tool="desktop",
                    resources=["project files"],
                    consequences="May create, rename, or modify files inside the agent workspace.",
                    dependencies=[tasks[-1].id] if tasks else [],
                )
            )
        for task in tasks:
            if task.agent in DANGEROUS_AGENTS:
                task.risk = RiskLevel.DANGEROUS
        tasks = tasks[: limits.max_tasks]
        validate_graph(tasks)
        return tasks
    def _research_report(self, goal: str) -> list[WorkflowTask]:
        research = WorkflowTask(
            name="Research",
            description=f"Research the topic and search the web: {goal}",
            agent="research",
            input=f"Research and search the web for: {goal}",
            tool="web_research",
            timeout=90.0,
            checkpoint_name="Research complete",
        )
        knowledge = WorkflowTask(
            name="Knowledge",
            description="Look up the topic in the Knowledge Base.",
            agent="research",
            input=goal,
            tool="knowledge_base",
            dependencies=[research.id],
        )
        analyze = WorkflowTask(
            name="Analysis",
            description="Analyze the research and knowledge-base findings.",
            agent="planning",
            input="Analyze the findings already collected and summarize the important points.",
            timeout=90.0,
            dependencies=[research.id, knowledge.id],
        )
        draft = WorkflowTask(
            name="Draft",
            description="Write a short report with sources.",
            agent="planning",
            input="Write a short report from the analysis. Include the sources that were collected.",
            timeout=90.0,
            dependencies=[analyze.id],
            checkpoint_name="Draft complete",
        )
        review = WorkflowTask(
            name="Review",
            description="Review the draft against the user's request.",
            agent="review",
            input="Review the draft for missing points, errors, and missing sources.",
            timeout=90.0,
            dependencies=[draft.id],
            checkpoint_name="Review complete",
        )
        return [research, knowledge, analyze, draft, review]
