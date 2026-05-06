"""TTS client that routes between two distinct Google APIs by voice name.

- Bare-persona names (e.g. 'Zephyr', 'Puck', 'Kore') → native Gemini API
  via ``genai.Client().models.generate_content`` with audio response
  modality. Language is auto-detected from the input text. Output is
  raw PCM that we wrap in a WAV header for downstream FFmpeg/concat.

- Lang-prefixed names (e.g. 'cmn-CN-Chirp3-HD-Zephyr', 'en-US-Standard-A')
  → Google Cloud Text-to-Speech REST API via the
  ``google-cloud-texttospeech`` SDK.

Routing the wrong way produces ``400 language code … not supported``
errors, which is exactly the bug that shipped a silent video on the
first Mandarin test.
"""
from __future__ import annotations

import io
import logging
import os
import time
import wave
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, List, Optional

from google import genai
from google.genai import types as genai_types
from google.cloud import texttospeech
from google.api_core import exceptions

from config import Config

logger = logging.getLogger(__name__)


# Cloud TTS uses BCP-47 macrolanguage codes that don't always match the
# locale codes we accept from the UI. Mandarin (Simplified) is the only
# active mismatch today; add more as we validate them against the
# texttospeech voices/list endpoint.
LANGUAGE_CODE_FOR_CLOUD_TTS = {
    'zh-CN': 'cmn-CN',
    'zh-TW': 'cmn-TW',
}


def is_gemini_voice(voice_name: str) -> bool:
    """Return True for bare-persona names that route through the native
    Gemini API; False for any lang-prefixed Cloud TTS voice."""
    if not voice_name:
        return False
    return ("-Chirp3-HD-" not in voice_name
            and "-Standard-" not in voice_name
            and "-Wavenet-" not in voice_name
            and "-Neural2-" not in voice_name
            and "-Studio-" not in voice_name)


def pcm_to_wav_bytes(pcm: bytes, sample_rate: int = 24000, channels: int = 1, sample_width: int = 2) -> bytes:
    """Wrap raw PCM in a WAV header in-memory. Gemini TTS returns raw PCM
    at 24 kHz mono 16-bit by default, but downstream FFmpeg/concat needs
    a real WAV file."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(sample_width)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm)
    return buf.getvalue()


class GoogleTTSClient:
    """Unified client routing between native Gemini TTS and Cloud TTS."""

    def __init__(self):
        try:
            self.client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud TTS client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud TTS client: {e}")
            raise Exception(f"Google Cloud TTS initialization failed: {str(e)}")

        self._gemini_client: Optional[genai.Client] = None  # lazy

    def _get_gemini_client(self) -> genai.Client:
        """Lazily build a Vertex AI genai client. Reused across calls."""
        if self._gemini_client is None:
            location = os.getenv('GOOGLE_CLOUD_LOCATION', 'us-central1')
            project = Config.GOOGLE_CLOUD_PROJECT
            if not project:
                import google.auth
                _, project = google.auth.default()
            logger.info(f"Initializing Gemini TTS client (Vertex AI, project={project}, location={location})")
            self._gemini_client = genai.Client(vertexai=True, project=project, location=location)
        return self._gemini_client

    # --- Public API ---------------------------------------------------------

    def generate_speech(
        self,
        translation_data: Dict,
        voice_name: str,
        output_dir: str,
        model_name: Optional[str] = None,
    ) -> List[str]:
        """Generate speech for every segment in translation_data."""
        n = len(translation_data['transcription'])
        return self.generate_speech_segments(
            translation_data, voice_name, output_dir,
            segment_indices=list(range(n)), model_name=model_name,
        )

    def generate_speech_segments(
        self,
        translation_data: Dict,
        voice_name: str,
        output_dir: str,
        segment_indices: List[int],
        model_name: Optional[str] = None,
    ) -> List[str]:
        """Generate speech for the given subset of segment indices.

        Routes per-call based on voice_name shape so the same client can
        serve both backends without the caller knowing.
        """
        try:
            segments = translation_data['transcription']
            valid_indices = sorted({i for i in segment_indices if 0 <= i < len(segments)})

            backend = "gemini-native" if is_gemini_voice(voice_name) else "cloud-tts"
            logger.info(
                f"Generating speech via {backend} with voice='{voice_name}' "
                f"(model={model_name}) for {len(valid_indices)}/{len(segments)} segments"
            )

            results: Dict[int, Optional[str]] = {i: None for i in valid_indices}
            target_language = translation_data.get('target_language', 'en-US')

            def _process(idx: int) -> None:
                segment = segments[idx]
                text = segment['text']
                start_time = segment['start_time']
                end_time = segment['end_time']
                logger.info(
                    f"[{backend}] segment {idx}: '{text[:50]}…' "
                    f"({start_time:.1f}s–{end_time:.1f}s)"
                )
                try:
                    if backend == "gemini-native":
                        wav_bytes = self._synthesize_gemini_native(
                            text, voice_name, model_name or Config.GEMINI_TTS_MODEL,
                        )
                    else:
                        wav_bytes = self._synthesize_cloud_tts(
                            text, voice_name, target_language, model_name,
                        )

                    filename = f"segment_{idx:03d}_{start_time:.1f}_{end_time:.1f}.wav"
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(wav_bytes)
                    logger.info(f"Saved segment {idx}: {filepath} ({os.path.getsize(filepath)} bytes)")
                    results[idx] = filepath
                except Exception as e:
                    logger.error(f"Failed to generate speech for segment {idx}: {e}")

            workers = max(1, Config.TTS_PARALLEL_WORKERS)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_process, i) for i in valid_indices]
                for fut in as_completed(futures):
                    fut.result()

            audio_files = [results[i] for i in valid_indices if results[i] is not None]
            logger.info(
                f"TTS generation completed: {len(audio_files)}/{len(valid_indices)} files "
                f"(backend={backend}, workers={workers})"
            )
            return audio_files

        except Exception as e:
            logger.error(f"TTS generation failed: {e}", exc_info=True)
            raise Exception(f"Speech generation failed: {str(e)}")

    # --- Backend-specific synth --------------------------------------------

    def _synthesize_gemini_native(self, text: str, voice_name: str, model_name: str) -> bytes:
        """Call the native Gemini API (audio modality) and return WAV bytes.

        Language is auto-detected from the input text — no language code
        is passed, by design.
        """
        client = self._get_gemini_client()
        config = genai_types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=genai_types.SpeechConfig(
                voice_config=genai_types.VoiceConfig(
                    prebuilt_voice_config=genai_types.PrebuiltVoiceConfig(
                        voice_name=voice_name,
                    )
                )
            ),
        )
        response = self._gemini_call_with_retry(client, model_name, text, config)
        pcm = response.candidates[0].content.parts[0].inline_data.data
        return pcm_to_wav_bytes(pcm, sample_rate=24000, channels=1, sample_width=2)

    def _synthesize_cloud_tts(
        self, text: str, voice_name: str, target_language: str, model_name: Optional[str],
    ) -> bytes:
        """Call Google Cloud TTS (Chirp 3 HD, Standard, Wavenet, Neural2)
        and return audio bytes (which are already wrapped — LINEAR16/WAV)."""
        # Apply BCP-47 mapping (zh-CN → cmn-CN for Cloud TTS)
        cloud_lang = LANGUAGE_CODE_FOR_CLOUD_TTS.get(target_language, target_language)

        kwargs = dict(language_code=cloud_lang, name=voice_name)
        if model_name:
            kwargs['model_name'] = model_name
        voice_params = texttospeech.VoiceSelectionParams(**kwargs)

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16,
            sample_rate_hertz=24000,
            speaking_rate=Config.TTS_SPEAKING_RATE,
        )
        response = self._synthesize_with_retry(
            texttospeech.SynthesisInput(text=text), voice_params, audio_config,
        )
        return response.audio_content

    # --- Retry wrappers ----------------------------------------------------

    def _gemini_call_with_retry(self, client, model: str, text: str, config, max_retries: Optional[int] = None):
        """Retry the native Gemini generate_content call on transient errors."""
        if max_retries is None:
            max_retries = Config.TTS_MAX_RETRIES

        last_exc: Optional[Exception] = None
        for attempt in range(max_retries):
            try:
                return client.models.generate_content(
                    model=model, contents=text, config=config,
                )
            except Exception as e:
                last_exc = e
                # Heuristic: retry on rate-limit/transient strings; raise on validation errors
                msg = str(e).lower()
                transient = any(s in msg for s in ("rate", "exhaust", "unavailable", "deadline", "timeout", "503", "429"))
                if attempt < max_retries - 1 and transient:
                    delay = (2 ** attempt) * 2
                    logger.warning(f"Gemini TTS transient error attempt {attempt+1}/{max_retries}; sleep {delay}s: {e}")
                    time.sleep(delay)
                else:
                    raise
        # pragma: no cover - loop always raises or returns
        raise last_exc  # type: ignore[misc]

    def _synthesize_with_retry(
        self,
        input_text: texttospeech.SynthesisInput,
        voice: texttospeech.VoiceSelectionParams,
        audio_config: texttospeech.AudioConfig,
        max_retries: Optional[int] = None,
    ) -> texttospeech.SynthesizeSpeechResponse:
        """Cloud TTS retry wrapper. Default cap = Config.TTS_MAX_RETRIES."""
        if max_retries is None:
            max_retries = Config.TTS_MAX_RETRIES

        for attempt in range(max_retries):
            try:
                return self.client.synthesize_speech(
                    request=texttospeech.SynthesizeSpeechRequest(
                        input=input_text, voice=voice, audio_config=audio_config,
                    )
                )
            except exceptions.ResourceExhausted as e:
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 2
                    logger.warning(f"Resource exhausted (attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Max retries exceeded for ResourceExhausted: {e}")
                    raise
            except exceptions.ServiceUnavailable as e:
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 1
                    logger.warning(f"Service unavailable (attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise
            except Exception:
                raise

    # --- Misc helpers (used elsewhere) -------------------------------------

    def list_available_voices(self, language_code: str = None) -> List[Dict]:
        try:
            voices = self.client.list_voices(language_code=language_code)
            return [
                {
                    'name': v.name,
                    'language_codes': v.language_codes,
                    'ssml_gender': v.ssml_gender.name,
                }
                for v in voices.voices
            ]
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []

    def generate_speech_with_duration_fit(
        self,
        translation_data: Dict,
        voice_name: str,
        output_dir: str,
        target_duration: float,
        model_name: Optional[str] = None,
    ) -> List[str]:
        """Backwards-compat shim. The duration-fit logic lives in app.py."""
        return self.generate_speech(translation_data, voice_name, output_dir, model_name)
