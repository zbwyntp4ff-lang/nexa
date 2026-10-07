"""Task-graph helpers: dependencies, cycles, and who may run next."""
from __future__ import annotations
from app.models.errors import WorkflowCycleError, WorkflowInvalidTaskError
from app.workflows.models import WorkflowStatus, WorkflowTask
def validate_graph(tasks: list[WorkflowTask]) -> None:
    """Reject unknown dependency ids and cyclic graphs before anything runs."""
    if not tasks:
        raise WorkflowInvalidTaskError("A workflow needs at least one task.")
    ids = {task.id for task in tasks}
    seen: set[tuple[str, str, str]] = set()
    for task in tasks:
        if not task.name.strip() or not task.description.strip():
            raise WorkflowInvalidTaskError("Every task needs a name and a description.")
        if not task.agent.strip():
            raise WorkflowInvalidTaskError(f"Task '{task.name}' has no agent.")
        signature = (task.name.strip().lower(), task.agent, task.description.strip().lower())
        if signature in seen:
            raise WorkflowInvalidTaskError(f"Repeated task '{task.name}' is not allowed.")
        seen.add(signature)
        for dep in task.dependencies:
            if dep not in ids:
                raise WorkflowInvalidTaskError(f"Task '{task.name}' depends on unknown task '{dep}'.")
            if dep == task.id:
                raise WorkflowCycleError(f"Task '{task.name}' depends on itself.")
    cycle = find_cycle(tasks)
    if cycle:
        raise WorkflowCycleError("Cyclic task dependencies: " + " -> ".join(cycle))
def find_cycle(tasks: list[WorkflowTask]) -> list[str] | None:
    """Depth-first search over dependency edges. Returns one cycle, if any."""
    deps = {task.id: list(task.dependencies) for task in tasks}
    names = {task.id: task.name for task in tasks}
    white, gray, black = 0, 1, 2
    color = {task_id: white for task_id in deps}
    stack: list[str] = []
    def walk(node: str) -> list[str] | None:
        color[node] = gray
        stack.append(node)
        for dep in deps[node]:
            if color[dep] == gray:
                start = stack.index(dep)
                return [names[item] for item in stack[start:]] + [names[dep]]
            if color[dep] == white:
                found = walk(dep)
                if found:
                    return found
        stack.pop()
        color[node] = black
        return None
    for task_id in deps:
        if color[task_id] == white:
            found = walk(task_id)
            if found:
                return found
    return None
def ready_tasks(tasks: list[WorkflowTask]) -> list[WorkflowTask]:
    """Tasks whose dependencies are all completed and that are still pending."""
    completed = {task.id for task in tasks if task.status == WorkflowStatus.COMPLETED}
    return [
        task
        for task in tasks
        if task.status == WorkflowStatus.PENDING and all(dep in completed for dep in task.dependencies)
    ]
def blocked_by_failure(tasks: list[WorkflowTask]) -> list[WorkflowTask]:
    """Pending tasks that can never run because a dependency failed or was cancelled."""
    dead = {
        task.id
        for task in tasks
        if task.status in (WorkflowStatus.FAILED, WorkflowStatus.CANCELLED)
    }
    blocked: list[WorkflowTask] = []
    changed = True
    while changed:
        changed = False
        for task in tasks:
            if task.status != WorkflowStatus.PENDING or task in blocked:
                continue
            if any(dep in dead or any(item.id == dep for item in blocked) for dep in task.dependencies):
                blocked.append(task)
                changed = True
    return blocked
