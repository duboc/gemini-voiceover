"""Cloud TTS uses 'cmn-CN' for Mandarin, not 'zh-CN'.

The deployed config generated voice names like zh-CN-Chirp3-HD-Zephyr,
which the Cloud TTS service does not recognise. Fix is twofold:

1. CHIRP3_VOICES for the user-facing 'zh-CN' key must list voices with
   the 'cmn-CN-Chirp3-HD-…' prefix that the API actually accepts.
2. When dispatching a Cloud TTS call for a job whose target_language is
   'zh-CN', the language_code on the wire must become 'cmn-CN'.
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest


def test_chirp3_voices_for_zh_cn_use_cmn_prefix():
    from config import Config

    voices = Config.CHIRP3_VOICES.get("zh-CN", {})
    assert voices, "Mandarin must have Chirp 3 voices configured"
    for voice_id in voices:
        assert voice_id.startswith("cmn-CN-Chirp3-HD-"), (
            f"Mandarin Chirp 3 voice id should be cmn-CN-prefixed; got {voice_id!r}"
        )


def test_default_chirp3_voice_for_zh_cn_is_cmn_zephyr():
    from config import Config

    assert Config.DEFAULT_CHIRP3_VOICES["zh-CN"] == "cmn-CN-Chirp3-HD-Zephyr"


def test_other_language_chirp3_voices_unchanged():
    """Only Mandarin gets the cmn- override; everything else must keep
    its locale prefix as-is."""
    from config import Config

    for lang in ["en-US", "pt-BR", "ja-JP", "fr-FR", "de-DE"]:
        for voice_id in Config.CHIRP3_VOICES.get(lang, {}):
            assert voice_id.startswith(f"{lang}-Chirp3-HD-"), (
                f"{lang} voice id should keep its locale prefix; got {voice_id!r}"
            )


def test_cloud_tts_call_translates_zh_cn_to_cmn_cn(tmp_path, monkeypatch):
    """When the job target_language is 'zh-CN' and we route through Cloud
    TTS (Chirp 3 path), the request's language_code must be 'cmn-CN'."""
    from modules.google_tts_client import GoogleTTSClient
    import modules.google_tts_client as gtc

    captured = {}

    def _fake_synthesize(*args, **kwargs):
        req = kwargs.get("request") or args[0]
        captured["language_code"] = req.voice.language_code
        captured["voice_name"] = req.voice.name
        resp = MagicMock()
        resp.audio_content = b"FAKE"
        return resp

    client = GoogleTTSClient()
    client.client = MagicMock()
    client.client.synthesize_speech.side_effect = _fake_synthesize

    # Patch VoiceSelectionParams to a simple namespace so we can read fields
    class _VSP:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
    monkeypatch.setattr(gtc.texttospeech, "VoiceSelectionParams", _VSP)

    class _SR:
        def __init__(self, input, voice, audio_config):
            self.voice = voice
    monkeypatch.setattr(gtc.texttospeech, "SynthesizeSpeechRequest", _SR)

    translation = {
        "target_language": "zh-CN",
        "transcription": [{"start_time": 0.0, "end_time": 1.0, "text": "你好"}],
    }
    files = client.generate_speech(translation, "cmn-CN-Chirp3-HD-Zephyr", str(tmp_path))

    assert len(files) == 1
    assert captured["language_code"] == "cmn-CN", (
        f"Expected language_code='cmn-CN' on wire (Cloud TTS quirk); got {captured['language_code']!r}"
    )
    assert captured["voice_name"] == "cmn-CN-Chirp3-HD-Zephyr"


def test_zh_tw_also_maps_to_cmn_tw():
    from modules.google_tts_client import LANGUAGE_CODE_FOR_CLOUD_TTS

    assert LANGUAGE_CODE_FOR_CLOUD_TTS["zh-CN"] == "cmn-CN"
    assert LANGUAGE_CODE_FOR_CLOUD_TTS["zh-TW"] == "cmn-TW"
