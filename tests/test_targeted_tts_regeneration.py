"""Tests for GoogleTTSClient.generate_speech_segments (targeted regeneration).

After the duration-adjustment loop shortens a few segments, only those
need fresh audio. The old code regenerated all N — wasting quota and
time. The new generate_speech_segments(indices=[...]) honours an opt-in
list, while generate_speech delegates with the full range.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def _build_translation(n: int) -> dict:
    return {
        "target_language": "en-US",
        "transcription": [
            {"start_time": float(i), "end_time": float(i + 1), "text": f"text-{i}"}
            for i in range(n)
        ],
    }


@pytest.fixture
def google_tts_client():
    from modules.google_tts_client import GoogleTTSClient
    client = GoogleTTSClient()

    calls = {"texts": []}

    def _synth(*args, **kwargs):
        # SynthesisInput first positional in the request; capture text
        req = kwargs.get("request") or (args[0] if args else None)
        if req is not None and hasattr(req, "input"):
            calls["texts"].append(getattr(req.input, "text", None))
        resp = MagicMock()
        resp.audio_content = b"x"
        return resp

    client.client = MagicMock()
    client.client.synthesize_speech.side_effect = _synth
    client._test_calls = calls
    return client


def test_generate_speech_segments_only_processes_requested_indices(google_tts_client, tmp_path):
    translation = _build_translation(10)

    files = google_tts_client.generate_speech_segments(
        translation, "Zephyr", str(tmp_path), segment_indices=[2, 5], model_name="m"
    )

    # Only 2 synth calls
    assert len(google_tts_client._test_calls["texts"]) == 2
    assert sorted(google_tts_client._test_calls["texts"]) == ["text-2", "text-5"]
    assert len(files) == 2
    # Filenames keep original segment index (zero-padded)
    assert any("segment_002_" in f for f in files)
    assert any("segment_005_" in f for f in files)


def test_generate_speech_delegates_to_segments_with_full_range(google_tts_client, tmp_path):
    """The legacy generate_speech entry point must still produce N files."""
    translation = _build_translation(4)

    files = google_tts_client.generate_speech(translation, "Zephyr", str(tmp_path), model_name="m")

    assert len(google_tts_client._test_calls["texts"]) == 4
    assert len(files) == 4


def test_generate_speech_segments_skips_invalid_indices(google_tts_client, tmp_path):
    """Out-of-range indices should be ignored gracefully, not crash."""
    translation = _build_translation(3)

    files = google_tts_client.generate_speech_segments(
        translation, "Zephyr", str(tmp_path), segment_indices=[1, 99, -5], model_name="m"
    )

    assert len(google_tts_client._test_calls["texts"]) == 1
    assert google_tts_client._test_calls["texts"] == ["text-1"]
    assert len(files) == 1
