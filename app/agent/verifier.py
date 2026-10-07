"""The Verifier - double-checks that a completed step actually achieved its goal.
For most tool calls, "the tool reported success" is sufficient. For
side-effecting calls like ``file_write``, the Verifier goes further and
reads the file back to confirm its content matches what was requested,
catching silent filesystem inconsistencies before the agent moves on.
"""
from __future__ import annotations
from app.agent.models import AgentStep
from app.core.logging_config import get_logger
from app.tools.registry import ToolRegistry
logger = get_logger("nexa.agent.verifier")
class Verifier:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry
    async def verify_step(self, step: AgentStep) -> bool:
        """Return ``True`` if ``step`` is verified as having achieved its goal."""
        if step.dry_run:
            return True
        if not step.success:
            return False
        if step.tool_name == "file_write":
            return await self._verify_file_write(step)
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
