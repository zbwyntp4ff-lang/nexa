"""Plugin Manager — connect/probe/invoke with deny-by-default permissions."""
from __future__ import annotations

import asyncio
import hashlib
import shutil
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.config.settings import get_settings
from app.core.logging_config import get_logger
from app.core.paths import resolve_under_project_root
from app.core.secrets import redact_secrets
from app.models.errors import PathTraversalError, ToolNotFoundError
from app.plugins.adapters.blender import BlenderAdapter
from app.plugins.adapters.github import GitHubAdapter
from app.plugins.adapters.godot import GodotAdapter
from app.plugins.adapters.playwright_adapter import PlaywrightAdapter
from app.plugins.adapters.vscode import VsCodeAdapter
from app.plugins.audit import PluginAuditLog
from app.plugins.base import PluginAdapter, PluginContext
from app.plugins.crypto import decrypt_secret, encrypt_secret, load_or_create_master_key
from app.plugins.errors import (
    PluginConfirmationRequiredError,
    PluginNotConnectedError,
    PluginNotFoundError,
    PluginPermissionDeniedError,
    PluginTimeoutError,
    PluginValidationError,
)
from app.plugins.models import PluginManifest, PluginResult, PluginState, ProbeResult
from app.plugins.store import PluginStore
from app.plugins.tools import PluginDispatchTool
from app.tools.registry import ToolRegistry, get_default_tool_registry

logger = get_logger("nexa.plugins")

_ADAPTERS: tuple[type[PluginAdapter], ...] = (
    VsCodeAdapter,
    GitHubAdapter,
    PlaywrightAdapter,
    BlenderAdapter,
    GodotAdapter,
)


class PluginManager:
    def __init__(
        self,
        *,
        store: PluginStore,
        workspace_root: Path,
        master_key: bytes,
        registry: ToolRegistry,
        timeout_seconds: float = 20.0,
        max_file_bytes: int = 1_000_000,
    ) -> None:
        self._store = store
        self._workspace_root = workspace_root
        self._workspace_root.mkdir(parents=True, exist_ok=True)
        self._master_key = master_key
        self._registry = registry
        self._timeout = timeout_seconds
        self._max_file_bytes = max_file_bytes
        self._audit = PluginAuditLog()
        self._adapters: dict[str, PluginAdapter] = {cls().manifest.id: cls() for cls in _ADAPTERS}

    def adapter(self, plugin_id: str) -> PluginAdapter:
        try:
            return self._adapters[plugin_id]
        except KeyError as exc:
            raise PluginNotFoundError(plugin_id) from exc

    def manifests(self) -> list[PluginManifest]:
        return [a.manifest for a in self._adapters.values()]

    def public_card(self, plugin_id: str, *, user_id: str | None = None) -> dict[str, Any]:
        manifest = self.adapter(plugin_id).manifest
        state = self._store.get(plugin_id, user_id=user_id) or PluginState(
            plugin_id=plugin_id, user_id=user_id
        )
        return {
            "id": manifest.id,
            "version": manifest.version,
            "name": manifest.name,
            "description": manifest.description,
            "category": manifest.category,
            "integration_type": manifest.integration_type,
            "dependencies": list(manifest.dependencies),
            "required_permissions": list(manifest.required_permissions),
            "optional_permissions": list(manifest.optional_permissions),
            "timeout_seconds": manifest.timeout_seconds,
            "actions": [a.model_dump() for a in manifest.actions],
            "install_hint": manifest.install_hint,
            "status": state.status,
            "enabled": state.enabled,
            "granted_permissions": list(state.granted_permissions),
            "settings": {k: v for k, v in state.settings.items() if k != "token"},
            "has_token": bool(state.secrets.get("token")),
            "last_error": state.last_error,
            "last_probe": state.last_probe,
            "connected_at": state.connected_at,
        }

    def list_public(
        self, *, query: str = "", category: str = "", user_id: str | None = None
    ) -> list[dict[str, Any]]:
        q = query.strip().lower()
        cards = [self.public_card(pid, user_id=user_id) for pid in self._adapters]
        if category:
            cards = [c for c in cards if c["category"] == category]
        if q:
            cards = [
                c
                for c in cards
                if q in c["name"].lower()
                or q in c["description"].lower()
                or q in c["id"].lower()
                or q in c["category"].lower()
            ]
        return cards

    def audit(
        self,
        plugin_id: str | None = None,
        limit: int = 50,
        *,
        user_id: str | None = None,
    ) -> list[dict[str, Any]]:
        items = self._audit.for_plugin(plugin_id, limit) if plugin_id else self._audit.all(limit)
        if user_id is not None:
            items = [e for e in items if e.user_id == user_id]
        return [e.model_dump() for e in items]

    def delete_user_data(self, user_id: str) -> int:
        """Disconnect and wipe all plugin connections for ``user_id``."""
        # User-scoped plugin tools are never registered globally, so deleting
        # one user's connection must not unregister another user's capability.
        removed = self._store.delete_user(user_id)
        candidate = self._workspace_root / hashlib.sha256(user_id.encode("utf-8")).hexdigest()
        if candidate.is_symlink():
            candidate.unlink()
        elif candidate.exists():
            root = self._workspace_root.resolve()
            resolved = candidate.resolve()
            if resolved != root and root in resolved.parents:
                shutil.rmtree(resolved)
        return removed

    async def connect(
        self,
        plugin_id: str,
        *,
        user_id: str | None = None,
        permissions: list[str] | None = None,
        settings: dict[str, Any] | None = None,
        secrets: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        adapter = self.adapter(plugin_id)
        allowed = set(adapter.manifest.required_permissions) | set(adapter.manifest.optional_permissions)
        requested = list(permissions) if permissions is not None else list(adapter.manifest.required_permissions)
        unknown = [p for p in requested if p not in allowed]
        if unknown:
            raise PluginValidationError(f"Unknown permissions: {', '.join(unknown)}")
        # deny-by-default: never auto-grant optional write/launch/submit
        granted = [p for p in requested if p in allowed]
        existing = self._store.get(plugin_id, user_id=user_id) or PluginState(
            plugin_id=plugin_id, user_id=user_id
        )
        encrypted = dict(existing.secrets)
        if secrets:
            for key, value in secrets.items():
                if value:
                    encrypted[key] = encrypt_secret(value, self._master_key)
        ctx = self._context(adapter, PluginState(
            plugin_id=plugin_id,
            user_id=user_id,
            granted_permissions=granted,
            settings=settings or existing.settings,
            secrets=encrypted,
        ))
        probe = await adapter.probe(ctx)
        now = datetime.now(timezone.utc).isoformat()
        connected = probe.ok and probe.status in {"connected", "connected_limited"}
        state = PluginState(
            plugin_id=plugin_id,
            user_id=user_id,
            enabled=connected,
            status=probe.status if connected else probe.status,
            granted_permissions=granted if connected else [],
            settings=settings or existing.settings,
            secrets=encrypted if connected else {},
            last_error=None if connected else (probe.detail or probe.limitation),
            last_probe=now,
            connected_at=now if connected else None,
        )
        if not connected:
            # Do not persist secrets if probe failed
            state.secrets = {}
            if user_id is None:
                self._unregister_tool(plugin_id)
            self._store.upsert(state)
            self._audit.record(plugin_id=plugin_id, action="connect", status="failed", user_id=user_id, detail=probe.detail)
            logger.info("plugin connect failed id=%s status=%s", plugin_id, probe.status)
            return self.public_card(plugin_id, user_id=user_id)
        self._store.upsert(state)
        if user_id is None:
            self._register_tool(plugin_id)
        self._audit.record(plugin_id=plugin_id, action="connect", status="ok", user_id=user_id, detail=probe.detail)
        logger.info("plugin connected id=%s status=%s user=%s", plugin_id, probe.status, user_id or "-")
        return self.public_card(plugin_id, user_id=user_id)

    async def disconnect(self, plugin_id: str, *, user_id: str | None = None) -> dict[str, Any]:
        self.adapter(plugin_id)
        if user_id is None:
            self._unregister_tool(plugin_id)
        self._store.upsert(
            PluginState(
                plugin_id=plugin_id,
                user_id=user_id,
                enabled=False,
                status="disconnected",
            )
        )
        self._audit.record(plugin_id=plugin_id, action="disconnect", status="ok", user_id=user_id)
        logger.info("plugin disconnected id=%s user=%s", plugin_id, user_id or "-")
        return self.public_card(plugin_id, user_id=user_id)

    async def diagnose(self, plugin_id: str, *, user_id: str | None = None) -> ProbeResult:
        adapter = self.adapter(plugin_id)
        state = self._store.get(plugin_id, user_id=user_id) or PluginState(
            plugin_id=plugin_id, user_id=user_id
        )
        ctx = self._context(adapter, state)
        probe = await adapter.probe(ctx)
        state.last_probe = datetime.now(timezone.utc).isoformat()
        state.last_error = None if probe.ok else probe.detail
        if state.enabled and not probe.ok:
            state.enabled = False
            state.status = probe.status
            state.connected_at = None
            if user_id is None:
                self._unregister_tool(plugin_id)
        elif state.enabled:
            state.status = probe.status
        self._store.upsert(state)
        self._audit.record(plugin_id=plugin_id, action="diagnose", status="ok" if probe.ok else "failed", user_id=user_id, detail=probe.detail)
        return probe

    async def set_permissions(
        self, plugin_id: str, permissions: list[str], *, user_id: str | None = None
    ) -> dict[str, Any]:
        adapter = self.adapter(plugin_id)
        state = self._store.get(plugin_id, user_id=user_id)
        if not state or not state.enabled:
            raise PluginNotConnectedError(plugin_id)
        allowed = set(adapter.manifest.required_permissions) | set(adapter.manifest.optional_permissions)
        unknown = [p for p in permissions if p not in allowed]
        if unknown:
            raise PluginValidationError(f"Unknown permissions: {', '.join(unknown)}")
        state.granted_permissions = [p for p in permissions if p in allowed]
        self._store.upsert(state)
        self._audit.record(plugin_id=plugin_id, action="permissions", status="ok", user_id=user_id, detail=",".join(state.granted_permissions))
        return self.public_card(plugin_id, user_id=user_id)

    async def invoke(
        self,
        plugin_id: str,
        action: str,
        params: dict[str, Any] | None = None,
        *,
        confirm: bool = False,
        user_id: str | None = None,
    ) -> PluginResult:
        adapter = self.adapter(plugin_id)
        state = self._store.get(plugin_id, user_id=user_id)
        if not state or not state.enabled:
            raise PluginNotConnectedError(plugin_id)
        spec = next((a for a in adapter.manifest.actions if a.name == action), None)
        if spec is None:
            raise PluginValidationError(f"Unknown action '{action}'")
        granted = frozenset(state.granted_permissions)
        missing = [p for p in spec.permissions if p not in granted]
        if missing:
            raise PluginPermissionDeniedError(plugin_id, missing[0])
        if spec.dangerous and not confirm:
            raise PluginConfirmationRequiredError(plugin_id, action)
        ctx = self._context(adapter, state, confirm=confirm)
        timeout = min(adapter.manifest.timeout_seconds, self._timeout)
        try:
            result = await asyncio.wait_for(
                adapter.execute(action, params or {}, ctx),
                timeout=timeout,
            )
        except PluginConfirmationRequiredError:
            raise
        except TimeoutError as exc:
            self._audit.record(plugin_id=plugin_id, action=action, status="timeout", user_id=user_id)
            raise PluginTimeoutError(f"Plugin '{plugin_id}' action '{action}' timed out") from exc
        except PathTraversalError:
            self._audit.record(plugin_id=plugin_id, action=action, status="denied", user_id=user_id, detail="path traversal")
            raise
        except Exception as exc:  # noqa: BLE001
            msg = redact_secrets(str(exc))
            logger.warning("plugin invoke failed id=%s action=%s err=%s", plugin_id, action, msg)
            self._audit.record(plugin_id=plugin_id, action=action, status="error", user_id=user_id, detail=msg)
            raise
        status = "ok" if result.success else "error"
        self._audit.record(plugin_id=plugin_id, action=action, status=status, user_id=user_id, detail=result.error or "")
        logger.info("plugin invoke id=%s action=%s success=%s", plugin_id, action, result.success)
        return result

    def restore_connected_tools(self) -> None:
        # The shared agent registry has no per-request user context. Only
        # explicitly system-scoped connections may be exposed as global tools.
        for state in self._store.all(user_id=None):
            if state.enabled and state.plugin_id in self._adapters:
                self._register_tool(state.plugin_id)

    def _context(self, adapter: PluginAdapter, state: PluginState, confirm: bool = False) -> PluginContext:
        decrypted: dict[str, str] = {}
        for key, blob in state.secrets.items():
            try:
                decrypted[key] = decrypt_secret(blob, self._master_key)
            except ValueError:
                logger.warning("plugin secret decrypt failed id=%s key=%s", state.plugin_id, key)
        return PluginContext(
            # Each account receives a distinct filesystem namespace. Hash the
            # internal user id so it can never become a path component.
            workspace_root=self._workspace_root / (
                "system" if state.user_id is None
                else hashlib.sha256(state.user_id.encode("utf-8")).hexdigest()
            ),
            granted_permissions=frozenset(state.granted_permissions),
            settings=dict(state.settings),
            secrets=decrypted,
            timeout_seconds=min(adapter.manifest.timeout_seconds, self._timeout),
            confirm=confirm,
            max_file_bytes=self._max_file_bytes,
        )

    def _register_tool(self, plugin_id: str) -> None:
        name = f"plugin_{plugin_id}"
        try:
            self._registry.get(name)
        except ToolNotFoundError:
            self._registry.register(PluginDispatchTool(self, plugin_id))
            return
        # already registered — leave in place

    def _unregister_tool(self, plugin_id: str) -> None:
        name = f"plugin_{plugin_id}"
        try:
            self._registry.unregister(name)
        except ToolNotFoundError:
            return


@lru_cache
def get_plugin_manager() -> PluginManager:
    settings = get_settings()
    workspace = resolve_under_project_root(
        getattr(settings, "plugin_workspace_dir", "agent_workspace/plugins")
    )
    store_path = resolve_under_project_root(
        getattr(settings, "plugin_store_path", "data/plugin_store.json")
    )
    key_path = getattr(settings, "plugin_key_path", "data/plugin.key")
    manager = PluginManager(
        store=PluginStore(store_path),
        workspace_root=workspace,
        master_key=load_or_create_master_key(key_path),
        registry=get_default_tool_registry(),
        timeout_seconds=float(getattr(settings, "plugin_timeout_seconds", 20.0)),
        max_file_bytes=int(getattr(settings, "plugin_max_file_bytes", 1_000_000)),
    )
    manager.restore_connected_tools()
    return manager
