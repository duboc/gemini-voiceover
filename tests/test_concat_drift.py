"""Tests for the overlap/drift handling in VideoProcessor._fallback_concatenation.

Original behaviour: when a TTS segment overran its expected end_time, the
loop kept appending without resetting current_time, so subsequent silence
gaps were computed against the *expected* timeline while the audio
timeline was already drifting forward. The output ended up longer than
total_duration and segment N's audio was offset from where the video
expected it.

Fix: when a segment overlaps the next start_time, truncate the previous
segment to fit (with a tiny fade-out to avoid clicks). When a segment
extends past total_duration, truncate it. current_time is always advanced
to the *expected* end_time, eliminating drift.

We assert the resulting ffmpeg command shape — no real audio decode —
because ffmpeg is not available in the unit-test environment.
"""
from __future__ import annotations

import os
import subprocess
from unittest.mock import MagicMock, patch

import pytest


def _captured_subprocess_run(captured):
    def _run(cmd, *args, **kwargs):
        captured.append(cmd)
        result = MagicMock()
        result.returncode = 0
        result.stderr = ""
        return result
    return _run


def _make_audio_files(tmp_path, count, prefix="seg"):
    files = []
    for i in range(count):
        p = tmp_path / f"{prefix}_{i}.wav"
        p.write_bytes(b"RIFF" + b"\x00" * 100)  # not a valid wav, but exists
        files.append(str(p))
    return files


@pytest.fixture
def video_processor(monkeypatch, tmp_path):
    from modules.video_processor import VideoProcessor
    # Point Config.TEMP_FOLDER at tmp_path so silence files land in an isolated dir
    from config import Config
    monkeypatch.setattr(Config, "TEMP_FOLDER", str(tmp_path))
    return VideoProcessor()


def test_concat_truncates_overrunning_segment_to_fit_next(video_processor, tmp_path, monkeypatch):
    """If segment 0 audio is 5s but timestamps say 0-3s and segment 1 starts
    at 3s, the prior audio must be truncated so it does not bleed into 1."""
    audio_files = _make_audio_files(tmp_path, 2)
    timestamps = [(0.0, 3.0), (3.0, 6.0)]
    output_path = str(tmp_path / "out.wav")

    # Mock ffmpeg-python and subprocess so we just observe what would be invoked
    captured_cmds = []

    monkeypatch.setattr(
        "modules.video_processor.subprocess.run",
        _captured_subprocess_run(captured_cmds),
    )

    fake_chain = MagicMock()
    fake_chain.input.return_value = fake_chain
    fake_chain.output.return_value = fake_chain
    fake_chain.overwrite_output.return_value = fake_chain
    fake_chain.run.return_value = None
    monkeypatch.setattr("modules.video_processor.ffmpeg.input", MagicMock(return_value=fake_chain))
    monkeypatch.setattr("modules.video_processor.ffmpeg.output", MagicMock(return_value=fake_chain))
    monkeypatch.setattr("modules.video_processor.ffmpeg.run", MagicMock())

    # Stub _get_segment_duration to report segment 0 is 5s long (overrun)
    monkeypatch.setattr(
        video_processor,
        "_get_segment_duration",
        lambda path: 5.0 if "seg_0" in path else 3.0,
        raising=False,
    )

    video_processor._fallback_concatenation(
        audio_files, timestamps, output_path, total_duration=6.0,
        sample_rate=24000, channels=1,
    )

    # When _get_segment_duration > expected slot, the implementation must call
    # ffmpeg to truncate the segment. We assert at least one such trim happened.
    trims = [c for c in captured_cmds if "-t" in c and any("seg_0" in str(arg) for arg in c)]
    assert trims, (
        "Expected a subprocess ffmpeg trim call on the overrunning segment 0; "
        f"captured commands: {captured_cmds}"
    )


def test_concat_helper_advances_current_time_by_expected_duration(video_processor, tmp_path, monkeypatch):
    """No matter how long actual audio is, current_time must be advanced to
    the *expected* end_time so silence calculations don't drift."""
    # We test the pure helper directly, decoupled from ffmpeg I/O
    timeline = video_processor._build_concat_timeline(
        audio_files=["a.wav", "b.wav", "c.wav"],
        timestamps=[(0.0, 2.0), (2.0, 4.0), (4.0, 6.0)],
        actual_durations=[3.0, 1.5, 2.5],  # overrun, underrun, overrun
        total_duration=6.0,
    )

    # current_time after each segment must equal its expected end_time
    assert abs(timeline["final_current_time"] - 6.0) < 1e-6
    # Segment 0 must be marked for truncation (3.0s actual vs 2.0s slot)
    assert abs(timeline["truncations"][0] - 2.0) < 1e-6
    # Segment 1 fits, no truncation
    assert 1 not in timeline["truncations"]
    # Segment 2 overruns total_duration, capped at total
    assert abs(timeline["truncations"][2] - 2.0) < 1e-6


def test_concat_helper_inserts_silence_only_for_real_gaps(video_processor):
    timeline = video_processor._build_concat_timeline(
        audio_files=["a.wav", "b.wav"],
        timestamps=[(0.0, 2.0), (5.0, 7.0)],  # 3-second gap
        actual_durations=[2.0, 2.0],
        total_duration=10.0,
    )

    # One pre-segment-1 silence of 3s, plus a final silence of 3s (10 - 7)
    silences = timeline["silences"]
    assert any(abs(d - 3.0) < 1e-6 for d in silences.values()), (
        f"Expected a 3.0s gap silence; got {silences}"
    )
    assert abs(timeline["final_silence"] - 3.0) < 1e-6
