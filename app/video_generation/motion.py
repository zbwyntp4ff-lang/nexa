"""Build a natural motion plan from the image + user text (real analysis when possible)."""
from __future__ import annotations

import asyncio
import base64
import json
from typing import Any

import httpx

from app.config.settings import Settings
from app.video_generation.intent import DEFAULT_CONSERVATIVE_MOTION, is_bare_animate_request
from app.video_generation.models import MotionPlan


async def build_motion_plan(
    *,
    settings: Settings,
    image_bytes: bytes,
    mime_type: str,
    user_text: str,
) -> MotionPlan:
    bare = is_bare_animate_request(user_text)
    user_notes = "" if bare else (user_text or "").strip()

    # Cap analysis so a slow local vision model cannot stall the job forever.
    analysis: dict[str, Any] | None = None
    try:
        analysis = await asyncio.wait_for(
            _analyze_image(settings, image_bytes, mime_type),
            timeout=18.0,
        )
    except Exception:  # noqa: BLE001
        analysis = None

    if analysis:
        scene = analysis.get("scene") or "the uploaded image"
        suggested = analysis.get("gentle_motion") or DEFAULT_CONSERVATIVE_MOTION
        if bare:
            prompt = (
                f"Animate this scene naturally and conservatively: {scene}. "
                f"{suggested} Preserve identity and appearance exactly. "
                f"{DEFAULT_CONSERVATIVE_MOTION}"
            )
            return MotionPlan(
                scene_summary=str(scene),
                motion_prompt=prompt.strip(),
                conservative=True,
                source="vision",
            )
        prompt = (
            f"Animate this scene: {scene}. "
            f"User motion request: {user_notes}. "
            f"Keep identity/appearance unchanged. Prefer natural restrained motion. "
            f"{DEFAULT_CONSERVATIVE_MOTION}"
        )
        return MotionPlan(
            scene_summary=str(scene),
            motion_prompt=prompt.strip(),
            conservative=True,
            source="vision",
        )

    if bare:
        return MotionPlan(
            scene_summary="uploaded image",
            motion_prompt=DEFAULT_CONSERVATIVE_MOTION,
            conservative=True,
            source="default",
        )
    return MotionPlan(
        scene_summary="uploaded image",
        motion_prompt=(
            f"{user_notes}. Keep identity and appearance unchanged. "
            f"{DEFAULT_CONSERVATIVE_MOTION}"
        ),
        conservative=True,
        source="user",
    )


async def _analyze_image(
    settings: Settings, image_bytes: bytes, mime_type: str
) -> dict[str, Any] | None:
    """Prefer real OpenAI vision, else local Ollama vision — never invent fake scene details."""
    if (settings.vision_provider or "").lower() == "openai" and settings.openai_api_key:
        try:
            return await _analyze_with_openai(settings, image_bytes, mime_type)
        except Exception:  # noqa: BLE001
            pass
    # Local Ollama vision (moondream / llava) when available
    try:
        return await _analyze_with_ollama(settings, image_bytes)
    except Exception:  # noqa: BLE001
        return None


async def _analyze_with_openai(
    settings: Settings, image_bytes: bytes, mime_type: str
) -> dict[str, Any]:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=settings.openai_api_key, timeout=45.0)
    mime = mime_type or "image/jpeg"
    data_uri = f"data:{mime};base64,{base64.b64encode(image_bytes).decode('ascii')}"
    prompt = (
        "Analyze this image for gentle image-to-video animation. "
        "Reply ONLY valid JSON with keys: scene (short), gentle_motion (1-2 sentences). "
        "Do not invent people/objects that are not visible. Prefer subtle natural motion."
    )
    response = await client.chat.completions.create(
        model=settings.openai_vision_model,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": data_uri}},
                ],
            }
        ],
        max_tokens=300,
    )
    text = (response.choices[0].message.content or "").strip()
    return _parse_json_object(text)


async def _analyze_with_ollama(settings: Settings, image_bytes: bytes) -> dict[str, Any]:
    base = (settings.local_model_url or "http://localhost:11434").rstrip("/")
    model = settings.local_model_name or "moondream:latest"
    b64 = base64.b64encode(image_bytes).decode("ascii")
    prompt = (
        "Describe this image briefly for animation. "
        'Respond as JSON: {"scene":"...","gentle_motion":"..."}. '
        "Suggest only subtle natural motion. Do not invent unseen objects."
    )
    candidates = [model]
    if "moondream" not in model.lower() and "llava" not in model.lower():
        candidates = ["moondream:latest", model]
    last_error: Exception | None = None
    async with httpx.AsyncClient(timeout=httpx.Timeout(12.0, connect=3.0)) as client:
        for candidate in candidates:
            try:
                resp = await client.post(
                    f"{base}/api/generate",
                    json={
                        "model": candidate,
                        "prompt": prompt,
                        "images": [b64],
                        "stream": False,
                        "format": "json",
                        "options": {"num_predict": 120},
                    },
                )
                if resp.status_code >= 400:
                    last_error = RuntimeError(resp.text[:200])
                    continue
                payload = resp.json()
                return _parse_json_object(payload.get("response") or "")
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                continue
    if last_error:
        raise last_error
    raise RuntimeError("Ollama vision analysis unavailable.")


def _parse_json_object(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.startswith("json"):
            cleaned = cleaned[4:].strip()
    try:
        data = json.loads(cleaned)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start >= 0 and end > start:
            data = json.loads(cleaned[start : end + 1])
            if isinstance(data, dict):
                return data
    return {"scene": cleaned[:240] or "the uploaded image", "gentle_motion": DEFAULT_CONSERVATIVE_MOTION}
