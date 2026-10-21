"""Godot engine adapter — detect, project tree, diffs, run with confirmation."""
from __future__ import annotations

from typing import Any

from app.plugins.base import PluginAdapter, PluginContext
from app.plugins.detect import first_existing, godot_candidates, run_version
from app.plugins.errors import PluginConfirmationRequiredError, PluginUnavailableError, PluginValidationError
from app.plugins.models import PluginActionSpec, PluginManifest, PluginResult, ProbeResult
from app.plugins.workspace import FileWorkspace


class GodotAdapter(PluginAdapter):
    manifest = PluginManifest(
        id="godot",
        version="1.0.0",
        name="Godot",
        description="Detect Godot, inspect an allowed project, preview file diffs, and run the project only with confirmation. Unknown scripts are not executed automatically.",
        category="game",
        integration_type="local",
        dependencies=["Godot 4 editor/binary"],
        required_permissions=["app.detect", "files.read"],
        optional_permissions=["files.write", "app.launch"],
        actions=[
            PluginActionSpec(name="detect", description="Find Godot and version", permissions=["app.detect"]),
            PluginActionSpec(name="list", description="List allowed project files", permissions=["files.read"]),
            PluginActionSpec(
                name="read",
                description="Read a project file",
                permissions=["files.read"],
                input_schema={"path": {"type": "string"}},
            ),
            PluginActionSpec(
                name="preview_write",
                description="Diff before write",
                permissions=["files.write"],
                input_schema={"path": {"type": "string"}, "content": {"type": "string"}},
            ),
            PluginActionSpec(
                name="apply_write",
                description="Apply write after confirmation",
                permissions=["files.write"],
                dangerous=True,
                input_schema={"path": {"type": "string"}, "content": {"type": "string"}},
            ),
            PluginActionSpec(
                name="undo",
                description="Undo last write",
                permissions=["files.write"],
                dangerous=True,
            ),
            PluginActionSpec(
                name="run",
                description="Run the allowed Godot project headless (confirm)",
                permissions=["app.launch"],
                dangerous=True,
            ),
        ],
        install_hint="Install Godot 4 and put `godot` (or Godot*.exe) on PATH. Place project files in the plugin workspace.",
    )

    async def probe(self, ctx: PluginContext) -> ProbeResult:
        exe = first_existing(godot_candidates())
        ws = FileWorkspace(ctx.workspace_root, "godot", ctx.max_file_bytes)
        if not exe:
            return ProbeResult(
                ok=False,
                status="missing_dependency",
                detail="Godot executable was not found",
                diagnostics={"workspace": str(ws.root)},
            )
        try:
            code, out = run_version(str(exe), ["--version"], min(ctx.timeout_seconds, 10))
        except (TimeoutError, OSError) as exc:
            return ProbeResult(ok=False, status="error", detail=str(exc))
        version = out.splitlines()[0] if out else None
        if code != 0 and not version:
            return ProbeResult(
                ok=False,
                status="error",
                detail="Godot --version failed",
                diagnostics={"executable": str(exe), "log": out},
            )
        return ProbeResult(
            ok=True,
            status="connected",
            detail="Godot detected",
            version=version,
            diagnostics={"executable": str(exe), "workspace": str(ws.root)},
        )

    async def execute(self, action: str, params: dict[str, Any], ctx: PluginContext) -> PluginResult:
        ws = FileWorkspace(ctx.workspace_root, "godot", ctx.max_file_bytes)
        if action == "detect":
            probe = await self.probe(ctx)
            return PluginResult(success=probe.ok, output=probe.model_dump(), error=None if probe.ok else probe.detail)
        if action == "list":
            return PluginResult(success=True, output={"files": ws.list_tree(".")})
        if action == "read":
            path = str(params.get("path") or "")
            if not path:
                raise PluginValidationError("path is required")
            return PluginResult(success=True, output={"path": path, "content": ws.read_text(path)})
        if action == "preview_write":
            path = str(params.get("path") or "")
            if not path:
                raise PluginValidationError("path is required")
            return PluginResult(success=True, output=ws.preview_write(path, str(params.get("content") or "")))
        if action == "apply_write":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("godot", "apply_write")
            path = str(params.get("path") or "")
            if not path:
                raise PluginValidationError("path is required")
            preview = ws.preview_write(path, str(params.get("content") or ""))
            applied = ws.apply_write(path, str(params.get("content") or ""))
            applied["diff"] = preview["diff"]
            return PluginResult(success=True, output=applied)
        if action == "undo":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("godot", "undo")
            return PluginResult(success=True, output=ws.undo_last())
        if action == "run":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("godot", "run")
            exe = first_existing(godot_candidates())
            if not exe:
                raise PluginUnavailableError("Godot is not installed")
            project = ws.root / "project.godot"
            if not project.is_file():
                return PluginResult(
                    success=False,
                    error="No project.godot in the allowed folder — refusing to run an unknown project.",
                )
            code, out = run_version(
                str(exe),
                ["--headless", "--path", str(ws.root), "--quit-after", "1"],
                min(ctx.timeout_seconds, 25),
            )
            return PluginResult(
                success=code == 0,
                output={"exit_code": code, "log": out[-1500:]},
                error=None if code == 0 else "Godot run failed",
            )
        raise PluginValidationError(f"Unknown action '{action}'")
