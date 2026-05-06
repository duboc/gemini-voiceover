"""Shared pytest fixtures for the test suite.

Tests are designed to be runnable without a local ffmpeg binary:
fixtures here build minimal valid WAV bytes in pure Python so that
tests can write/read real files and assert on subprocess/ffmpeg-python
*calls* via mocks, rather than depending on ffmpeg execution.
"""
from __future__ import annotations

import os
import shutil
import struct
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Make project root importable
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))


# Stub heavy / system-dependent third-party modules so unit tests can import
# project code without requiring the full runtime (ffmpeg-python, demucs, torch,
# google-cloud-texttospeech, google-cloud-storage). Tests that need real
# behaviour from these modules can still patch at finer granularity.
def _ensure_stub(name: str, attrs: dict | None = None) -> None:
    if name in sys.modules:
        return
    mod = types.ModuleType(name)
    for k, v in (attrs or {}).items():
        setattr(mod, k, v)
    sys.modules[name] = mod


# ffmpeg-python: expose Error class + chainable mock so module imports succeed
_ffmpeg_stub = types.ModuleType("ffmpeg")
_ffmpeg_stub.Error = type("Error", (Exception,), {})
_ffmpeg_stub.input = MagicMock(return_value=MagicMock())
_ffmpeg_stub.output = MagicMock(return_value=MagicMock())
_ffmpeg_stub.probe = MagicMock(return_value={"streams": [], "format": {"duration": "1.0"}})
_ffmpeg_stub.run = MagicMock()
sys.modules.setdefault("ffmpeg", _ffmpeg_stub)

# google-cloud-texttospeech: stub minimal classes used at import time
_tts_stub = types.ModuleType("google.cloud.texttospeech")
_tts_stub.TextToSpeechClient = MagicMock
_tts_stub.SynthesisInput = MagicMock
_tts_stub.VoiceSelectionParams = MagicMock
_tts_stub.AudioConfig = MagicMock
_tts_stub.AudioEncoding = types.SimpleNamespace(LINEAR16="LINEAR16")
_tts_stub.SynthesizeSpeechRequest = MagicMock
_tts_stub.SynthesizeSpeechResponse = MagicMock
sys.modules.setdefault("google.cloud.texttospeech", _tts_stub)

# google.api_core.exceptions: classes referenced for retry handling
_api_core_exc = types.ModuleType("google.api_core.exceptions")
_api_core_exc.ResourceExhausted = type("ResourceExhausted", (Exception,), {})
_api_core_exc.ServiceUnavailable = type("ServiceUnavailable", (Exception,), {})
sys.modules.setdefault("google.api_core", types.ModuleType("google.api_core"))
sys.modules.setdefault("google.api_core.exceptions", _api_core_exc)

# google-cloud-storage: only used by GCSClient, which is loaded lazily
_gcs_stub = types.ModuleType("google.cloud.storage")
_gcs_stub.Client = MagicMock
sys.modules.setdefault("google.cloud.storage", _gcs_stub)

# Heavy ML / audio numerics: stub so AudioSeparator imports succeed.
for mod_name in ("numpy", "torch", "torchaudio", "soundfile", "scipy", "librosa"):
    sys.modules.setdefault(mod_name, MagicMock())


def _build_wav(sample_rate: int = 24000, channels: int = 1, duration_s: float = 1.0) -> bytes:
    """Build a valid PCM s16le WAV file as raw bytes (silent)."""
    num_samples = int(sample_rate * duration_s)
    bytes_per_sample = 2
    data_size = num_samples * channels * bytes_per_sample
    byte_rate = sample_rate * channels * bytes_per_sample
    block_align = channels * bytes_per_sample

    header = b"RIFF"
    header += struct.pack("<I", 36 + data_size)
    header += b"WAVE"
    header += b"fmt "
    header += struct.pack("<I", 16)              # fmt chunk size
    header += struct.pack("<H", 1)               # audio format = PCM
    header += struct.pack("<H", channels)
    header += struct.pack("<I", sample_rate)
    header += struct.pack("<I", byte_rate)
    header += struct.pack("<H", block_align)
    header += struct.pack("<H", 16)              # bits per sample
    header += b"data"
    header += struct.pack("<I", data_size)

    silence = b"\x00\x00" * num_samples * channels
    return header + silence


@pytest.fixture
def wav_bytes_factory():
    """Return a callable that builds WAV bytes with given params."""
    return _build_wav


@pytest.fixture
def make_wav_file(tmp_path, wav_bytes_factory):
    """Return a callable that writes a silent WAV to tmp_path and returns its path."""
    def _make(name: str = "audio.wav", duration_s: float = 1.0, sample_rate: int = 24000, channels: int = 1) -> str:
        p = tmp_path / name
        p.write_bytes(wav_bytes_factory(sample_rate=sample_rate, channels=channels, duration_s=duration_s))
        return str(p)
    return _make


@pytest.fixture
def has_ffmpeg() -> bool:
    """True if ffmpeg binary is available on PATH (used to skip integration tests)."""
    return shutil.which("ffmpeg") is not None


@pytest.fixture(autouse=True)
def _isolate_env(monkeypatch, tmp_path):
    """Avoid tests touching real GCS / Vertex by setting safe defaults."""
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("GOOGLE_CLOUD_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "test-project"))
    monkeypatch.setenv("UPLOAD_FOLDER", str(tmp_path / "uploads"))
    monkeypatch.setenv("TEMP_FOLDER", str(tmp_path / "temp"))
    monkeypatch.setenv("OUTPUT_FOLDER", str(tmp_path / "outputs"))
    yield
