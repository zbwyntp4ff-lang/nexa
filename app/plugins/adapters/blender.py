"""Blender local adapter — detect, version, constrained Python API, save with confirm."""
from __future__ import annotations

from typing import Any

from app.plugins.base import PluginAdapter, PluginContext
from app.plugins.detect import blender_candidates, first_existing, run_version
from app.plugins.errors import PluginConfirmationRequiredError, PluginUnavailableError, PluginValidationError
from app.plugins.models import PluginActionSpec, PluginManifest, PluginResult, ProbeResult
from app.plugins.workspace import FileWorkspace

_PROBE_PY = (
    "import bpy, sys; "
    "print('NEXA_BLENDER_OK', bpy.app.version_string); "
    "sys.exit(0)"
)

_SCENE_PY = """
import bpy
import sys
out = sys.argv[sys.argv.index('--') + 1]
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.mesh.primitive_cube_add(size=2)
bpy.ops.wm.save_as_mainfile(filepath=out)
print('NEXA_BLENDER_SAVED', out)
"""


class BlenderAdapter(PluginAdapter):
    manifest = PluginManifest(
        id="blender",
        version="1.0.0",
        name="Blender",
        description="Detect a real Blender install, verify the Python API, create a simple scene in the allowed project, and save only with confirmation.",
        category="3d",
        integration_type="local",
        dependencies=["Blender 3+ with bpy"],
        required_permissions=["app.detect"],
        optional_permissions=["blender.scene", "files.write"],
        actions=[
            PluginActionSpec(name="detect", description="Find Blender and print version", permissions=["app.detect"]),
            PluginActionSpec(name="python_api", description="Verify bpy via --python-expr", permissions=["app.detect"]),
            PluginActionSpec(
                name="create_scene",
                description="Create a cube scene and save to the allowed folder",
                permissions=["blender.scene", "files.write"],
                dangerous=True,
                input_schema={"filename": {"type": "string"}},
            ),
            PluginActionSpec(
                name="status",
                description="Last scene files in the allowed folder",
                permissions=["app.detect"],
            ),
        ],
        install_hint="Install Blender and add `blender` to PATH, or keep it under Program Files/Blender Foundation.",
    )

    async def probe(self, ctx: PluginContext) -> ProbeResult:
        exe = first_existing(blender_candidates())
        if not exe:
            return ProbeResult(
                ok=False,
                status="missing_dependency",
                detail="Blender executable was not found",
            )
        try:
            code, out = run_version(str(exe), ["--version"], min(ctx.timeout_seconds, 12))
        except (TimeoutError, OSError) as exc:
            return ProbeResult(ok=False, status="error", detail=str(exc))
        version = None
        for line in out.splitlines():
            if "Blender" in line:
                version = line.strip()
                break
        api_ok = False
        api_detail = ""
        try:
            acode, aout = run_version(
                str(exe),
                ["--background", "--python-expr", _PROBE_PY],
                min(ctx.timeout_seconds, 20),
            )
            api_ok = acode == 0 and "NEXA_BLENDER_OK" in aout
            api_detail = aout.splitlines()[-1] if aout else ""
        except (TimeoutError, OSError) as exc:
            api_detail = str(exc)
        if not api_ok:
            return ProbeResult(
                ok=False,
                status="error",
                detail="Blender found but Python API check failed",
                version=version,
                limitation=api_detail,
                diagnostics={"executable": str(exe)},
            )
        return ProbeResult(
            ok=True,
            status="connected",
            detail="Blender and bpy available",
            version=version,
            diagnostics={"executable": str(exe), "python_api": api_detail},
        )

    async def execute(self, action: str, params: dict[str, Any], ctx: PluginContext) -> PluginResult:
        exe = first_existing(blender_candidates())
        ws = FileWorkspace(ctx.workspace_root, "blender", ctx.max_file_bytes)
        if action == "detect":
            probe = await self.probe(ctx)
            return PluginResult(success=probe.ok, output=probe.model_dump(), error=None if probe.ok else probe.detail)
        if action == "python_api":
            if not exe:
                raise PluginUnavailableError("Blender is not installed")
            code, out = run_version(
                str(exe),
                ["--background", "--python-expr", _PROBE_PY],
                min(ctx.timeout_seconds, 20),
            )
            ok = code == 0 and "NEXA_BLENDER_OK" in out
            return PluginResult(success=ok, output={"log": out}, error=None if ok else "bpy check failed")
        if action == "status":
            return PluginResult(success=True, output={"files": ws.list_tree(".")})
        if action == "create_scene":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("blender", "create_scene")
            if not exe:
                raise PluginUnavailableError("Blender is not installed")
            name = str(params.get("filename") or "nexa_scene.blend")
            if "/" in name or "\\" in name or ".." in name:
                raise PluginValidationError("filename must be a simple name")
            if not name.endswith(".blend"):
                name += ".blend"
            target = ws.root / name
            if target.exists() and not params.get("overwrite"):
                raise PluginConfirmationRequiredError("blender", "create_scene")
            script = ws.root / "_nexa_create_scene.py"
            script.write_text(_SCENE_PY, encoding="utf-8")
            code, out = run_version(
                str(exe),
                ["--background", "--python", str(script), "--", str(target)],
                min(ctx.timeout_seconds, 40),
            )
            ok = code == 0 and target.is_file()
            return PluginResult(
                success=ok,
                output={"path": name, "log": out[-1500:]},
                error=None if ok else "Blender did not write the scene",
            )
        raise PluginValidationError(f"Unknown action '{action}'")
