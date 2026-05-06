"""Tests for the loudnorm pass applied at the end of _fallback_concatenation.

TTS segments arrive at varying loudness across calls; concatenating them
raw produces a track where some sentences are noticeably louder than
others. A single loudnorm pass at the end normalises the whole track to
broadcast-grade loudness without per-segment processing overhead.

V1 is configurable via Config.ENABLE_LOUDNORM (default True) and
LOUDNORM_TARGET_I / LOUDNORM_TP / LOUDNORM_LRA so operators can tune for
their downstream platform.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _stub_ffmpeg_chain(monkeypatch, captured: list):
    """Patch ffmpeg-python so that every .output(...) call (whether on the
    module or on a chained object) records its kwargs into `captured`.
    The real chain shape is `ffmpeg.input(x).output(path, **kw).overwrite_output().run()`.
    """
    fake_chain = MagicMock()

    def _record_output(*args, **kwargs):
        captured.append({"args": args, "kwargs": kwargs})
        return fake_chain

    fake_chain.output.side_effect = _record_output
    fake_chain.overwrite_output.return_value = fake_chain
    fake_chain.run.return_value = None

    monkeypatch.setattr("modules.video_processor.ffmpeg.input", MagicMock(return_value=fake_chain))
    monkeypatch.setattr("modules.video_processor.ffmpeg.output", _record_output)
    monkeypatch.setattr("modules.video_processor.ffmpeg.run", MagicMock())


def test_loudnorm_applied_to_final_concat(monkeypatch, tmp_path):
    from config import Config
    from modules.video_processor import VideoProcessor

    monkeypatch.setattr(Config, "ENABLE_LOUDNORM", True)
    monkeypatch.setattr(Config, "TEMP_FOLDER", str(tmp_path))

    captured = []
    _stub_ffmpeg_chain(monkeypatch, captured)

    vp = VideoProcessor()
    monkeypatch.setattr(vp, "_get_segment_duration", lambda p: 1.0, raising=False)

    audio_files = [str(tmp_path / "a.wav"), str(tmp_path / "b.wav")]
    for f in audio_files:
        with open(f, "wb") as fh:
            fh.write(b"x")

    out = str(tmp_path / "out.wav")
    vp._fallback_concatenation(
        audio_files, [(0.0, 1.0), (1.0, 2.0)], out,
        total_duration=2.0, sample_rate=24000, channels=1,
    )

    # Find the final concat output call (target == out path)
    final_outs = [c for c in captured if out in c["args"]]
    assert final_outs, f"No ffmpeg.output call targeted {out}; got {captured}"
    af = final_outs[-1]["kwargs"].get("af", "")
    assert "loudnorm" in af, f"Expected 'loudnorm' filter in -af, got: {af!r}"
    assert "I=-16" in af
    assert "TP=-1.5" in af
    assert "LRA=11" in af


def test_loudnorm_can_be_disabled(monkeypatch, tmp_path):
    from config import Config
    from modules.video_processor import VideoProcessor

    monkeypatch.setattr(Config, "ENABLE_LOUDNORM", False)
    monkeypatch.setattr(Config, "TEMP_FOLDER", str(tmp_path))

    captured = []
    _stub_ffmpeg_chain(monkeypatch, captured)

    vp = VideoProcessor()
    monkeypatch.setattr(vp, "_get_segment_duration", lambda p: 1.0, raising=False)

    audio_files = [str(tmp_path / "a.wav")]
    for f in audio_files:
        with open(f, "wb") as fh:
            fh.write(b"x")

    out = str(tmp_path / "out.wav")
    vp._fallback_concatenation(
        audio_files, [(0.0, 1.0)], out,
        total_duration=1.0, sample_rate=24000, channels=1,
    )

    final_outs = [c for c in captured if out in c["args"]]
    assert final_outs
    af = final_outs[-1]["kwargs"].get("af", "")
    assert "loudnorm" not in af, f"Expected no loudnorm when disabled; got: {af!r}"


def test_config_exposes_loudnorm_defaults():
    from config import Config

    assert hasattr(Config, "ENABLE_LOUDNORM")
    assert Config.ENABLE_LOUDNORM is True
    assert Config.LOUDNORM_TARGET_I == "-16"
    assert Config.LOUDNORM_TP == "-1.5"
    assert Config.LOUDNORM_LRA == "11"
