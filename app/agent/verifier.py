"""The Verifier - double-checks that a completed step actually achieved its goal.
For most tool calls, "the tool reported success" is sufficient. For
side-effecting calls like ``file_write``, the Verifier goes further and
reads the file back to confirm its content matches what was requested,
catching silent filesystem inconsistencies before the agent moves on.

Phase 3 also verifies office artifacts (openable files + download URLs) and
research outputs (real sources/results).
"""
from __future__ import annotations
from app.agent.artifact_verify import ArtifactVerifier
from app.agent.models import AgentStep
from app.core.logging_config import get_logger
from app.tools.registry import ToolRegistry
logger = get_logger("nexa.agent.verifier")
class Verifier:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
        self._artifacts = ArtifactVerifier(registry)
        self.last_detail: str = ""
    async def verify_step(self, step: AgentStep) -> bool:
        """Return ``True`` if ``step`` is verified as having achieved its goal."""
        if step.dry_run:
            self.last_detail = "dry_run"
            return True
        if not step.success:
            self.last_detail = step.error or "tool reported failure"
            return False
        if step.tool_name == "file_write":
            ok = await self._verify_file_write(step)
            self.last_detail = "file_write content match" if ok else "file_write mismatch"
            return ok
        if step.tool_name in ArtifactVerifier.OFFICE_TOOLS or step.tool_name == "web_research":
            ok, detail = await self._artifacts.verify(step)
            self.last_detail = detail
            if not ok:
                logger.warning(
                    "artifact verification failed tool=%s detail=%s",
                    step.tool_name,
                    detail,
                )
            return ok
        self.last_detail = "ok"
        return True
    async def _verify_file_write(self, step: AgentStep) -> bool:
        path = step.tool_input.get("path")
        expected_content = step.tool_input.get("content")
        if not path:
            return False
        try:
            read_result = await self._registry.execute("file_read", path=path)
        except Exception:  # noqa: BLE001 - verification failure, not a crash
            logger.warning("verification read failed for file_write path=%s", path)
            return False
        if not read_result.success:
            return False
        return read_result.output == expected_content
