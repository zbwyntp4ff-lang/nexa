"""VS Code / limited local project adapter."""
from __future__ import annotations

from typing import Any

from app.plugins.base import PluginAdapter, PluginContext
from app.plugins.detect import first_existing, run_version, vscode_candidates
from app.plugins.errors import PluginConfirmationRequiredError, PluginValidationError
from app.plugins.models import PluginActionSpec, PluginManifest, PluginResult, ProbeResult
from app.plugins.workspace import FileWorkspace


class VsCodeAdapter(PluginAdapter):
    manifest = PluginManifest(
        id="vscode",
        version="1.0.0",
        name="VS Code",
        description="Open a permitted project folder, list/read files, preview diffs, apply or undo edits. No full-disk access and no automatic terminal commands.",
        category="editor",
        integration_type="local",
        dependencies=["Visual Studio Code (code CLI) — optional for the limited local adapter"],
        required_permissions=["files.read"],
        optional_permissions=["files.write", "app.launch"],
        actions=[
            PluginActionSpec(
                name="detect",
                description="Detect VS Code CLI and version",
                permissions=[],
            ),
            PluginActionSpec(
                name="list",
                description="List files in the allowed project",
                permissions=["files.read"],
                input_schema={"path": {"type": "string"}},
            ),
            PluginActionSpec(
                name="read",
                description="Read a file in the allowed project",
                permissions=["files.read"],
                input_schema={"path": {"type": "string"}},
            ),
            PluginActionSpec(
                name="preview_write",
                description="Show a unified diff before writing",
                permissions=["files.write"],
                input_schema={"path": {"type": "string"}, "content": {"type": "string"}},
            ),
            PluginActionSpec(
                name="apply_write",
                description="Apply a file write after confirmation",
                permissions=["files.write"],
                dangerous=True,
                input_schema={"path": {"type": "string"}, "content": {"type": "string"}},
            ),
            PluginActionSpec(
                name="undo",
                description="Undo the last write",
                permissions=["files.write"],
                dangerous=True,
            ),
            PluginActionSpec(
                name="open",
                description="Open the allowed project in VS Code (requires CLI + permission)",
                permissions=["app.launch"],
                dangerous=True,
            ),
        ],
        install_hint="Install VS Code and ensure the `code` command is on PATH. File edits still work in the NEXA plugin workspace without the CLI.",
    )

    async def probe(self, ctx: PluginContext) -> ProbeResult:
        exe = first_existing(vscode_candidates())
        ws = FileWorkspace(ctx.workspace_root, "vscode", ctx.max_file_bytes)
        diagnostics = {"workspace": str(ws.root), "cli": str(exe) if exe else None}
        if exe:
            try:
                code, out = run_version(str(exe), ["--version"], min(ctx.timeout_seconds, 8))
                version = out.splitlines()[0] if out else None
                return ProbeResult(
                    ok=True,
                    status="connected",
                    detail="VS Code CLI detected",
                    version=version if code == 0 else None,
                    diagnostics=diagnostics,
                )
            except (TimeoutError, FileNotFoundError, OSError) as exc:
                return ProbeResult(
                    ok=True,
                    status="connected_limited",
                    detail="CLI present but version check failed; using limited local adapter",
                    limitation=str(exc),
                    diagnostics=diagnostics,
                )
        return ProbeResult(
            ok=True,
            status="connected_limited",
            detail="VS Code CLI not found; limited local adapter for the allowed project folder",
            limitation="Official VS Code CLI is unavailable. File list/read/diff/undo work only inside the plugin workspace.",
            diagnostics=diagnostics,
        )

    async def execute(self, action: str, params: dict[str, Any], ctx: PluginContext) -> PluginResult:
        ws = FileWorkspace(ctx.workspace_root, "vscode", ctx.max_file_bytes)
        if action == "detect":
            probe = await self.probe(ctx)
            return PluginResult(success=probe.ok, output=probe.model_dump())
        if action == "list":
            return PluginResult(success=True, output={"files": ws.list_tree(str(params.get("path") or "."))})
        if action == "read":
            path = str(params.get("path") or "")
            if not path:
                raise PluginValidationError("path is required")
            return PluginResult(success=True, output={"path": path, "content": ws.read_text(path)})
        if action == "preview_write":
            path = str(params.get("path") or "")
            content = str(params.get("content") or "")
            if not path:
                raise PluginValidationError("path is required")
            return PluginResult(success=True, output=ws.preview_write(path, content))
        if action == "apply_write":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("vscode", "apply_write")
            path = str(params.get("path") or "")
            content = str(params.get("content") or "")
            if not path:
                raise PluginValidationError("path is required")
            preview = ws.preview_write(path, content)
            applied = ws.apply_write(path, content)
            applied["diff"] = preview["diff"]
            return PluginResult(success=True, output=applied)
        if action == "undo":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("vscode", "undo")
            return PluginResult(success=True, output=ws.undo_last())
        if action == "open":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("vscode", "open")
            exe = first_existing(vscode_candidates())
            if not exe:
                return PluginResult(
                    success=False,
                    error="VS Code CLI is not installed; cannot open the editor.",
                )
            try:
                run_version(str(exe), [str(ws.root)], min(ctx.timeout_seconds, 10))
            except (TimeoutError, OSError) as exc:
                return PluginResult(success=False, error=str(exc))
            return PluginResult(success=True, output={"opened": str(ws.root)})
        raise PluginValidationError(f"Unknown action '{action}'")
