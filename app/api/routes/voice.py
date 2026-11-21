"""Voice endpoints (Part 8 architecture points only).
STT/TTS providers are still interfaces (Part 3 scope) - no real backend is
implemented. These endpoints are honest about that: ``/status`` reports
unconfigured, and transcribe/synthesize return a normal 503
``ProviderConfigurationError`` rather than faking a result. Wiring a real
provider later only requires changing
:mod:`app.voice.factory` - these endpoints do not need to change.
"""
from __future__ import annotations
from fastapi import APIRouter, Depends, UploadFile
from pydantic import BaseModel, Field
from app.config.settings import Settings, get_settings
from app.api.security_deps import require_user_when_enforced
from app.auth.models import UserRecord
from typing import Annotated
from app.voice.factory import SpeechToTextProviderFactory, TextToSpeechProviderFactory
router = APIRouter(prefix="/api/v1/voice", tags=["voice"])
class SynthesizeRequest(BaseModel):
    text: str = Field(..., min_length=1)
    voice: str | None = None
@router.get("/status")
async def voice_status(settings: Settings = Depends(get_settings)) -> dict:
    stt = SpeechToTextProviderFactory.create(settings)
    tts = TextToSpeechProviderFactory.create(settings)
    return {
        "stt_configured": await stt.health_check(),
        "tts_configured": await tts.health_check(),
    }
@router.post("/transcribe")
async def transcribe(
    file: UploadFile,
    settings: Settings = Depends(get_settings),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> dict:
    provider = SpeechToTextProviderFactory.create(settings)
    raw = await file.read()
    result = await provider.transcribe(raw, file.content_type or "audio/webm")
    return result.model_dump()
@router.post("/synthesize")
async def synthesize(
    request: SynthesizeRequest,
    settings: Settings = Depends(get_settings),
    user: Annotated[UserRecord | None, Depends(require_user_when_enforced)] = None,
) -> dict:
    provider = TextToSpeechProviderFactory.create(settings)
    result = await provider.synthesize(request.text, voice=request.voice)
    return {"mime_type": result.mime_type, "provider": result.provider, "voice": result.voice}
