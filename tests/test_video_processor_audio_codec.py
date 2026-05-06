"""Tests for the audio codec settings used when muxing the final video.

The original `replace_video_audio` left audio_bitrate to ffmpeg's default
(~128 kbps mono) which made the output noticeably quieter and thinner
than the source. We now pin `audio_bitrate` (configurable) and force
stereo + 48 kHz so the rendered file matches consumer-video expectations.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def captured_output_kwargs(monkeypatch):
    """Capture the kwargs passed to ffmpeg.output() inside replace_video_audio."""
    captured = {}

    def _fake_output(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        result = MagicMock()
        result.overwrite_output.return_value = result
        return result

    monkeypatch.setattr("modules.video_processor.ffmpeg.output", _fake_output)
    monkeypatch.setattr("modules.video_processor.ffmpeg.input", MagicMock(return_value=MagicMock()))
    monkeypatch.setattr("modules.video_processor.ffmpeg.run", MagicMock())
    return captured


def test_replace_video_audio_uses_explicit_bitrate(captured_output_kwargs, tmp_path):
    from modules.video_processor import VideoProcessor

    video = tmp_path / "in.mp4"
    audio = tmp_path / "a.wav"
    out = tmp_path / "out.mp4"
    video.write_bytes(b"x")
    audio.write_bytes(b"y")

    VideoProcessor().replace_video_audio(str(video), str(audio), str(out))

    kwargs = captured_output_kwargs["kwargs"]
    assert kwargs.get("audio_bitrate") == "192k", (
        f"Expected audio_bitrate=192k, got {kwargs.get('audio_bitrate')!r}"
    )
    assert kwargs.get("ac") == 2, f"Expected ac=2 (stereo), got {kwargs.get('ac')!r}"
    assert kwargs.get("ar") == 48000, f"Expected ar=48000, got {kwargs.get('ar')!r}"
    assert kwargs.get("acodec") == "aac"
    assert kwargs.get("vcodec") == "copy"


def test_replace_video_audio_respects_config_override(captured_output_kwargs, tmp_path, monkeypatch):
    from config import Config
    from modules.video_processor import VideoProcessor

    monkeypatch.setattr(Config, "OUTPUT_AUDIO_BITRATE", "256k")

    video = tmp_path / "in.mp4"
    audio = tmp_path / "a.wav"
    out = tmp_path / "out.mp4"
    video.write_bytes(b"x")
    audio.write_bytes(b"y")

    VideoProcessor().replace_video_audio(str(video), str(audio), str(out))

    assert captured_output_kwargs["kwargs"].get("audio_bitrate") == "256k"


def test_config_exposes_output_audio_bitrate_default():
    from config import Config

    assert hasattr(Config, "OUTPUT_AUDIO_BITRATE")
    assert Config.OUTPUT_AUDIO_BITRATE == "192k"
