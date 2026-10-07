"""Web research endpoint — runs the real ResearchTool (search → fetch → extract → sources)."""
from __future__ import annotations
import time
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from app.api.deps import get_nexa_core
from app.core.nexa_core import NexaCore
from app.gateway.models import TaskKind
from app.models.chat import ChatMessage, ChatRole
from app.models.errors import NexaError, ProviderConfigurationError
from app.tools.registry import get_default_tool_registry
from app.tools.base import ToolResult
router = APIRouter(prefix="/api/v1", tags=["research"])
class ResearchRequest(BaseModel):
    query: str = Field(..., description="What to search for on the web")
    max_results: int = Field(default=5, ge=1, le=20)
class ResearchSourceResponse(BaseModel):
    url: str
    title: str
    text: str
    content_hash: str
class ResearchResponse(BaseModel):
    query: str
    results: list[dict]
    sources: list[ResearchSourceResponse]
    skipped: list[str] = Field(default_factory=list)
@router.post("/research", response_model=ResearchResponse)
async def research(request: ResearchRequest) -> ResearchResponse:
    registry = get_default_tool_registry()
    tool = registry.get("web_research")
    result: ToolResult = await tool.execute(query=request.query, max_results=request.max_results)
    if not result.success:
        from app.models.errors import NexaError
        raise NexaError(result.error or "Research failed.")
    output = result.output
    return ResearchResponse(
        query=output["query"],
        results=output["results"],
        sources=[ResearchSourceResponse(**s) for s in output["sources"]],
        skipped=result.metadata.get("skipped", []),
    )
class ResearchChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="The user's research question.")
    max_results: int = Field(default=5, ge=1, le=20)
    model: str | None = Field(default=None, description="Optional model id or 'auto'.")
class ResearchChatResponse(BaseModel):
    """Research mode's answer: a live web search, synthesized with inline [n] citations."""
    message: str
    provider: str
    model: str
    display_name: str | None = None
    sources: list[ResearchSourceResponse]
    latency_ms: float
_RESEARCH_SYSTEM_PROMPT = (
    "You just ran a live web search for the user's question. The numbered sources below are "
    "the only information you may use to answer - do not rely on prior knowledge instead of them. "
    "Cite every claim inline as [1], [2], etc., matching the source numbers. If the sources don't "
    "answer the question, say so plainly rather than guessing. "
    "Distinguish FACT (from sources) vs ASSUMPTION/HYPOTHESIS/UNCERTAINTY — never invent sources."
)
def _build_context(sources: list[ResearchSourceResponse]) -> str:
    if not sources:
        return "No web results were found for this query."
    return "\n\n".join(f"[{i}] {s.title} ({s.url})\n{s.text}" for i, s in enumerate(sources, start=1))
@router.post("/research/chat", response_model=ResearchChatResponse)
async def research_chat(
    request: ResearchChatRequest, core: NexaCore = Depends(get_nexa_core)
) -> ResearchChatResponse:
    """Research mode: search the web, then ask the model to answer *from those
    sources only*, with numbered citations the frontend can render as links."""
    if core.gateway is None:
        raise ProviderConfigurationError("Model gateway is not available.")
    registry = get_default_tool_registry()
    tool = registry.get("web_research")
    result: ToolResult = await tool.execute(query=request.message, max_results=request.max_results)
    if not result.success:
        raise NexaError(result.error or "Research failed.")
    sources = [ResearchSourceResponse(**s) for s in result.output["sources"]]
    system = f"{_RESEARCH_SYSTEM_PROMPT}\n\n{_build_context(sources)}"
    try:
        from app.knowledge_core.composer import KnowledgeCoreComposer

        core = KnowledgeCoreComposer().compose(request.message, task="research")
        if core.text:
            system = f"{system}\n\n{core.text}"
    except Exception:  # noqa: BLE001
        pass
    messages = [
        ChatMessage(role=ChatRole.SYSTEM, content=system),
        ChatMessage(role=ChatRole.USER, content=request.message),
    ]
    start = time.perf_counter()
    gw_result = await core.gateway.chat(messages, model=request.model, task_kind=TaskKind.RESEARCH)
    elapsed_ms = (time.perf_counter() - start) * 1000
    return ResearchChatResponse(
        message=gw_result.text,
        provider=gw_result.provider,
        model=gw_result.model_id,
        display_name=gw_result.display_name,
        sources=sources,
        latency_ms=round(elapsed_ms, 2),
    )
