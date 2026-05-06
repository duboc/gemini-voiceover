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


@pytest.fixture
def google_tts_client(monkeypatch):
    from modules.google_tts_client import GoogleTTSClient
    client = GoogleTTSClient()

    calls = {"texts": []}

    def _gen(model, contents, config):
        # contents is the bare text string for native Gemini TTS
        calls["texts"].append(str(contents))
        return _gemini_response_with_pcm(b"\x00\x00" * 100)

    fake_client = MagicMock()
    fake_models = MagicMock()
    fake_models.generate_content.side_effect = _gen
    fake_client.models = fake_models
    monkeypatch.setattr(
        "modules.google_tts_client.genai.Client",
        MagicMock(return_value=fake_client),
        raising=False,
    )

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
