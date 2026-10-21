"""GitHub official REST API adapter (minimal scopes)."""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

import httpx

from app.core.secrets import redact_secrets
from app.plugins.base import PluginAdapter, PluginContext
from app.plugins.errors import PluginConfirmationRequiredError, PluginUnavailableError, PluginValidationError
from app.plugins.models import PluginActionSpec, PluginManifest, PluginResult, ProbeResult

_API = "https://api.github.com"
_ALLOWED_HOSTS = frozenset({"api.github.com"})
_REPO_SEGMENT = re.compile(r"^[A-Za-z0-9._-]+$")


def _safe_github_url(url: str) -> str:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or host not in _ALLOWED_HOSTS:
        raise PluginValidationError("Only https://api.github.com URLs are allowed.")
    return url


def _safe_owner_repo(owner: str, repo: str) -> tuple[str, str]:
    if (
        not _REPO_SEGMENT.fullmatch(owner)
        or not _REPO_SEGMENT.fullmatch(repo)
        or owner in {".", ".."}
        or repo in {".", ".."}
    ):
        raise PluginValidationError("owner and repo must be simple GitHub name segments.")
    return owner, repo


class GitHubAdapter(PluginAdapter):
    manifest = PluginManifest(
        id="github",
        version="1.0.0",
        name="GitHub",
        description="List repositories, read issues/PRs and status. Create issues only with write permission and confirmation. Uses the official GitHub API.",
        category="git",
        integration_type="api",
        dependencies=["GitHub personal access token (repo read; public_repo or issues write if creating issues)"],
        required_permissions=["github.read"],
        optional_permissions=["github.write"],
        actions=[
            PluginActionSpec(name="whoami", description="Verify token against GET /user", permissions=["github.read"]),
            PluginActionSpec(name="list_repos", description="List accessible repositories", permissions=["github.read"]),
            PluginActionSpec(
                name="repo_status",
                description="Repository metadata",
                permissions=["github.read"],
                input_schema={"owner": {"type": "string"}, "repo": {"type": "string"}},
            ),
            PluginActionSpec(
                name="list_issues",
                description="List issues",
                permissions=["github.read"],
                input_schema={"owner": {"type": "string"}, "repo": {"type": "string"}},
            ),
            PluginActionSpec(
                name="list_pulls",
                description="List pull requests",
                permissions=["github.read"],
                input_schema={"owner": {"type": "string"}, "repo": {"type": "string"}},
            ),
            PluginActionSpec(
                name="create_issue",
                description="Create an issue (write + confirm)",
                permissions=["github.write"],
                dangerous=True,
                input_schema={
                    "owner": {"type": "string"},
                    "repo": {"type": "string"},
                    "title": {"type": "string"},
                    "body": {"type": "string"},
                },
            ),
        ],
        install_hint="Create a fine-grained PAT with Contents: Read and Issues: Read (Issues: Write only if you create issues). Paste it in Plugin Hub — it is stored encrypted, never logged.",
    )

    async def probe(self, ctx: PluginContext) -> ProbeResult:
        token = (ctx.secrets.get("token") or "").strip()
        if not token:
            return ProbeResult(
                ok=False,
                status="needs_token",
                detail="GitHub token is not configured",
            )
        try:
            data = await self._get(ctx, "/user")
        except Exception as exc:  # noqa: BLE001
            return ProbeResult(
                ok=False,
                status="error",
                detail=redact_secrets(str(exc)),
            )
        login = data.get("login") if isinstance(data, dict) else None
        return ProbeResult(
            ok=True,
            status="connected",
            detail=f"Authenticated as {login}" if login else "Token accepted",
            version=str(login) if login else None,
            diagnostics={"login": login},
        )

    async def execute(self, action: str, params: dict[str, Any], ctx: PluginContext) -> PluginResult:
        if action == "whoami":
            data = await self._get(ctx, "/user")
            return PluginResult(success=True, output={"login": data.get("login"), "id": data.get("id")})
        if action == "list_repos":
            data = await self._get(ctx, "/user/repos?per_page=30&sort=updated")
            repos = [
                {
                    "full_name": r.get("full_name"),
                    "private": r.get("private"),
                    "default_branch": r.get("default_branch"),
                    "open_issues": r.get("open_issues_count"),
                }
                for r in (data if isinstance(data, list) else [])
            ]
            return PluginResult(success=True, output={"repos": repos})
        owner = str(params.get("owner") or "")
        repo = str(params.get("repo") or "")
        if action in {"repo_status", "list_issues", "list_pulls", "create_issue"}:
            if not owner or not repo:
                raise PluginValidationError("owner and repo are required")
            owner, repo = _safe_owner_repo(owner, repo)
        if action == "repo_status":
            data = await self._get(ctx, f"/repos/{owner}/{repo}")
            return PluginResult(
                success=True,
                output={
                    "full_name": data.get("full_name"),
                    "default_branch": data.get("default_branch"),
                    "open_issues": data.get("open_issues_count"),
                    "visibility": data.get("visibility") or ("private" if data.get("private") else "public"),
                    "pushed_at": data.get("pushed_at"),
                },
            )
        if action == "list_issues":
            data = await self._get(ctx, f"/repos/{owner}/{repo}/issues?state=open&per_page=20")
            issues = [
                {"number": i.get("number"), "title": i.get("title"), "state": i.get("state")}
                for i in (data if isinstance(data, list) else [])
                if "pull_request" not in i
            ]
            return PluginResult(success=True, output={"issues": issues})
        if action == "list_pulls":
            data = await self._get(ctx, f"/repos/{owner}/{repo}/pulls?state=open&per_page=20")
            pulls = [
                {"number": p.get("number"), "title": p.get("title"), "state": p.get("state")}
                for p in (data if isinstance(data, list) else [])
            ]
            return PluginResult(success=True, output={"pulls": pulls})
        if action == "create_issue":
            if not ctx.confirm:
                raise PluginConfirmationRequiredError("github", "create_issue")
            title = str(params.get("title") or "").strip()
            if not title:
                raise PluginValidationError("title is required")
            body = str(params.get("body") or "")
            data = await self._post(
                ctx,
                f"/repos/{owner}/{repo}/issues",
                {"title": title, "body": body},
            )
            return PluginResult(
                success=True,
                output={"number": data.get("number"), "html_url": data.get("html_url")},
            )
        raise PluginValidationError(f"Unknown action '{action}'")

    async def _headers(self, ctx: PluginContext) -> dict[str, str]:
        token = (ctx.secrets.get("token") or "").strip()
        if not token:
            raise PluginUnavailableError("GitHub token is not configured")
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "NEXA-PluginHub",
        }

    async def _get(self, ctx: PluginContext, path: str) -> Any:
        url = _safe_github_url(_API + path)
        headers = await self._headers(ctx)
        timeout = httpx.Timeout(ctx.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.get(url, headers=headers)
        if response.status_code >= 400:
            raise PluginUnavailableError(f"GitHub API {response.status_code}")
        return response.json()

    async def _post(self, ctx: PluginContext, path: str, payload: dict[str, Any]) -> Any:
        url = _safe_github_url(_API + path)
        headers = await self._headers(ctx)
        timeout = httpx.Timeout(ctx.timeout_seconds)
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
            response = await client.post(url, headers=headers, json=payload)
        if response.status_code >= 400:
            raise PluginUnavailableError(f"GitHub API {response.status_code}")
        return response.json()
