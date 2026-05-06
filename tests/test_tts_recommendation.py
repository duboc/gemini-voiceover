"""Tests for per-language recommended TTS backend.

Mandarin Chirp 3 HD voices for many personas may not exist in Vertex AI
(returning 404 at synth time). To steer users toward the safer path
without removing choice, Config exposes a recommendation per language
and a tiny endpoint surfaces it to the UI.
"""
from __future__ import annotations

import pytest


def test_config_recommended_tts_backend_for_mandarin():
    from config import Config

    assert hasattr(Config, "RECOMMENDED_TTS_BACKEND"), (
        "Config must expose a RECOMMENDED_TTS_BACKEND mapping"
    )
    assert Config.RECOMMENDED_TTS_BACKEND.get("zh-CN") == "gemini"


def test_get_recommended_tts_backend_returns_gemini_for_mandarin():
    from config import Config

    assert Config.get_recommended_tts_backend("zh-CN") == "gemini"


def test_get_recommended_tts_backend_falls_back_to_default():
    from config import Config

    # English has no specific recommendation, so it must fall back
    assert Config.get_recommended_tts_backend("en-US") == Config.TTS_BACKEND


def test_get_recommended_tts_backend_unknown_language_falls_back():
    from config import Config

    assert Config.get_recommended_tts_backend("xx-XX") == Config.TTS_BACKEND


@pytest.fixture
def flask_client(monkeypatch):
    """Build a Flask test client without hitting real Vertex/GCS at import."""
    from unittest.mock import MagicMock, patch
    import importlib

    # Pre-import the inner modules so patch can resolve their attributes
    import modules.gemini_client  # noqa: F401

    with patch("modules.gemini_client.genai.Client", return_value=MagicMock()):
        import app as app_module
        importlib.reload(app_module)
        app_module.app.config["TESTING"] = True
        with app_module.app.test_client() as c:
            yield c


def test_endpoint_returns_recommendation_for_mandarin(flask_client):
    resp = flask_client.get("/api/tts-recommendation/zh-CN")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["recommended"] == "gemini"
    assert body["language"] == "zh-CN"


def test_endpoint_returns_default_for_english(flask_client):
    from config import Config

    resp = flask_client.get("/api/tts-recommendation/en-US")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["recommended"] == Config.TTS_BACKEND


def test_endpoint_rejects_unsupported_language(flask_client):
    resp = flask_client.get("/api/tts-recommendation/xx-XX")
    assert resp.status_code == 400
