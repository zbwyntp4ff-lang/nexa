"""Chat endpoint - the main entry point into NEXA Core."""
from __future__ import annotations
from collections.abc import AsyncIterator
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from app.api.deps import get_nexa_core
from app.core.nexa_core import NexaCore
from app.gateway.models import StreamEvent
from app.models.chat import ChatRequest, ChatResponse
from app.models.errors import NexaError
router = APIRouter(prefix="/api/v1", tags=["chat"])
@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: ChatRequest, core: NexaCore = Depends(get_nexa_core)
) -> ChatResponse:
    return await core.chat(request)
@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest, core: NexaCore = Depends(get_nexa_core)
) -> StreamingResponse:
    """Server-sent events. Each event is a JSON object (meta, delta, or done).

    Validation and model work run inside the generator so the HTTP response
    can start immediately (important for early TTFT).
    """
    async def events() -> AsyncIterator[str]:
        try:
            async for event in core.stream_events(request):
                yield f"data: {event.model_dump_json()}\n\n"
        except NexaError as exc:
            code = getattr(exc, "code", None) or exc.__class__.__name__
            payload = StreamEvent(type="error", error=str(code), message=exc.message)
            yield f"data: {payload.model_dump_json()}\n\n"
    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
