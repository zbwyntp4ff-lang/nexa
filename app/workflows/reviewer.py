"""Final review before a workflow may be marked completed.
Uses the existing Review Agent's output (the Review task) and then applies
deterministic checks. A failed check leaves the workflow FAILED.
"""
from __future__ import annotations
from app.core.secrets import contains_secret
from app.workflows.models import Workflow, WorkflowStatus
class WorkflowReviewer:
    def review(self, workflow: Workflow) -> tuple[bool, str]:
        problems: list[str] = []
        required = [task for task in workflow.tasks if task.required]
        unfinished = [task.name for task in required if task.status != WorkflowStatus.COMPLETED]
        if unfinished:
            problems.append("Required tasks are not complete: " + ", ".join(unfinished))
        if any(task.status == WorkflowStatus.FAILED for task in workflow.tasks):
            problems.append("A task failed.")
        if workflow.error:
            problems.append(workflow.error)
        draft = next((task.output or "" for task in workflow.tasks if task.name == "Draft"), "")
        review_output = next((task.output or "" for task in workflow.tasks if task.name == "Review"), "")
        final = draft or review_output or workflow.final_result or ""
        if not final.strip():
            problems.append("The workflow produced no result.")
        research = any(task.tool == "web_research" for task in workflow.tasks)
        if research and not workflow.sources and "http" not in final.lower() and "source" not in final.lower():
            problems.append("The report has no sources.")
        blob = "\n".join(task.output or "" for task in workflow.tasks)
        if contains_secret(blob) or contains_secret(final):
            problems.append("The result contains a secret.")
        if any(record.status == "permission_denied" for record in workflow.audit):
            problems.append("A permission check failed.")
        if problems:
            return False, "; ".join(problems)
        return True, final
