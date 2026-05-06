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
from pathlib import Path

import pytest

# Make project root importable
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))


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
