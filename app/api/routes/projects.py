"""Project manifests + desktop capability audit (Phase 3)."""
from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from app.config.settings import get_settings
from app.core.paths import resolve_under_project_root
from app.agent.project_manifest import ManifestStore, ProjectManifest
from app.tools.desktop.capabilities import DesktopCapabilityReport, audit_desktop_capabilities

router = APIRouter(prefix="/api/v1", tags=["projects"])
_Auth = Annotated[UserRecord | None, Depends(require_user_when_enforced)]


class ProjectManifestResponse(BaseModel):
    project: ProjectManifest


def _store() -> ManifestStore:
    root = resolve_under_project_root(get_settings().agent_workspace_dir) / "projects"
    return ManifestStore(root)


@router.get("/projects/{project_id}", response_model=ProjectManifestResponse)
async def get_project(project_id: str, user: _Auth = None) -> ProjectManifestResponse:
    uid = user.id if user else None
    man = _store().get(project_id, user_id=uid)
    if man is None:
        raise HTTPException(status_code=404, detail="Project not found or access denied.")
    return ProjectManifestResponse(project=man)


@router.get("/desktop/capabilities", response_model=DesktopCapabilityReport)
async def desktop_capabilities(_user: _Auth = None) -> DesktopCapabilityReport:
    """Honest inventory of local computer-control capabilities."""
    return audit_desktop_capabilities()
