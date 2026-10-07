"""Detect IMAGE_TO_VIDEO intent from user text (RU/EN)."""
from __future__ import annotations

import re

_ANIMATE_PATTERNS = (
    r"\bожив(?:и|ить|ление|и\s+эту)\b",
    r"\bанимир(?:уй|овать|уешь)\b",
    r"\bсделай\s+(?:видео|ролик|клип)\b",
    r"\bпревратить?\s+в\s+видео\b",
    r"\bдвижение\b",
    r"\banimat(?:e|ion|ing)\b",
    r"\bbring\s+(?:this\s+)?(?:image|picture|photo)\s+to\s+life\b",
    r"\bmake\s+(?:this\s+)?(?:image|picture|photo)\s+move\b",
    r"\bimage[\s_-]?to[\s_-]?video\b",
    r"\bi2v\b",
    r"\blive\s+(?:photo|picture|image)\b",
    r"\bvideo\s+from\s+(?:this\s+)?(?:image|picture|photo)\b",
)

_ONLY_ANIMATE = re.compile(
    r"^\s*(?:оживи(?:\s+эту(?:\s+картинку|\s+фотку|\s+фото)?)?|"
    r"animate(?:\s+this)?|"
    r"bring\s+(?:it|this)\s+to\s+life)\s*[.!]?\s*$",
    re.IGNORECASE,
)

_COMPILED = [re.compile(p, re.IGNORECASE | re.UNICODE) for p in _ANIMATE_PATTERNS]


def detects_image_to_video(text: str) -> bool:
    cleaned = (text or "").strip()
    if not cleaned:
        return False
    return any(p.search(cleaned) for p in _COMPILED)


def is_bare_animate_request(text: str) -> bool:
    """True when the user only asked to animate, with no custom motion notes."""
    return bool(_ONLY_ANIMATE.match((text or "").strip()))


DEFAULT_CONSERVATIVE_MOTION = (
    "Subtle natural cinematic motion only: gentle ambient movement, soft parallax, "
    "light breathing or breeze if appropriate. Keep identity, face, body, clothing, "
    "and composition unchanged. No morphing, no style transfer, no camera whip-pans, "
    "no exaggerated or surreal motion."
)
