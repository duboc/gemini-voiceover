"""Tests for parallel TTS generation in GoogleTTSClient.generate_speech.

Before: segments were synthesised in a tight `for` loop — for a 30-segment
video that's at minimum ~30 sequential round-trips. Now we fan out the
work to a ThreadPoolExecutor capped at Config.TTS_PARALLEL_WORKERS, while
still ordering the resulting file paths by segment index.
"""
from __future__ import annotations

import threading
import time
from unittest.mock import MagicMock, patch

import pytest


def _gemini_response_with_pcm(pcm: bytes) -> MagicMock:
    inline_data = MagicMock()
    inline_data.data = pcm
    part = MagicMock()
    part.inline_data = inline_data
    content = MagicMock()
    content.parts = [part]
    candidate = MagicMock()
    candidate.content = content
    response = MagicMock()
    response.candidates = [candidate]
    return response


@pytest.fixture(autouse=True)
def _patch_genai(monkeypatch):
    """Bare-persona voices route through genai.Client now; mock it so tests
    that pre-date the refactor continue to exercise the parallelism logic."""
    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_client.models = fake_models
    monkeypatch.setattr(
        "modules.google_tts_client.genai.Client",
        MagicMock(return_value=fake_client),
        raising=False,
    )
    return fake_models


def _build_translation(n: int) -> dict:
    return {
        "target_language": "en-US",
        "transcription": [
            {"start_time": float(i), "end_time": float(i + 1), "text": f"segment {i}"}
            for i in range(n)
        ],
    }


@pytest.fixture
def google_tts_client():
    from modules.google_tts_client import GoogleTTSClient
    return GoogleTTSClient()


def test_generate_speech_runs_segments_in_parallel(google_tts_client, tmp_path, monkeypatch, _patch_genai):
    """10 segments, each simulating 0.2s of latency, should finish well under
    the 2.0s a serial loop would take."""
    from config import Config

    monkeypatch.setattr(Config, "TTS_PARALLEL_WORKERS", 5)

    active = {"count": 0, "max": 0}
    lock = threading.Lock()

    def _slow_gemini(*args, **kwargs):
        with lock:
            active["count"] += 1
            active["max"] = max(active["max"], active["count"])
        time.sleep(0.2)
        with lock:
            active["count"] -= 1
        return _gemini_response_with_pcm(b"\x00\x00" * 100)

    _patch_genai.generate_content.side_effect = _slow_gemini

    translation = _build_translation(10)
    out_dir = tmp_path / "speech"
    out_dir.mkdir()

    start = time.monotonic()
    files = google_tts_client.generate_speech(translation, "Zephyr", str(out_dir), model_name="m")
    elapsed = time.monotonic() - start

    # 10 segments × 0.2s = 2.0s serial. With 5 workers ideal is 0.4s; allow 1.0s slack.
    assert elapsed < 1.0, f"Parallel run took {elapsed:.2f}s, expected < 1.0s"
    assert active["max"] >= 2, "No concurrency observed; loop appears serial"
    assert active["max"] <= 5, f"Concurrency {active['max']} exceeded TTS_PARALLEL_WORKERS=5"
    assert len(files) == 10


def test_generate_speech_returns_files_in_segment_order(google_tts_client, tmp_path, _patch_genai):
    """Even though work runs concurrently, the returned list must be ordered
    by segment index so downstream timing logic stays correct."""

    def _synth(model, contents, config):
        # Sleep proportional to which segment to scramble completion order
        time.sleep(0.05 if "segment 9" in str(contents) else 0.01)
        return _gemini_response_with_pcm(b"\x00\x00" * 100)

    _patch_genai.generate_content.side_effect = _synth

    translation = _build_translation(10)
    files = google_tts_client.generate_speech(translation, "Zephyr", str(tmp_path), model_name="m")

    # Every returned filename must include its segment index as zero-padded prefix
    for i, f in enumerate(files):
        assert f"segment_{i:03d}_" in f, f"File at position {i} is {f}; expected segment_{i:03d}_*"


def test_config_exposes_tts_parallel_workers_default():
    from config import Config

    assert hasattr(Config, "TTS_PARALLEL_WORKERS")
    assert Config.TTS_PARALLEL_WORKERS >= 1
