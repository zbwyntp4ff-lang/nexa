"""``ToolRegistry`` - registers and executes :class:`app.tools.base.Tool` instances."""
from __future__ import annotations
from functools import lru_cache
from app.config.settings import get_settings
from app.core.logging_config import get_logger
from app.core.paths import resolve_under_project_root
from app.models.errors import ToolAlreadyRegisteredError, ToolExecutionError, ToolNotFoundError
from app.tools.base import Tool, ToolResult
from app.tools.calculator import CalculatorTool
from app.tools.current_time import CurrentTimeTool
from app.tools.directory_list import DirectoryListTool
from app.tools.file_read import FileReadTool
from app.tools.file_write import FileWriteTool
from app.tools.math_solver import MathSolverTool
from app.web.page_fetcher import PageFetcher
from app.web.search_provider import SearchProviderFactory
logger = get_logger("nexa.tools")
class ToolRegistry:
    """A simple in-process registry of available tools."""
    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
    def register(self, tool: Tool) -> None:
        """Register ``tool``.
        Raises:
            app.models.errors.ToolAlreadyRegisteredError: If a tool with the
                same name is already registered.
        """
        if tool.name in self._tools:
            raise ToolAlreadyRegisteredError(tool.name)
        self._tools[tool.name] = tool
    def unregister(self, name: str) -> None:
        """Remove a tool by name.
        Raises:
            app.models.errors.ToolNotFoundError: If no such tool is registered.
        """
        if name not in self._tools:
            raise ToolNotFoundError(name, available=tuple(self._tools))
        del self._tools[name]
    def get(self, name: str) -> Tool:
        """Return the registered tool named ``name``.
        Raises:
            app.models.errors.ToolNotFoundError: If no such tool is registered.
        """
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ToolNotFoundError(name, available=tuple(self._tools)) from exc
    def list(self) -> list[Tool]:
        """Return all registered tools."""
        return list(self._tools.values())
    async def execute(self, name: str, **kwargs) -> ToolResult:
        """Look up and run the tool named ``name`` with ``kwargs``.
        Unlike a raw ``Tool.execute()`` call, unexpected exceptions raised by
        the tool are caught and normalized into
        :class:`app.models.errors.ToolExecutionError` instead of propagating
        a raw traceback.
        Raises:
            app.models.errors.ToolNotFoundError: If no such tool is registered.
            app.models.errors.ToolExecutionError: If the tool raises an
                unexpected exception while running.
        """
        tool = self.get(name)
        try:
            result = await tool.execute(**kwargs)
        except Exception as exc:  # noqa: BLE001 - normalize all tool crashes
            logger.error("tool '%s' raised an unexpected exception: %s", name, exc.__class__.__name__)
            raise ToolExecutionError(f"Tool '{name}' failed: {exc}") from exc
        logger.info("tool '%s' executed success=%s", name, result.success)
        return result
def build_default_registry() -> ToolRegistry:
    """Construct a fresh registry with all built-in NEXA tools registered."""
    settings = get_settings()
    sandbox_root = resolve_under_project_root(settings.agent_workspace_dir)
    sandbox_root.mkdir(parents=True, exist_ok=True)
    registry = ToolRegistry()
    registry.register(CalculatorTool())
    registry.register(MathSolverTool())
    registry.register(CurrentTimeTool())
    registry.register(FileReadTool(sandbox_root, max_bytes=settings.max_file_read_bytes))
    registry.register(FileWriteTool(sandbox_root))
    registry.register(DirectoryListTool(sandbox_root))
    # Desktop Agent tools (Part 6B): safe file/dir operations within sandbox.
    from app.tools.file_create import FileCreateTool
    from app.tools.file_rename import FileRenameTool
    from app.tools.directory_create import DirectoryCreateTool
    registry.register(FileCreateTool(sandbox_root))
    registry.register(FileRenameTool(sandbox_root))
    registry.register(DirectoryCreateTool(sandbox_root))
    # Office generation + analysis (Phase 2): PPTX / DOCX / XLSX / PDF.
    from app.tools.office import (
        DocumentTool,
        FileAnalysisTool,
        PDFTool,
        PresentationTool,
        SpreadsheetTool,
    )
    from app.tools.office.result_store import ResultStore

    result_store = ResultStore(sandbox_root)
    registry.register(PresentationTool(result_store))
    registry.register(DocumentTool(result_store))
    registry.register(SpreadsheetTool(result_store))
    registry.register(PDFTool(result_store))
    registry.register(FileAnalysisTool(sandbox_root))
    # Phase 4 — browser + allowlisted local files + open result (local desktop gated).
    from app.tools.desktop import BrowserTool, LocalFileTool, OpenResultTool

    registry.register(BrowserTool(sandbox_root))
    registry.register(LocalFileTool(sandbox_root))
    registry.register(OpenResultTool(sandbox_root, store=result_store))
    # Expose store for download API (same sandbox as tools).
    registry._result_store = result_store  # type: ignore[attr-defined]
    # Register the web research tool with a real search provider (Part 6A).
    from app.web.research_tool import ResearchTool
    search_provider = SearchProviderFactory.create(
        settings.web_search_provider,
        api_url=settings.search_api_url,
        api_key=settings.search_api_key,
        timeout_seconds=settings.web_fetch_timeout_seconds,
    )
    page_fetcher = PageFetcher(
        timeout_seconds=settings.web_fetch_timeout_seconds,
        max_page_size_bytes=settings.web_max_page_size_bytes,
        max_redirects=settings.web_max_redirects,
    )
    registry.register(
        ResearchTool(
            search_provider=search_provider,
            page_fetcher=page_fetcher,
            default_max_results=settings.web_max_search_results,
        )
    )
    return registry
@lru_cache
def get_default_tool_registry() -> ToolRegistry:
    """Return a process-wide cached default :class:`ToolRegistry`.
    Tests that need isolation should call
    ``get_default_tool_registry.cache_clear()`` or construct a
    ``ToolRegistry`` directly.
    """
    return build_default_registry()
