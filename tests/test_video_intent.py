"""Unit tests for IMAGE_TO_VIDEO intent detection (no network)."""
from app.video_generation.intent import (
    DEFAULT_CONSERVATIVE_MOTION,
    detects_image_to_video,
    is_bare_animate_request,
)


def test_detects_russian_animate():
    assert detects_image_to_video("Оживи эту картинку")
    assert detects_image_to_video("оживи")
    assert is_bare_animate_request("оживи")
    assert is_bare_animate_request("Оживи эту картинку")


def test_detects_english_animate():
    assert detects_image_to_video("animate this image")
    assert detects_image_to_video("bring this photo to life")
    assert detects_image_to_video("image to video")


def test_rejects_unrelated():
    assert not detects_image_to_video("what is in this picture?")
    assert not detects_image_to_video("hello")


def test_custom_motion_not_bare():
    assert detects_image_to_video("оживи и слегка поверни камеру вправо")
    assert not is_bare_animate_request("оживи и слегка поверни камеру вправо")
    assert DEFAULT_CONSERVATIVE_MOTION
