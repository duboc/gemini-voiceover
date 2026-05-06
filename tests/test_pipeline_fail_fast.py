"""Pipeline must abort when TTS produces zero audio files.

Without this guard, a TTS backend that rejects every segment (the live
Mandarin bug) silently moves through sync/concat/mux and ships a video
with a fully-silent audio track. Catastrophic UX.
"""
from __future__ import annotations

import inspect


def test_app_aborts_when_tts_returns_no_audio_files():
    """Source-level check that the pipeline raises if generate_speech() and
    its peers return an empty list. Reading source so we don't have to spin
    up the whole Flask + threading machinery."""
    import app as app_module
    src = inspect.getsource(app_module.process_video)

    # The guard must mention both checking the audio_files list emptiness
    # AND raising/erroring out (not just logging a warning).
    assert "len(audio_files)" in src or "not audio_files" in src, (
        "process_video must check that audio_files is non-empty after TTS"
    )
    assert "TTS produced no audio" in src or "no_audio_files_error" in src.lower() or "TTS returned 0" in src, (
        "process_video must surface a clear error message when 0 TTS files were produced"
    )


def test_no_silent_video_produced_when_tts_fails(monkeypatch):
    """Run process_video against mocked clients where TTS yields nothing,
    and assert the job ends in 'error' status — not 'completed' with a
    silent track."""
    from unittest.mock import MagicMock, patch
    import app as app_module
    from config import Config

    # Mock every collaborator that touches the network or filesystem
    fake_video_info = {"duration": 10.0, "video_codec": "h264"}
    fake_translation = {
        "transcription": [
            {"start_time": 0.0, "end_time": 2.0, "text": "hi"},
            {"start_time": 2.0, "end_time": 4.0, "text": "world"},
        ]
    }

    monkeypatch.setattr(app_module.video_processor, "get_video_info", lambda p: fake_video_info)
    monkeypatch.setattr(app_module.video_processor, "extract_audio", lambda *a, **kw: a[1])
    monkeypatch.setattr(app_module.video_processor, "validate_video_file", lambda p: True)
    monkeypatch.setattr(app_module.video_processor, "combine_audio_segments", MagicMock())
    monkeypatch.setattr(app_module.video_processor, "replace_video_audio", MagicMock())

    monkeypatch.setattr(app_module.gemini_client, "validate_and_regenerate", lambda *a, **kw: fake_translation)
    monkeypatch.setattr(app_module.gemini_client, "translate_text", lambda *a, **kw: fake_translation)

    monkeypatch.setattr(app_module.file_manager, "create_temp_directory", lambda: "/tmp/test_dir")
    monkeypatch.setattr(app_module.file_manager, "cleanup_temp_files", MagicMock())
    monkeypatch.setattr(app_module.file_manager, "save_artifact", MagicMock())
    monkeypatch.setattr(app_module.file_manager, "save_output_file", lambda *a, **kw: "/tmp/out.mp4")

    # Patch os.makedirs to no-op so we don't need real dirs
    monkeypatch.setattr(app_module.os, "makedirs", MagicMock())

    # The critical mock: TTS returns []
    fake_tts = MagicMock()
    fake_tts.generate_speech.return_value = []
    monkeypatch.setattr(app_module, "GoogleTTSClient", lambda: fake_tts)

    # Auto-approve the review step
    pid = "test-fail-fast"
    app_module.processing_status[pid] = {
        "status": "started", "progress": 0, "message": "", "approved": True,
    }

    app_module.process_video(
        pid, "/tmp/in.mp4", "zh-CN", "Zephyr", "gemini",
        "htdemucs", "replace_all", 0.8, "in.mp4",
    )

    final = app_module.processing_status[pid]
    assert final["status"] == "error", (
        f"Expected status='error' when TTS returned 0 files, got {final}"
    )
    # Mux must NOT have been called when no audio was produced
    app_module.video_processor.replace_video_audio.assert_not_called()
