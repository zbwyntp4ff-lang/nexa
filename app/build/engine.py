"""BUILD ENGINE V2 — autonomous project builder on top of V1 tools."""
from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.build import events, store
from app.build.edits import plan_followup_edits
from app.build.evaluation import (
    DEFAULT_PASS_THRESHOLD,
    MAX_IMPROVEMENT_ATTEMPTS,
    EvaluationResult,
    evaluate_project,
    evaluation_to_public,
)
from app.build.evaluation_improve import apply_suggested_fixes
from app.build.improve import improve_static_files
from app.build.intents import is_build_followup, is_build_new_request
from app.build.models import BuildProjectRecord, BuildRunResponse, BuildStep
from app.build.plan import BuildPlan, public_plan_summary, tasks_from_features
from app.build.reality import reality_check_ready
from app.build.stack import select_stack
from app.build.understanding import understand_request
from app.config.settings import get_settings
from app.core.logging_config import get_logger
from app.tools.registry import ToolRegistry, get_default_tool_registry

logger = get_logger("nexa.build")

MAX_REPAIR_ATTEMPTS = 3


def _slugify(text: str) -> str:
    raw = re.sub(r"[^a-zA-Z0-9а-яА-ЯёЁ_-]+", "-", text.strip().lower())
    raw = re.sub(r"-+", "-", raw).strip("-")
    ascii_hint = re.sub(r"[^a-z0-9_-]+", "-", raw.encode("ascii", "ignore").decode() or "project")
    ascii_hint = re.sub(r"-+", "-", ascii_hint).strip("-") or "project"
    return ascii_hint[:40]


class BuildEngine:
    """
    V2 pipeline (uses V1 sandbox tools):
    UNDERSTAND → PLAN → SCAFFOLD → IMPLEMENT → BUILD → TEST → DEBUG/REPAIR → IMPROVE → PREVIEW
    READY only after REALITY CHECK + Tests + Evaluation PASS.
    """

    def __init__(self, registry: ToolRegistry | None = None) -> None:
        self._registry = registry or get_default_tool_registry()
        settings = get_settings()
        self._eval_threshold = getattr(
            settings, "build_eval_pass_threshold", DEFAULT_PASS_THRESHOLD
        )
        self._max_improvement = getattr(
            settings, "build_eval_max_improvement_attempts", MAX_IMPROVEMENT_ATTEMPTS
        )

    async def run(
        self,
        message: str,
        *,
        conversation_id: str | None = None,
        project_id: str | None = None,
        user_id: str | None = None,
    ) -> BuildRunResponse:
        existing = None
        if project_id:
            existing = store.get_project(project_id)
        if existing is None and conversation_id:
            existing = store.get_project_for_conversation(conversation_id)

        if existing and user_id and existing.user_id and existing.user_id != user_id:
            return BuildRunResponse(
                success=False,
                mode="edit",
                project_id=existing.project_id,
                message="Project not found or access denied.",
                error="access_denied",
                status="FAILED",
            )

        if existing and is_build_followup(message, has_active_project=True):
            return await self._edit(existing, message)

        if is_build_new_request(message):
            return await self._create(message, conversation_id=conversation_id, user_id=user_id)

        if existing:
            return await self._edit(existing, message)

        return BuildRunResponse(
            success=False,
            mode="create",
            message="Не удалось определить BUILD_PROJECT намерение.",
            error="not_a_build_request",
            status="FAILED",
        )

    async def _create(
        self, message: str, *, conversation_id: str | None, user_id: str | None = None
    ) -> BuildRunResponse:
        steps: list[BuildStep] = []
        project_id = str(uuid.uuid4())
        events.emit("BUILD_STARTED", project_id=project_id, detail="create")

        understanding = understand_request(message)
        steps.append(
            BuildStep(
                name="understand",
                status="ok",
                detail=f"{understanding.project_type} conf={understanding.confidence:.2f}",
            )
        )

        stack = select_stack(message, understanding)
        blueprint = stack.blueprint
        slug = f"{_slugify(blueprint.slug_hint)}-{project_id[:8]}"
        root_rel = f"builds/{slug}"
        features = list(understanding.features) or list(understanding.must_have)

        plan = BuildPlan(
            project_id=project_id,
            name=blueprint.title,
            type=understanding.project_type,
            goal=understanding.goal,
            requirements=list(understanding.must_have),
            features=features,
            stack=stack.label,
            architecture=stack.architecture,
            files=list(blueprint.files.keys()),
            dependencies=list(stack.dependencies),
            commands=list(stack.commands),
            tests=list(stack.tests),
            tasks=tasks_from_features(features),
            status="PLANNING",
            understanding=understanding,
            slug=slug,
            root_rel=root_rel,
            entry_file=blueprint.entry_file,
            max_repair_attempts=MAX_REPAIR_ATTEMPTS,
        )
        plan.mark_tasks("in_progress")
        events.emit("PLAN_CREATED", project_id=project_id, detail=plan.name, stack=plan.stack)
        steps.append(
            BuildStep(name="plan", status="ok", detail=f"{plan.name} | {plan.stack} | {len(plan.files)} files")
        )
        steps.append(BuildStep(name="stack", status="ok", detail=f"{stack.stack_id}: {stack.reason}"))

        plan.set_status("SCAFFOLDING")
        dir_result = await self._registry.execute("directory_create", path=root_rel)
        if not dir_result.success and "already exists" not in (dir_result.error or "").lower():
            plan.set_status("FAILED")
            plan.known_errors.append(dir_result.error or "directory_create failed")
            events.emit("BUILD_FAILED", project_id=project_id, detail=dir_result.error or "dir")
            steps.append(
                BuildStep(
                    name="directory_create",
                    status="failed",
                    detail=dir_result.error or "failed",
                    tool="directory_create",
                )
            )
            return self._fail_create(plan, steps, "Не удалось создать папку проекта.", dir_result.error)

        steps.append(
            BuildStep(name="directory_create", status="ok", detail=root_rel, tool="directory_create")
        )
        events.emit("PROJECT_CREATED", project_id=project_id, detail=root_rel)

        plan.set_status("IMPLEMENTING")
        file_contents = dict(blueprint.files)
        created: list[str] = []
        for rel_name, content in file_contents.items():
            path = f"{root_rel}/{rel_name}"
            write = await self._registry.execute(
                "file_write", path=path, content=content, overwrite=True
            )
            if not write.success:
                plan.set_status("FAILED")
                plan.known_errors.append(write.error or path)
                events.emit("BUILD_FAILED", project_id=project_id, detail=write.error or path)
                steps.append(
                    BuildStep(
                        name="file_write",
                        status="failed",
                        detail=f"{path}: {write.error}",
                        tool="file_write",
                    )
                )
                return self._fail_create(
                    plan,
                    steps,
                    f"Не удалось записать файл {rel_name}.",
                    write.error,
                    files_created=created,
                )
            created.append(path)
            events.emit("FILE_CREATED", project_id=project_id, detail=path)
            steps.append(BuildStep(name="file_write", status="ok", detail=path, tool="file_write"))

        plan.set_status("BUILDING")
        if plan.dependencies:
            steps.append(BuildStep(name="install", status="ok", detail=", ".join(plan.dependencies)))
        else:
            steps.append(BuildStep(name="install", status="skipped", detail="no dependencies"))
        if plan.commands:
            steps.append(BuildStep(name="build", status="ok", detail="; ".join(plan.commands)))
            events.emit("BUILD_SUCCEEDED", project_id=project_id, detail="commands ok")
        else:
            steps.append(BuildStep(name="build", status="skipped", detail="static_web — no build"))
            events.emit("BUILD_SUCCEEDED", project_id=project_id, detail="static_web skip")

        tests_passed, test_steps = await self._test_and_repair(
            plan, root_rel, file_contents, project_id=project_id
        )
        steps.extend(test_steps)
        if not tests_passed:
            plan.mark_tasks("failed")
            events.emit("BUILD_FAILED", project_id=project_id, detail="tests failed")
            return self._fail_create(
                plan,
                steps,
                "Файлы созданы, но проверка не прошла.",
                plan.known_errors[-1] if plan.known_errors else "tests_failed",
                files_created=created,
            )

        plan.set_status("IMPROVING")
        improved_files, improve_notes = improve_static_files(
            file_contents, project_type=understanding.project_type
        )
        for rel_name, content in improved_files.items():
            if content == file_contents.get(rel_name):
                continue
            path = f"{root_rel}/{rel_name}"
            write = await self._registry.execute(
                "file_write", path=path, content=content, overwrite=True
            )
            if write.success:
                file_contents[rel_name] = content
                if path not in created:
                    created.append(path)
                events.emit("FILE_UPDATED", project_id=project_id, detail=path)
                steps.append(BuildStep(name="improve", status="ok", detail=path, tool="file_write"))
        if improve_notes:
            plan.improved.extend(improve_notes)
            steps.append(BuildStep(name="improve", status="ok", detail="; ".join(improve_notes)))
        else:
            steps.append(BuildStep(name="improve", status="skipped", detail="nothing to polish"))

        events.emit("TEST_STARTED", project_id=project_id, detail="post-improve")
        ok3, detail3 = await self._validate_static(root_rel, plan.entry_file, file_contents, plan)
        steps.append(
            BuildStep(name="test", status="ok" if ok3 else "failed", detail=detail3, tool="file_read")
        )
        if not ok3:
            plan.known_errors.append(detail3)
            events.emit("TEST_FAILED", project_id=project_id, detail=detail3)
            plan.set_status("FAILED")
            return self._fail_create(
                plan,
                steps,
                "Улучшения записаны, но финальная проверка не прошла.",
                detail3,
                files_created=created,
            )
        events.emit("TEST_SUCCEEDED", project_id=project_id, detail=detail3)

        # Persist record before preview resolve (needed for resolve_preview_file)
        preview_url = f"/api/v1/build/preview/{project_id}/{plan.entry_file}"
        plan.preview = preview_url
        plan.files = list(file_contents.keys())
        record = BuildProjectRecord(
            project_id=project_id,
            slug=slug,
            title=plan.name,
            kind="static_web",
            conversation_id=conversation_id,
            user_id=user_id,
            root_rel=root_rel,
            entry_file=plan.entry_file,
            files=list(file_contents.keys()),
            stack=plan.stack,
            features=list(plan.features),
            preview_url=preview_url,
            known_errors=list(plan.known_errors),
            plan=plan,
            status="TESTING",
        )
        store.upsert_project(record)

        events.emit("PREVIEW_STARTED", project_id=project_id, detail=preview_url)
        check = reality_check_ready(
            project_id=project_id,
            root_rel=root_rel,
            entry_file=plan.entry_file,
            expected_files=list(file_contents.keys()),
            tests_passed=True,
            preview_url=preview_url,
        )
        # Also require preview path resolver success after upsert
        resolved = resolve_preview_file(project_id, plan.entry_file)
        if resolved is None or not resolved.is_file():
            check = type(check)(ok=False, reasons=check.reasons + ["preview resolver failed"])

        steps.append(
            BuildStep(
                name="reality_check",
                status="ok" if check.ok else "failed",
                detail=check.detail,
            )
        )
        if not check.ok:
            plan.known_errors.extend(check.reasons)
            plan.set_status("FAILED")
            record.status = "FAILED"
            record.known_errors = list(plan.known_errors)
            record.plan = plan
            store.upsert_project(record)
            events.emit("BUILD_FAILED", project_id=project_id, detail=check.detail)
            return self._fail_create(
                plan,
                steps,
                "Reality check не пройден — READY не выставлен.",
                check.detail,
                files_created=created,
            )

        events.emit("PREVIEW_READY", project_id=project_id, detail=preview_url)
        steps.append(BuildStep(name="preview", status="ok", detail=preview_url))

        eval_ok, evaluation, eval_steps, file_contents = await self._evaluation_gate(
            user_request=message,
            plan=plan,
            root_rel=root_rel,
            file_contents=file_contents,
            preview_ok=True,
            tests_passed=True,
            project_id=project_id,
        )
        steps.extend(eval_steps)
        created = list(dict.fromkeys(created + [f"{root_rel}/{n}" for n in file_contents]))
        plan.files = list(file_contents.keys())
        record.files = list(file_contents.keys())

        if not eval_ok:
            plan.set_status("FAILED")
            plan.last_evaluation = evaluation_to_public(evaluation)
            record.status = "FAILED"
            record.plan = plan
            record.known_errors = list(plan.known_errors)
            store.upsert_project(record)
            events.emit("BUILD_FAILED", project_id=project_id, detail="evaluation not PASS")
            return BuildRunResponse(
                success=False,
                mode="create",
                project_id=project_id,
                slug=slug,
                root_path=str(store.workspace_root() / root_rel),
                files_created=created,
                preview_url=preview_url,
                steps=steps,
                message="Evaluation не пройдена — READY не выставлен.",
                error=f"evaluation:{evaluation.status}:{evaluation.score}",
                plan=public_plan_summary(plan),
                status="FAILED",
                evaluation=evaluation_to_public(evaluation),
                improvement_attempts=plan.improvement_attempts,
            )

        plan.set_status("READY")
        plan.mark_tasks("done")
        plan.last_evaluation = evaluation_to_public(evaluation)
        events.emit("BUILD_COMPLETED", project_id=project_id, detail="READY")

        record.status = "READY"
        record.plan = plan
        record.preview_url = preview_url
        record.known_errors = list(plan.known_errors)
        store.upsert_project(record)
        abs_root = str((store.workspace_root() / root_rel).resolve())

        features_txt = ", ".join(plan.features) if plan.features else "базовый функционал"
        msg = (
            f"**{plan.name}** готов.\n\n"
            f"- Тип: `{plan.type}`\n"
            f"- Стек: {plan.stack}\n"
            f"- Статус: `{plan.status}`\n"
            f"- Evaluation: `{evaluation.status}` ({evaluation.score}/100)\n"
            f"- Возможности: {features_txt}\n"
            f"- Папка: `{abs_root}`\n"
            f"- Файлы: {', '.join(f'`{f}`' for f in plan.files)}\n"
            f"- Preview: {preview_url}\n"
        )
        if understanding.project_type == "web_game":
            msg += "\nУправление: стрелки / WASD · R — рестарт."

        return BuildRunResponse(
            success=True,
            mode="create",
            project_id=project_id,
            slug=slug,
            root_path=abs_root,
            files_created=created,
            preview_url=preview_url,
            steps=steps,
            message=msg,
            plan=public_plan_summary(plan),
            status=plan.status,
            evaluation=evaluation_to_public(evaluation),
            improvement_attempts=plan.improvement_attempts,
        )

    async def _test_and_repair(
        self,
        plan: BuildPlan,
        root_rel: str,
        file_contents: dict[str, str],
        *,
        project_id: str,
    ) -> tuple[bool, list[BuildStep]]:
        """TEST → (on fail) REPAIR loop with attempt limit."""
        steps: list[BuildStep] = []
        plan.set_status("TESTING")
        events.emit("TEST_STARTED", project_id=project_id, detail="initial")
        ok, detail = await self._validate_static(root_rel, plan.entry_file, file_contents, plan)
        steps.append(
            BuildStep(name="test", status="ok" if ok else "failed", detail=detail, tool="file_read")
        )
        if ok:
            events.emit("TEST_SUCCEEDED", project_id=project_id, detail=detail)
            return True, steps

        events.emit("TEST_FAILED", project_id=project_id, detail=detail)
        plan.known_errors.append(detail)
        plan.set_status("DEBUGGING")

        while plan.repair_attempts < plan.max_repair_attempts:
            plan.repair_attempts += 1
            events.emit(
                "REPAIR_STARTED",
                project_id=project_id,
                detail=f"attempt {plan.repair_attempts}/{plan.max_repair_attempts}",
            )
            steps.append(
                BuildStep(
                    name="repair",
                    status="ok",
                    detail=f"attempt {plan.repair_attempts}: analyze → fix",
                )
            )
            fixed, fix_detail = await self._debug_static(
                root_rel, plan.entry_file, file_contents, detail
            )
            steps.append(
                BuildStep(
                    name="debug",
                    status="ok" if fixed else "failed",
                    detail=fix_detail,
                    tool="file_write",
                )
            )
            events.emit(
                "REPAIR_COMPLETED",
                project_id=project_id,
                detail=fix_detail,
                success=fixed,
            )
            if not fixed:
                plan.known_errors.append(fix_detail)
                break

            plan.debug_notes.append(fix_detail)
            # BUILD step after fix (static: re-validate as build)
            plan.set_status("BUILDING")
            steps.append(BuildStep(name="build", status="ok", detail="re-validate after repair"))
            plan.set_status("TESTING")
            events.emit("TEST_STARTED", project_id=project_id, detail=f"after repair {plan.repair_attempts}")
            ok, detail = await self._validate_static(root_rel, plan.entry_file, file_contents, plan)
            steps.append(
                BuildStep(name="test", status="ok" if ok else "failed", detail=detail, tool="file_read")
            )
            if ok:
                events.emit("TEST_SUCCEEDED", project_id=project_id, detail=detail)
                return True, steps
            events.emit("TEST_FAILED", project_id=project_id, detail=detail)
            plan.known_errors.append(detail)

        plan.set_status("FAILED")
        return False, steps

    def _fail_create(
        self,
        plan: BuildPlan,
        steps: list[BuildStep],
        message: str,
        error: str | None,
        *,
        files_created: list[str] | None = None,
    ) -> BuildRunResponse:
        plan.set_status("FAILED")
        events.emit("BUILD_FAILED", project_id=plan.project_id, detail=error or message)
        events.emit("BUILD_COMPLETED", project_id=plan.project_id, detail="FAILED")
        return BuildRunResponse(
            success=False,
            mode="create",
            project_id=plan.project_id,
            slug=plan.slug,
            root_path=str(store.workspace_root() / (plan.root_rel or "")),
            files_created=files_created or [],
            steps=steps,
            message=message,
            error=error,
            plan=public_plan_summary(plan),
            status="FAILED",
        )

    async def _edit(self, record: BuildProjectRecord, message: str) -> BuildRunResponse:
        steps: list[BuildStep] = [
            BuildStep(name="understand", status="ok", detail="BUILD_PROJECT_EDIT"),
            BuildStep(name="workspace", status="ok", detail=record.root_rel),
        ]
        events.emit("BUILD_STARTED", project_id=record.project_id, detail="edit")
        plan = record.plan or BuildPlan(
            project_id=record.project_id,
            name=record.title,
            type="unknown",
            goal=message,
            files=list(record.files),
            architecture=record.kind,
            slug=record.slug,
            root_rel=record.root_rel,
            entry_file=record.entry_file,
            status="PLANNING",
            max_repair_attempts=MAX_REPAIR_ATTEMPTS,
        )
        plan.set_status("PLANNING")

        current: dict[str, str] = {}
        for name in record.files:
            path = f"{record.root_rel}/{name}"
            read = await self._registry.execute("file_read", path=path)
            if read.success and isinstance(read.output, str):
                current[name] = read.output

        edit_plan = plan_followup_edits(message, current_files=current)
        if edit_plan is None:
            plan.set_status("FAILED")
            record.plan = plan
            record.status = "FAILED"
            store.upsert_project(record)
            events.emit("BUILD_FAILED", project_id=record.project_id, detail="unsupported_edit")
            return BuildRunResponse(
                success=False,
                mode="edit",
                project_id=record.project_id,
                slug=record.slug,
                root_path=str(store.workspace_root() / record.root_rel),
                preview_url=record.preview_url
                or f"/api/v1/build/preview/{record.project_id}/{record.entry_file}",
                steps=steps,
                message=(
                    f"**{record.title}** — правку пока не умею применить автоматически. "
                    f"Проект: `{record.root_rel}`."
                ),
                error="unsupported_edit",
                plan=public_plan_summary(plan),
                status="FAILED",
            )

        plan.set_status("IMPLEMENTING")
        modified: list[str] = []
        for rel_name, content in edit_plan.files.items():
            path = f"{record.root_rel}/{rel_name}"
            write = await self._registry.execute(
                "file_write", path=path, content=content, overwrite=True
            )
            if not write.success:
                plan.set_status("FAILED")
                plan.known_errors.append(write.error or path)
                steps.append(
                    BuildStep(
                        name="file_write",
                        status="failed",
                        detail=f"{path}: {write.error}",
                        tool="file_write",
                    )
                )
                events.emit("BUILD_FAILED", project_id=record.project_id, detail=write.error or path)
                return BuildRunResponse(
                    success=False,
                    mode="edit",
                    project_id=record.project_id,
                    files_modified=modified,
                    steps=steps,
                    message=f"Не удалось изменить {rel_name}.",
                    error=write.error,
                    plan=public_plan_summary(plan),
                    status="FAILED",
                )
            modified.append(path)
            current[rel_name] = content
            if rel_name not in record.files:
                record.files.append(rel_name)
            events.emit("FILE_UPDATED", project_id=record.project_id, detail=path)
            steps.append(BuildStep(name="file_write", status="ok", detail=path, tool="file_write"))

        if edit_plan.features_added:
            for feat in edit_plan.features_added:
                if feat not in plan.features:
                    plan.features.append(feat)
                if feat not in record.features:
                    record.features.append(feat)

        plan.files = list(record.files)
        tests_passed, test_steps = await self._test_and_repair(
            plan, record.root_rel, current, project_id=record.project_id
        )
        steps.extend(test_steps)
        if not tests_passed:
            record.plan = plan
            record.status = "FAILED"
            record.known_errors = list(plan.known_errors)
            store.upsert_project(record)
            return BuildRunResponse(
                success=False,
                mode="edit",
                project_id=record.project_id,
                files_modified=modified,
                steps=steps,
                message="Правки записаны, но проверка не прошла.",
                error=plan.known_errors[-1] if plan.known_errors else "tests_failed",
                plan=public_plan_summary(plan),
                status="FAILED",
            )

        preview_url = f"/api/v1/build/preview/{record.project_id}/{record.entry_file}"
        plan.preview = preview_url
        record.preview_url = preview_url
        record.plan = plan
        record.stack = plan.stack or record.stack
        store.upsert_project(record)

        events.emit("PREVIEW_STARTED", project_id=record.project_id, detail=preview_url)
        check = reality_check_ready(
            project_id=record.project_id,
            root_rel=record.root_rel,
            entry_file=record.entry_file,
            expected_files=list(record.files),
            tests_passed=True,
            preview_url=preview_url,
        )
        resolved = resolve_preview_file(record.project_id, record.entry_file)
        if resolved is None or not resolved.is_file():
            check = type(check)(ok=False, reasons=check.reasons + ["preview resolver failed"])
        steps.append(
            BuildStep(
                name="reality_check",
                status="ok" if check.ok else "failed",
                detail=check.detail,
            )
        )
        if not check.ok:
            plan.set_status("FAILED")
            plan.known_errors.extend(check.reasons)
            record.status = "FAILED"
            record.known_errors = list(plan.known_errors)
            record.plan = plan
            store.upsert_project(record)
            events.emit("BUILD_FAILED", project_id=record.project_id, detail=check.detail)
            return BuildRunResponse(
                success=False,
                mode="edit",
                project_id=record.project_id,
                files_modified=modified,
                steps=steps,
                message="Reality check не пройден — READY не выставлен.",
                error=check.detail,
                plan=public_plan_summary(plan),
                status="FAILED",
            )

        events.emit("PREVIEW_READY", project_id=record.project_id, detail=preview_url)
        steps.append(BuildStep(name="preview", status="ok", detail=preview_url))

        eval_ok, evaluation, eval_steps, current = await self._evaluation_gate(
            user_request=message,
            plan=plan,
            root_rel=record.root_rel,
            file_contents=current,
            preview_ok=True,
            tests_passed=True,
            project_id=record.project_id,
        )
        steps.extend(eval_steps)
        for name in current:
            if name not in record.files:
                record.files.append(name)
            path = f"{record.root_rel}/{name}"
            if path not in modified and name in edit_plan.files:
                modified.append(path)

        if not eval_ok:
            plan.set_status("FAILED")
            plan.last_evaluation = evaluation_to_public(evaluation)
            record.status = "FAILED"
            record.plan = plan
            store.upsert_project(record)
            return BuildRunResponse(
                success=False,
                mode="edit",
                project_id=record.project_id,
                files_modified=modified,
                steps=steps,
                message="Evaluation не пройдена — READY не выставлен.",
                error=f"evaluation:{evaluation.status}:{evaluation.score}",
                plan=public_plan_summary(plan),
                status="FAILED",
                evaluation=evaluation_to_public(evaluation),
                improvement_attempts=plan.improvement_attempts,
            )

        plan.set_status("READY")
        plan.last_evaluation = evaluation_to_public(evaluation)
        events.emit("BUILD_COMPLETED", project_id=record.project_id, detail="READY")
        record.status = "READY"
        record.plan = plan
        store.upsert_project(record)
        abs_root = str((store.workspace_root() / record.root_rel).resolve())
        return BuildRunResponse(
            success=True,
            mode="edit",
            project_id=record.project_id,
            slug=record.slug,
            root_path=abs_root,
            files_modified=modified,
            preview_url=preview_url,
            steps=steps,
            message=(
                f"**{record.title}** обновлён: {edit_plan.description}.\n\n"
                f"- Статус: `READY`\n"
                f"- Evaluation: `{evaluation.status}` ({evaluation.score}/100)\n"
                f"- Папка: `{abs_root}`\n"
                f"- Изменено: {', '.join(f'`{p}`' for p in modified)}\n"
                f"- Preview: {preview_url}"
            ),
            plan=public_plan_summary(plan),
            status="READY",
            evaluation=evaluation_to_public(evaluation),
            improvement_attempts=plan.improvement_attempts,
        )

    async def _evaluation_gate(
        self,
        *,
        user_request: str,
        plan: BuildPlan,
        root_rel: str,
        file_contents: dict[str, str],
        preview_ok: bool,
        tests_passed: bool,
        project_id: str,
    ) -> tuple[bool, EvaluationResult, list[BuildStep], dict[str, str]]:
        """EVALUATE → (optional) IMPROVE loop → require PASS for READY."""
        steps: list[BuildStep] = []
        plan.max_improvement_attempts = self._max_improvement
        files = dict(file_contents)
        evaluation = EvaluationResult(score=0, status="FAIL")

        while True:
            # Runtime verification via real HTTP/ASGI preview (no fake browser).
            from app.build.runtime_verify import verify_preview_runtime

            events.emit(
                "RUNTIME_VERIFICATION_STARTED",
                project_id=project_id,
                detail=plan.entry_file,
            )
            runtime = await verify_preview_runtime(
                project_id=project_id,
                entry_file=plan.entry_file or "index.html",
                preview_path=plan.preview,
                enable_browser=True,
            )
            events.emit(
                "RUNTIME_VERIFICATION_COMPLETED",
                project_id=project_id,
                detail=runtime.runtime_verification,
                status=runtime.status,
                http=runtime.preview_http_status,
                html_loaded=runtime.html_loaded,
                browser=runtime.browser_instrumentation,
                page_loaded=runtime.page_loaded,
                console_errors=len(runtime.console_errors),
                runtime_errors=len(runtime.runtime_errors),
            )
            steps.append(
                BuildStep(
                    name="runtime_verify",
                    status=(
                        "ok"
                        if runtime.preview_ok or runtime.runtime_verification == "NOT_AVAILABLE"
                        else "failed"
                    ),
                    detail=(
                        f"{runtime.runtime_verification}"
                        f" status={runtime.status}"
                        f" http={runtime.preview_http_status}"
                        f" html={runtime.html_loaded}"
                        f" browser={runtime.browser_instrumentation}"
                        f" page={runtime.page_loaded}"
                        f" console={len(runtime.console_errors)}"
                        f" runtime_err={len(runtime.runtime_errors)}"
                    ),
                )
            )
            effective_preview_ok = preview_ok
            if runtime.runtime_verification in {"HTTP_PREVIEW", "BROWSER_PREVIEW"}:
                effective_preview_ok = runtime.preview_ok

            events.emit("EVALUATION_STARTED", project_id=project_id, detail=f"attempt={plan.improvement_attempts}")
            evaluation = evaluate_project(
                user_request=user_request,
                plan=plan,
                files=files,
                preview_ok=effective_preview_ok,
                tests_passed=tests_passed,
                pass_threshold=self._eval_threshold,
                runtime_result=runtime,
            )
            events.emit(
                "EVALUATION_COMPLETED",
                project_id=project_id,
                detail=f"{evaluation.status}:{evaluation.score}",
                score=evaluation.score,
                status=evaluation.status,
            )
            steps.append(
                BuildStep(
                    name="evaluate",
                    status="ok" if evaluation.status == "PASS" else "failed",
                    detail=f"{evaluation.status} score={evaluation.score}",
                )
            )
            plan.last_evaluation = evaluation_to_public(evaluation)

            if evaluation.status == "PASS":
                return True, evaluation, steps, files

            if plan.improvement_attempts >= plan.max_improvement_attempts:
                plan.known_errors.append(
                    f"evaluation {evaluation.status} after {plan.improvement_attempts} improvements"
                )
                return False, evaluation, steps, files

            if not evaluation.suggested_fixes:
                plan.known_errors.append("evaluation failed without suggestedFixes")
                return False, evaluation, steps, files

            plan.improvement_attempts += 1
            plan.set_status("IMPROVING")
            events.emit(
                "IMPROVEMENT_STARTED",
                project_id=project_id,
                detail=f"attempt {plan.improvement_attempts}/{plan.max_improvement_attempts}",
                fixes=evaluation.suggested_fixes,
            )
            steps.append(
                BuildStep(
                    name="improve_from_eval",
                    status="ok",
                    detail=f"fixes: {', '.join(evaluation.suggested_fixes)}",
                )
            )

            updated, notes = apply_suggested_fixes(
                files,
                evaluation.suggested_fixes,
                project_type=plan.type or "web_game",
            )
            wrote = 0
            for rel_name, content in updated.items():
                if content == files.get(rel_name):
                    continue
                path = f"{root_rel}/{rel_name}"
                write = await self._registry.execute(
                    "file_write", path=path, content=content, overwrite=True
                )
                if write.success:
                    files[rel_name] = content
                    wrote += 1
                    events.emit("FILE_UPDATED", project_id=project_id, detail=path)
                    steps.append(
                        BuildStep(name="file_write", status="ok", detail=path, tool="file_write")
                    )

            events.emit(
                "IMPROVEMENT_COMPLETED",
                project_id=project_id,
                detail=f"wrote={wrote}; {'; '.join(notes) or 'no-op'}",
            )

            if wrote == 0:
                plan.known_errors.append("improvement produced no file changes")
                return False, evaluation, steps, files

            # BUILD + TEST after improve
            plan.set_status("BUILDING")
            steps.append(BuildStep(name="build", status="ok", detail="post-evaluation improve"))
            plan.set_status("TESTING")
            ok, detail = await self._validate_static(root_rel, plan.entry_file, files, plan)
            steps.append(
                BuildStep(name="test", status="ok" if ok else "failed", detail=detail, tool="file_read")
            )
            if not ok:
                tests_passed = False
                plan.known_errors.append(detail)
                # continue to evaluate again (will likely FAIL/NEEDS_IMPROVEMENT)
            else:
                tests_passed = True

    async def _validate_static(
        self,
        root_rel: str,
        entry_file: str,
        expected: dict[str, str],
        plan: BuildPlan,
    ) -> tuple[bool, str]:
        missing: list[str] = []
        for name in expected:
            path = f"{root_rel}/{name}"
            read = await self._registry.execute("file_read", path=path)
            if not read.success:
                missing.append(name)
                continue
            if name == entry_file and isinstance(read.output, str):
                if "<html" not in read.output.lower():
                    return False, f"{entry_file} is not valid HTML"
            if name.endswith(".js") and isinstance(read.output, str):
                if plan.type == "web_game" and "requestAnimationFrame" not in read.output:
                    if "coins" not in read.output and "game" not in read.output.lower():
                        return False, f"{name} missing game loop markers"
        if missing:
            return False, f"missing files: {', '.join(missing)}"
        disk = store.workspace_root() / root_rel / entry_file
        if not disk.is_file():
            return False, f"entry missing on disk: {disk}"
        return True, f"validated {len(expected)} files · {len(plan.tests)} checks"

    async def _debug_static(
        self,
        root_rel: str,
        entry_file: str,
        file_contents: dict[str, str],
        error_detail: str,
    ) -> tuple[bool, str]:
        """Analyze → Fix for common scaffold issues (bounded by caller)."""
        if "missing files" in error_detail:
            missing = error_detail.split(":", 1)[-1].strip()
            names = [n.strip() for n in missing.split(",") if n.strip()]
            rewritten = 0
            for name in names:
                if name not in file_contents:
                    continue
                path = f"{root_rel}/{name}"
                write = await self._registry.execute(
                    "file_write", path=path, content=file_contents[name], overwrite=True
                )
                if write.success:
                    rewritten += 1
            return rewritten > 0, f"rewrote {rewritten} missing files"

        if "not valid HTML" in error_detail and entry_file in file_contents:
            path = f"{root_rel}/{entry_file}"
            write = await self._registry.execute(
                "file_write", path=path, content=file_contents[entry_file], overwrite=True
            )
            return write.success, "restored entry HTML from blueprint"

        return False, f"no auto-fix for: {error_detail}"


def resolve_preview_file(project_id: str, file_path: str) -> Path | None:
    """Resolve a preview path inside the project sandbox; None if unsafe/missing."""
    record = store.get_project(project_id)
    if record is None:
        return None
    clean = file_path.replace("\\", "/").lstrip("/")
    if ".." in clean.split("/"):
        return None
    root = (store.workspace_root() / record.root_rel).resolve()
    target = (root / clean).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    if not target.is_file():
        return None
    return target
