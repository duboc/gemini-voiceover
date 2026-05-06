"""Tests for the native Gemini TTS code path in GoogleTTSClient.

Voices like 'Zephyr', 'Puck', 'Kore' belong to the Gemini native TTS
API (genai.Client().models.generate_content with response_modalities=AUDIO),
NOT to Cloud TTS — the service rejects them with 400 'language code not
supported'. The client must detect a bare-persona voice name and route
through the right API.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _gemini_response_with_pcm(pcm: bytes) -> MagicMock:
    """Build the nested object structure genai.generate_content returns."""
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
def patched_genai_client(monkeypatch):
    """Replace the genai.Client constructor used by GoogleTTSClient with a
    mock that captures generate_content calls."""
    captured = {"calls": []}

    def _gen(model, contents, config):
        captured["calls"].append({"model": model, "contents": contents, "config": config})
        return _gemini_response_with_pcm(b"\x00\x00" * 24000)  # 1s of silence @ 24kHz mono

    fake_models = MagicMock()
    fake_models.generate_content.side_effect = _gen
    fake_client = MagicMock()
    fake_client.models = fake_models

    monkeypatch.setattr(
        "modules.google_tts_client.genai.Client",
        MagicMock(return_value=fake_client),
        raising=False,
    )
    return captured


def _is_gemini_voice_name(name: str) -> bool:
    return "-Chirp3-HD-" not in name and "-Standard-" not in name and "-Wavenet-" not in name


def test_detects_gemini_voice_name():
    """Bare-persona names route through Gemini API; lang-prefixed names route
    through Cloud TTS."""
    from modules.google_tts_client import is_gemini_voice
    assert is_gemini_voice("Zephyr")
    assert is_gemini_voice("Puck")
    assert is_gemini_voice("Aoede")
    assert not is_gemini_voice("cmn-CN-Chirp3-HD-Zephyr")
    assert not is_gemini_voice("en-US-Chirp3-HD-Charon")
    assert not is_gemini_voice("en-US-Standard-A")


def test_generate_speech_uses_native_gemini_api_for_bare_persona(patched_genai_client, tmp_path):
    """When voice_name is a bare persona ('Zephyr'), route through
    genai.Client().models.generate_content() instead of Cloud TTS."""
    from modules.google_tts_client import GoogleTTSClient

    client = GoogleTTSClient()
    # Cloud TTS client must NOT be touched
    client.client = MagicMock()
    client.client.synthesize_speech.side_effect = AssertionError("Cloud TTS must not be called for Gemini voices")

    translation = {
        "target_language": "zh-CN",
        "transcription": [
            {"start_time": 0.0, "end_time": 1.0, "text": "你好"},
        ],
    }

    files = client.generate_speech(translation, "Zephyr", str(tmp_path), model_name="gemini-3.1-flash-tts-preview")

    assert len(files) == 1
    assert len(patched_genai_client["calls"]) == 1
    call = patched_genai_client["calls"][0]
    assert call["model"] == "gemini-3.1-flash-tts-preview"
    assert "你好" in str(call["contents"])
    # The voice_config must be wired with our persona
    assert "Zephyr" in str(call["config"])


def test_native_gemini_output_is_valid_wav(patched_genai_client, tmp_path):
    """The PCM data returned by Gemini must be wrapped in a WAV header so
    downstream FFmpeg/concat treats it as a regular audio file."""
    import wave
    from modules.google_tts_client import GoogleTTSClient

    client = GoogleTTSClient()
    translation = {
        "target_language": "en-US",
        "transcription": [{"start_time": 0.0, "end_time": 1.0, "text": "hello"}],
    }
    files = client.generate_speech(translation, "Kore", str(tmp_path), model_name="gemini-3.1-flash-tts-preview")

    with wave.open(files[0], "rb") as wf:
        assert wf.getnchannels() == 1
        assert wf.getsampwidth() == 2
        assert wf.getframerate() == 24000
        assert wf.getnframes() > 0


def test_chirp3_voice_still_uses_cloud_tts(monkeypatch, tmp_path):
    """A lang-prefixed Chirp3 name must NOT touch the Gemini native client;
    it stays on Cloud TTS."""
    from modules.google_tts_client import GoogleTTSClient

    monkeypatch.setattr(
        "modules.google_tts_client.genai.Client",
        MagicMock(side_effect=AssertionError("genai must not be called for Chirp3 voices")),
        raising=False,
    )

    client = GoogleTTSClient()
    fake_resp = MagicMock()
    fake_resp.audio_content = b"FAKE_WAV_BYTES"
    client.client = MagicMock()
    client.client.synthesize_speech.return_value = fake_resp

    translation = {
        "target_language": "cmn-CN",
        "transcription": [{"start_time": 0.0, "end_time": 1.0, "text": "你好"}],
    }
    files = client.generate_speech(translation, "cmn-CN-Chirp3-HD-Zephyr", str(tmp_path))

    assert len(files) == 1
    client.client.synthesize_speech.assert_called_once()


def test_gemini_tts_default_model_is_3_1_preview():
    from config import Config
    assert Config.GEMINI_TTS_MODEL == "gemini-3.1-flash-tts-preview"
