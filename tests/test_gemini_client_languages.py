"""Tests for language code -> human name resolution in GeminiClient.

These guard against the regression where new languages (zh-CN, nl-NL,
pl-PL, ru-RU) are added to Config.SUPPORTED_LANGUAGES but the prompt
sent to Gemini still says "Translate to zh-CN" because the inner
language_names dict was never updated. The fix extracts the mapping to
a module-level LANGUAGE_NAMES constant.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


def _fake_client(captured: dict):
    """Build a fake genai.Client whose generate_content captures the prompt."""
    fake_response = MagicMock()
    fake_response.text = '{"transcription": []}'

    fake_models = MagicMock()

    def _capture(model, contents, config):
        # contents is List[Content]; we want the first user text part
        captured["prompt"] = contents[0].parts[0].text
        captured["model"] = model
        return fake_response

    fake_models.generate_content.side_effect = _capture

    fake_client = MagicMock()
    fake_client.models = fake_models
    return fake_client


@pytest.fixture
def gemini_client(monkeypatch):
    """Return a GeminiClient instance whose underlying genai client is mocked."""
    captured: dict = {}

    # Patch the genai.Client constructor used inside modules.gemini_client
    with patch("modules.gemini_client.genai.Client", return_value=_fake_client(captured)):
        from modules.gemini_client import GeminiClient
        client = GeminiClient()

    # Re-attach a fresh capturing client (since GeminiClient __init__ already ran)
    client.client = _fake_client(captured)
    return client, captured


@pytest.mark.parametrize(
    "lang_code,expected_substring",
    [
        ("zh-CN", "Mandarin Chinese (Simplified)"),
        ("nl-NL", "Dutch"),
        ("pl-PL", "Polish"),
        ("ru-RU", "Russian"),
        ("pt-BR", "Brazilian Portuguese"),
        ("en-US", "English"),
    ],
)
def test_translate_text_uses_human_language_name(gemini_client, lang_code, expected_substring):
    client, captured = gemini_client
    sample = {"transcription": [{"start_time": 0.0, "end_time": 1.0, "text": "hello"}]}

    client.translate_text(sample, lang_code)

    assert "prompt" in captured, "generate_content was not called"
    assert expected_substring in captured["prompt"], (
        f"Prompt for {lang_code} should contain {expected_substring!r}; got: "
        f"{captured['prompt'][:200]}"
    )
    # And it should NOT contain the bare locale code as the language name
    assert f"to {lang_code}" not in captured["prompt"], (
        f"Prompt should not fall back to bare locale {lang_code!r}"
    )


@pytest.mark.parametrize(
    "lang_code,expected_substring",
    [
        ("zh-CN", "Mandarin Chinese (Simplified)"),
        ("nl-NL", "Dutch"),
        ("pl-PL", "Polish"),
        ("ru-RU", "Russian"),
    ],
)
def test_adjust_translation_for_duration_uses_human_language_name(
    gemini_client, lang_code, expected_substring
):
    client, captured = gemini_client
    sample = {"transcription": [{"start_time": 0.0, "end_time": 2.0, "text": "olá mundo"}]}

    client.adjust_translation_for_duration(
        sample, target_duration=2.0, current_duration=3.0, target_language=lang_code
    )

    assert expected_substring in captured["prompt"], (
        f"Adjustment prompt for {lang_code} should contain {expected_substring!r}"
    )


def test_language_names_constant_is_module_level():
    """The mapping must be a module-level constant so it is shared between
    translate_text and adjust_translation_for_duration (single source of truth)."""
    from modules import gemini_client as gc

    assert hasattr(gc, "LANGUAGE_NAMES"), (
        "GeminiClient must expose a module-level LANGUAGE_NAMES constant"
    )
    assert gc.LANGUAGE_NAMES["zh-CN"] == "Mandarin Chinese (Simplified)"
    assert gc.LANGUAGE_NAMES["nl-NL"] == "Dutch"
    assert gc.LANGUAGE_NAMES["pl-PL"] == "Polish"
    assert gc.LANGUAGE_NAMES["ru-RU"] == "Russian"
