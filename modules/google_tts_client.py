import os
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from google.cloud import texttospeech
from google.api_core import exceptions
from config import Config

# Set up logging
logger = logging.getLogger(__name__)


class GoogleTTSClient:
    """
    Unified Google Cloud TTS client supporting both:
    1. Standard/Neural voices
    2. Vertex AI Chirp 3 HD voices
    3. Vertex AI Gemini 2.5 TTS
    """
    
    def __init__(self):
        """Initialize Google Cloud Text-to-Speech client"""
        try:
            self.client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud TTS client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud TTS client: {e}")
            raise Exception(f"Google Cloud TTS initialization failed: {str(e)}")
    
    def generate_speech(
        self,
        translation_data: Dict,
        voice_name: str,
        output_dir: str,
        model_name: Optional[str] = None
    ) -> List[str]:
        """
        Generate speech for every segment in translation_data.

        Thin wrapper around generate_speech_segments that requests the full
        index range. Kept for backwards compatibility with existing callers.
        """
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
        """
        Generate speech for a chosen subset of segments only.

        Used by the duration-adjustment loop so that re-shortening one or two
        segments does not force re-synthesis of the entire video.
        """
        try:
            segments = translation_data['transcription']
            valid_indices = sorted({i for i in segment_indices if 0 <= i < len(segments)})

            logger.info(
                f"Generating speech with voice '{voice_name}' (Model: {model_name}) "
                f"for {len(valid_indices)}/{len(segments)} segments (indices={valid_indices})"
            )
            audio_files = []
            
            # Determine language code
            # For Chirp voices: en-US-Chirp3-HD-Charon -> en-US
            # For Gemini voices: usually passed as "Zephyr" etc, need language from data or config
            # But Config.CHIRP3_VOICES keys are like 'en-US-Chirp3-HD-A'.
            
            # If it's a Gemini voice (simple name like "Zephyr"), we need the target language
            target_language = translation_data.get('target_language', 'en-US')
            
            # Construct voice params
            # Note: model_name is supported in newer versions of the library
            # We pass it to the constructor directly as per documentation/examples
            if model_name:
                voice_params = texttospeech.VoiceSelectionParams(
                    language_code=target_language,
                    name=voice_name,
                    model_name=model_name
                )
            else:
                voice_params = texttospeech.VoiceSelectionParams(
                    language_code=target_language,
                    name=voice_name
                )
            
            # Configure audio output
            # Gemini 2.5 and Chirp 3 HD work well with LINEAR16 24kHz
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=24000,
                speaking_rate=Config.TTS_SPEAKING_RATE
            )
            
            results: Dict[int, Optional[str]] = {i: None for i in valid_indices}

            def _process(idx: int, segment: Dict) -> None:
                text = segment['text']
                start_time = segment['start_time']
                end_time = segment['end_time']
                logger.info(
                    f"Generating speech for segment {idx}: '{text[:50]}...' "
                    f"({start_time:.1f}s - {end_time:.1f}s)"
                )
                try:
                    synthesis_input = texttospeech.SynthesisInput(text=text)
                    response = self._synthesize_with_retry(
                        synthesis_input, voice_params, audio_config
                    )
                    filename = f"segment_{idx:03d}_{start_time:.1f}_{end_time:.1f}.wav"
                    filepath = os.path.join(output_dir, filename)
                    with open(filepath, 'wb') as f:
                        f.write(response.audio_content)
                    file_size = os.path.getsize(filepath)
                    logger.info(f"Saved audio segment {idx} to: {filepath} ({file_size} bytes)")
                    results[idx] = filepath
                except Exception as e:
                    logger.error(f"Failed to generate speech for segment {idx}: {e}")

            workers = max(1, Config.TTS_PARALLEL_WORKERS)
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = [pool.submit(_process, i, segments[i]) for i in valid_indices]
                for fut in as_completed(futures):
                    fut.result()  # propagate unexpected exceptions

            audio_files = [results[i] for i in valid_indices if results[i] is not None]
            logger.info(
                f"Google Cloud TTS generation completed: {len(audio_files)} files generated "
                f"(parallel workers={workers})"
            )
            return audio_files
            
        except Exception as e:
            logger.error(f"Google Cloud TTS generation failed: {str(e)}", exc_info=True)
            raise Exception(f"Speech generation failed: {str(e)}")
            
    def _synthesize_with_retry(
        self,
        input_text: texttospeech.SynthesisInput,
        voice: texttospeech.VoiceSelectionParams,
        audio_config: texttospeech.AudioConfig,
        max_retries: Optional[int] = None,
    ) -> texttospeech.SynthesizeSpeechResponse:
        """
        Synthesize speech with retry logic for rate limits and quota errors.

        max_retries defaults to Config.TTS_MAX_RETRIES so operators can tune
        the cap without editing code.
        """
        if max_retries is None:
            max_retries = Config.TTS_MAX_RETRIES

        for attempt in range(max_retries):
            try:
                return self.client.synthesize_speech(
                    request=texttospeech.SynthesizeSpeechRequest(
                        input=input_text,
                        voice=voice,
                        audio_config=audio_config
                    )
                )
            except exceptions.ResourceExhausted as e:
                # Rate limit or quota exceeded
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 2  # Exponential backoff: 2, 4, 8 seconds
                    logger.warning(f"Resource exhausted (attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    logger.error(f"Max retries exceeded for ResourceExhausted: {e}")
                    raise
            except exceptions.ServiceUnavailable as e:
                # Service unavailable (transient)
                if attempt < max_retries - 1:
                    delay = (2 ** attempt) * 1
                    logger.warning(f"Service unavailable (attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                    time.sleep(delay)
                else:
                    raise
            except Exception as e:
                # Other errors - raise immediately
                raise e
                
    def list_available_voices(self, language_code: str = None) -> List[Dict]:
        """
        List available voices for the specified language
        """
        try:
            voices = self.client.list_voices(language_code=language_code)
            
            available_voices = []
            for voice in voices.voices:
                # Filter for Chirp 3 HD or Neural voices if needed
                # For now, returning all or filtering logic can be added here
                available_voices.append({
                    'name': voice.name,
                    'language_codes': voice.language_codes,
                    'ssml_gender': voice.ssml_gender.name
                })
            
            logger.info(f"Found {len(available_voices)} voices for language: {language_code}")
            return available_voices
            
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
    
    def test_voice(self, voice_name: str, language_code: str = "en-US", model_name: str = None) -> bool:
        """
        Test if a voice is available and working
        """
        try:
            test_text = "Hello, this is a test."
            synthesis_input = texttospeech.SynthesisInput(text=test_text)
            
            if model_name:
                voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=voice_name,
                    model_name=model_name
                )
            else:
                voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=voice_name
                )
                
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                sample_rate_hertz=24000
            )
            
            self.client.synthesize_speech(
                request=texttospeech.SynthesizeSpeechRequest(
                    input=synthesis_input,
                    voice=voice,
                    audio_config=audio_config
                )
            )
            return True
            
        except Exception as e:
            logger.error(f"Voice {voice_name} test failed: {e}")
            return False

    def generate_speech_with_duration_fit(
        self,
        translation_data: Dict,
        voice_name: str,
        output_dir: str,
        target_duration: float,
        model_name: Optional[str] = None
    ) -> List[str]:
        """
        Simplified version of duration fitting that just generates normal speech for now.
        The advanced duration fitting logic from Gemini TTS client relying on Gemini API 
        text adjustments is preserved in the App logic or can be ported if needed, 
        but for strict TTS migration, we generate the audio first.
        """
        # Just delegate to generate_speech for now
        return self.generate_speech(translation_data, voice_name, output_dir, model_name)
