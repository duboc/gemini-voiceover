"""Tests for Config.TTS_MAX_RETRIES being honoured by GoogleTTSClient.

Before: _synthesize_with_retry hardcoded max_retries=3 even though
Config.TTS_MAX_RETRIES defaults to 5 — production callers had no way
to actually tune the retry count.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def google_tts_client():
    from modules.google_tts_client import GoogleTTSClient
    client = GoogleTTSClient()
    return client


def test_synthesize_with_retry_uses_config_max_retries(google_tts_client, monkeypatch):
    """When ResourceExhausted keeps firing, retries should equal Config.TTS_MAX_RETRIES."""
    from config import Config
    from google.api_core import exceptions

    monkeypatch.setattr(Config, "TTS_MAX_RETRIES", 5)

    call_count = {"n": 0}

    def _always_fail(*args, **kwargs):
        call_count["n"] += 1
        raise exceptions.ResourceExhausted("rate limit")

    google_tts_client.client = MagicMock()
    google_tts_client.client.synthesize_speech.side_effect = _always_fail

    # Patch sleep to avoid waiting through exponential backoff
    with patch("modules.google_tts_client.time.sleep"):
        with pytest.raises(exceptions.ResourceExhausted):
            google_tts_client._synthesize_with_retry(
                MagicMock(), MagicMock(), MagicMock()
            )

    assert call_count["n"] == 5, (
        f"Expected 5 attempts (Config.TTS_MAX_RETRIES), got {call_count['n']}"
    )


def test_synthesize_with_retry_succeeds_before_exhausting_retries(google_tts_client, monkeypatch):
    """Should return as soon as the call succeeds, not exhaust all retries."""
    from config import Config
    from google.api_core import exceptions

    monkeypatch.setattr(Config, "TTS_MAX_RETRIES", 5)

    call_count = {"n": 0}
    success_response = MagicMock()

    def _fail_twice_then_succeed(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] < 3:
            raise exceptions.ResourceExhausted("rate limit")
        return success_response

    google_tts_client.client = MagicMock()
    google_tts_client.client.synthesize_speech.side_effect = _fail_twice_then_succeed

    with patch("modules.google_tts_client.time.sleep"):
        result = google_tts_client._synthesize_with_retry(
            MagicMock(), MagicMock(), MagicMock()
        )

    assert result is success_response
    assert call_count["n"] == 3


def test_synthesize_with_retry_respects_lower_config_value(google_tts_client, monkeypatch):
    """Lowering TTS_MAX_RETRIES to 2 should cap attempts at 2."""
    from config import Config
    from google.api_core import exceptions

    monkeypatch.setattr(Config, "TTS_MAX_RETRIES", 2)

    call_count = {"n": 0}

    def _always_fail(*args, **kwargs):
        call_count["n"] += 1
        raise exceptions.ResourceExhausted("rate limit")

    google_tts_client.client = MagicMock()
    google_tts_client.client.synthesize_speech.side_effect = _always_fail

    with patch("modules.google_tts_client.time.sleep"):
        with pytest.raises(exceptions.ResourceExhausted):
            google_tts_client._synthesize_with_retry(
                MagicMock(), MagicMock(), MagicMock()
            )

    assert call_count["n"] == 2
