"""Plugin Hub API — catalog, connect, diagnose, invoke (per-user connections)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query

from app.api.deps import get_plugin_manager_dep
from app.api.security_deps import require_user
from app.auth.models import UserRecord
from app.models.plugins_api import PluginConnectRequest, PluginInvokeRequest, PluginPermissionsRequest
from app.plugins.manager import PluginManager

router = APIRouter(prefix="/api/v1/plugins", tags=["plugins"])


@router.get("/")
async def list_plugins(
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
    q: str = Query(default=""),
    category: str = Query(default=""),
) -> dict[str, Any]:
    items = manager.list_public(query=q, category=category, user_id=user.id)
    return {"plugins": items, "count": len(items)}


@router.get("/{plugin_id}")
async def get_plugin(
    plugin_id: str,
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
) -> dict[str, Any]:
    return manager.public_card(plugin_id, user_id=user.id)


@router.post("/{plugin_id}/connect")
async def connect_plugin(
    plugin_id: str,
    body: PluginConnectRequest,
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
) -> dict[str, Any]:
    secrets = {}
    if body.token:
        secrets["token"] = body.token
    return await manager.connect(
        plugin_id,
        user_id=user.id,
        permissions=body.permissions,
        settings=body.settings,
        secrets=secrets or None,
    )


@router.post("/{plugin_id}/disconnect")
async def disconnect_plugin(
    plugin_id: str,
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
) -> dict[str, Any]:
    return await manager.disconnect(plugin_id, user_id=user.id)


@router.post("/{plugin_id}/diagnose")
async def diagnose_plugin(
    plugin_id: str,
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
) -> dict[str, Any]:
    probe = await manager.diagnose(plugin_id, user_id=user.id)
    return {"plugin_id": plugin_id, "probe": probe.model_dump()}


@router.post("/{plugin_id}/invoke")
async def invoke_plugin(
    plugin_id: str,
    body: PluginInvokeRequest,
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
) -> dict[str, Any]:
    result = await manager.invoke(
        plugin_id,
        body.action,
        body.params,
        confirm=body.confirm,
        user_id=user.id,
    )
    return {"plugin_id": plugin_id, "result": result.model_dump()}


@router.patch("/{plugin_id}/permissions")
async def patch_permissions(
    plugin_id: str,
    body: PluginPermissionsRequest,
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
) -> dict[str, Any]:
    return await manager.set_permissions(plugin_id, body.permissions, user_id=user.id)


@router.get("/{plugin_id}/audit")
async def plugin_audit(
    plugin_id: str,
    manager: Annotated[PluginManager, Depends(get_plugin_manager_dep)],
    user: Annotated[UserRecord, Depends(require_user)],
    limit: int = Query(default=50, ge=1, le=200),
) -> dict[str, Any]:
    return {"events": manager.audit(plugin_id, limit=limit, user_id=user.id)}
