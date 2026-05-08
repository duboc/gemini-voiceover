import os
import json
import base64
import mimetypes
import struct
import logging
from typing import Dict, List, Optional, Tuple
from google import genai
from google.genai import types
from config import Config
from modules.error_handler import GeminiErrorHandler

# Set up logging
logger = logging.getLogger(__name__)


# Single source of truth for translating BCP-47 codes to natural language
# names sent to Gemini in prompts. Keep aligned with Config.SUPPORTED_LANGUAGES.
LANGUAGE_NAMES = {
    'en-US': 'English',
    'pt-BR': 'Brazilian Portuguese',
    'es-ES': 'Spanish',
    'es': 'Spanish',
    'fr-FR': 'French',
    'de-DE': 'German',
    'it-IT': 'Italian',
    'ja-JP': 'Japanese',
    'ko-KR': 'Korean',
    'nl-NL': 'Dutch',
    'pl-PL': 'Polish',
    'ru-RU': 'Russian',
    'zh-CN': 'Mandarin Chinese (Simplified)',
}


class GeminiClient:
    def __init__(self):
        """Initialize Gemini Client using Vertex AI (ADC)"""
        try:
            location = Config.GEMINI_API_LOCATION
            project = Config.GOOGLE_CLOUD_PROJECT
            
            if not project:
                # Try to get from default environment if not in Config
                import google.auth
                _, project = google.auth.default()
            
            logger.info(f"Initializing Gemini Client with Vertex AI (Project: {project}, Location: {location})")
            
            self.client = genai.Client(
                vertexai=True,
                project=project,
                location=location
            )
        except Exception as e:
            logger.error(f"Failed to initialize Gemini Client with Vertex AI: {e}")
            raise Exception(f"Gemini Client initialization failed: {str(e)}")
    
    @staticmethod
    def _build_thinking_config(model_name: str):
        """Return a ThinkingConfig that minimises reasoning overhead.

        Gemini 3.x uses ``thinking_level``; 2.5 uses ``thinking_budget``.
        Non-thinking models (2.0, 1.x) return None so the caller can omit
        the parameter entirely.
        """
        try:
            if model_name.startswith('gemini-3'):
                return types.ThinkingConfig(
                    thinking_level=types.ThinkingLevel.MINIMAL,
                )
            if 'gemini-2.5' in model_name:
                return types.ThinkingConfig(thinking_budget=0)
        except Exception as e:
            logger.warning(f"Could not build thinking config for {model_name}: {e}")
        return None

    def transcribe_audio(self, audio_file_path: str, video_file_path: str = None) -> Dict:
        """
        Transcribe audio file with optional video context for better accuracy
        
        Args:
            audio_file_path: Path to audio file
            video_file_path: Optional path to video file for visual context
            
        Returns:
            Dictionary with timestamped transcription
        """
        try:
            # Read audio file
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
            
            mime_type = mimetypes.guess_type(audio_file_path)[0] or 'audio/wav'
            
            # Define response schema for controlled generation
            response_schema = {
                "type": "OBJECT",
                "properties": {
                    "transcription": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "start_time": {"type": "NUMBER"},
                                "end_time": {"type": "NUMBER"},
                                "text": {"type": "STRING"}
                            },
                            "required": ["start_time", "end_time", "text"]
                        }
                    }
                },
                "required": ["transcription"]
            }
            
            # Create prompt for timestamped transcription
            prompt = ("Please transcribe this audio/video file and provide timestamped segments. "
                     "Include precise start_time and end_time in seconds for each segment of speech. "
                     "Break the transcription into natural speech segments (typically 3-10 seconds each). "
                     "Ensure all text is accurately transcribed.")
            
            # Build content parts
            parts = [types.Part.from_text(text=prompt)]
            
            # Add video if available for better context
            if video_file_path and os.path.exists(video_file_path):
                logger.info("Adding video context for improved transcription accuracy")
                with open(video_file_path, 'rb') as f:
                    video_data = f.read()
                video_mime = mimetypes.guess_type(video_file_path)[0] or 'video/mp4'
                parts.append(types.Part.from_bytes(data=video_data, mime_type=video_mime))
            else:
                # Add audio
                parts.append(types.Part.from_bytes(data=audio_data, mime_type=mime_type))
            
            contents = [
                types.Content(
                    role="user",
                    parts=parts,
                ),
            ]
            
            # Use controlled generation with response schema.
            # max_output_tokens must be set high to avoid truncation on long
            # videos. Thinking is minimised because transcription is a
            # perception task, not a reasoning task — thinking tokens would
            # otherwise consume the output budget and truncate the JSON.
            thinking = self._build_thinking_config(Config.TRANSCRIPTION_MODEL)
            config = types.GenerateContentConfig(
                temperature=0.1,
                max_output_tokens=65536,
                response_mime_type="application/json",
                response_schema=response_schema,
                **({'thinking_config': thinking} if thinking else {}),
            )

            response = self.client.models.generate_content(
                model=Config.TRANSCRIPTION_MODEL,
                contents=contents,
                config=config,
            )

            # Warn when the model stops early — likely output-token exhaustion
            finish = getattr(response.candidates[0], 'finish_reason', None)
            if finish and str(finish) not in ('STOP', 'FinishReason.STOP', '1'):
                logger.warning(
                    f"Transcription finished with reason={finish}; "
                    f"output may be truncated — consider raising max_output_tokens"
                )

            # Parse JSON response (should be clean with schema)
            transcription_data = json.loads(response.text)
            
            # Add confidence score if available
            transcription_data['quality_score'] = self._estimate_transcription_quality(transcription_data)
            
            return transcription_data
            
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing failed even with schema: {e}")
            # Check if response exists before accessing it
            if 'response' in locals():
                logger.error(f"Response text: {response.text[:1000]}...")
                # Fallback to manual parsing if schema didn't work
                transcription_data = self._parse_json_response(response.text, "transcription")
                transcription_data['quality_score'] = self._estimate_transcription_quality(transcription_data)
                return transcription_data
            else:
                raise
        except Exception as e:
            GeminiErrorHandler.handle_gemini_error(e, "Transcription")
    
    def translate_text(self, transcription_data: Dict, target_language: str) -> Dict:
        """Translate transcription data to target language with controlled generation"""
        try:
            target_lang_name = LANGUAGE_NAMES.get(target_language, target_language)
            
            # Define response schema for controlled generation
            response_schema = {
                "type": "OBJECT",
                "properties": {
                    "transcription": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "start_time": {"type": "NUMBER"},
                                "end_time": {"type": "NUMBER"},
                                "text": {"type": "STRING"}
                            },
                            "required": ["start_time", "end_time", "text"]
                        }
                    }
                },
                "required": ["transcription"]
            }
            
            prompt = (f"Translate the following transcription segments to {target_lang_name}. "
                     f"Keep the EXACT same start_time and end_time values. "
                     f"Only translate the 'text' field content. "
                     f"Preserve natural language flow and meaning.\n\n"
                     f"Input transcription:\n{json.dumps(transcription_data, indent=2, ensure_ascii=False)}")
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            
            thinking = self._build_thinking_config(Config.TRANSLATION_MODEL)
            config = types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=65536,
                response_mime_type="application/json",
                response_schema=response_schema,
                **({'thinking_config': thinking} if thinking else {}),
            )

            response = self.client.models.generate_content(
                model=Config.TRANSLATION_MODEL,
                contents=contents,
                config=config,
            )

            finish = getattr(response.candidates[0], 'finish_reason', None)
            if finish and str(finish) not in ('STOP', 'FinishReason.STOP', '1'):
                logger.warning(
                    f"Translation finished with reason={finish}; "
                    f"output may be truncated"
                )

            # Parse JSON response (should be clean with schema)
            translation_data = json.loads(response.text)
            return translation_data
            
        except json.JSONDecodeError as e:
            logger.error(f"Translation JSON parsing failed even with schema: {e}")
            if 'response' in locals():
                logger.error(f"Response text: {response.text[:1000]}...")
                # Fallback to manual parsing if schema didn't work
                translation_data = self._parse_json_response(response.text, "translation")
                return translation_data
            else:
                raise
        except Exception as e:
            GeminiErrorHandler.handle_gemini_error(e, "Translation")
    
    # Note: generate_speech method removed as it is now handled by GoogleTTSClient (Vertex AI)
    
    def _parse_json_response(self, response_text: str, operation: str) -> Dict:
        """Parse JSON response with error handling and cleanup"""
        try:
            logger.info(f"Parsing {operation} response ({len(response_text)} characters)")
            
            # First, try direct JSON parsing
            try:
                return json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Direct JSON parsing failed: {e}")
                logger.info(f"Raw response: {response_text[:500]}...")
            
            # Clean up common JSON issues
            cleaned_text = self._clean_json_response(response_text)
            
            try:
                return json.loads(cleaned_text)
            except json.JSONDecodeError as e:
                logger.warning(f"Cleaned JSON parsing failed: {e}")
                logger.info(f"Cleaned response: {cleaned_text[:500]}...")
            
            # Try to extract JSON from markdown code blocks
            json_text = self._extract_json_from_markdown(response_text)
            if json_text:
                try:
                    return json.loads(json_text)
                except json.JSONDecodeError as e:
                    logger.warning(f"Markdown JSON parsing failed: {e}")
            
            # Last resort: try to fix common JSON issues
            fixed_text = self._fix_common_json_issues(response_text)
            try:
                return json.loads(fixed_text)
            except json.JSONDecodeError as e:
                logger.error(f"All JSON parsing attempts failed: {e}")
                logger.error(f"Final attempt text: {fixed_text[:500]}...")
                
                # Create a fallback structure
                if operation == "transcription":
                    logger.warning("Creating fallback transcription structure")
                    return {
                        "transcription": [
                            {
                                "start_time": 0.0,
                                "end_time": 10.0,
                                "text": "Audio transcription failed - using fallback"
                            }
                        ]
                    }
                else:
                    raise Exception(f"Failed to parse {operation} JSON response")
                    
        except Exception as e:
            logger.error(f"JSON parsing error for {operation}: {e}")
            raise Exception(f"Failed to parse {operation} response: {str(e)}")
    
    def _clean_json_response(self, text: str) -> str:
        """Clean common JSON formatting issues while preserving structure"""
        import re
        
        # Remove any text before the first {
        start_idx = text.find('{')
        if start_idx > 0:
            text = text[start_idx:]
        
        # Remove any text after the last }
        end_idx = text.rfind('}')
        if end_idx > 0:
            text = text[:end_idx + 1]
        
        # Fix trailing commas (but preserve structure)
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        # Remove any markdown artifacts
        text = re.sub(r'```json\s*', '', text)
        text = re.sub(r'```\s*', '', text)
        
        return text.strip()
    
    def _extract_json_from_markdown(self, text: str) -> Optional[str]:
        """Extract JSON from markdown code blocks"""
        import re
        
        # Look for JSON in code blocks
        patterns = [
            r'```json\s*(.*?)\s*```',
            r'```\s*(.*?)\s*```',
            r'`(.*?)`'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL)
            if match:
                json_text = match.group(1).strip()
                if json_text.startswith('{') and json_text.endswith('}'):
                    return json_text
        
        return None
    
    def _fix_common_json_issues(self, text: str) -> str:
        """Fix common JSON formatting issues"""
        import re
        
        # Remove any non-JSON text at the beginning
        start_idx = text.find('{')
        if start_idx > 0:
            text = text[start_idx:]
        
        # Remove any non-JSON text at the end
        end_idx = text.rfind('}')
        if end_idx > 0:
            text = text[:end_idx + 1]
        
        # Fix unescaped quotes in strings
        text = re.sub(r'(?<!\\)"(?=.*")', r'\\"', text)
        
        # Fix missing commas between objects
        text = re.sub(r'}\s*{', r'},{', text)
        
        # Fix missing commas between array elements
        text = re.sub(r']\s*\[', r'],[', text)
        
        # Remove trailing commas
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
        return text.strip()
    
    def _estimate_transcription_quality(self, transcription_data: Dict) -> float:
        """
        Estimate quality of transcription based on various factors
        
        Args:
            transcription_data: Transcription dictionary
            
        Returns:
            Quality score between 0.0 and 1.0
        """
        try:
            if 'transcription' not in transcription_data:
                return 0.0
            
            segments = transcription_data['transcription']
            if not segments:
                return 0.0
            
            # Factors for quality estimation
            score = 1.0
            
            # Check for valid timestamps
            has_valid_timestamps = all(
                'start_time' in seg and 'end_time' in seg and
                seg['end_time'] > seg['start_time']
                for seg in segments
            )
            if not has_valid_timestamps:
                score *= 0.5
            
            # Check for text content
            avg_text_length = sum(len(seg.get('text', '')) for seg in segments) / len(segments)
            if avg_text_length < 10:
                score *= 0.7
            
            # Check for reasonable segment duration
            avg_duration = sum(seg['end_time'] - seg['start_time'] for seg in segments) / len(segments)
            if avg_duration < 1 or avg_duration > 30:
                score *= 0.8
            
            return min(1.0, max(0.0, score))
            
        except Exception as e:
            logger.warning(f"Failed to estimate quality: {e}")
            return 0.5
    
    def validate_and_regenerate(
        self,
        audio_file_path: str,
        video_file_path: str = None,
        min_quality: float = 0.6,
        max_attempts: int = 2
    ) -> Dict:
        """
        Transcribe with quality validation and automatic regeneration
        
        Args:
            audio_file_path: Path to audio file
            video_file_path: Optional path to video file
            min_quality: Minimum acceptable quality score
            max_attempts: Maximum number of attempts
            
        Returns:
            Best transcription result
        """
        best_result = None
        best_quality = 0.0
        
        for attempt in range(max_attempts):
            logger.info(f"Transcription attempt {attempt + 1}/{max_attempts}")
            
            try:
                result = self.transcribe_audio(audio_file_path, video_file_path)
                quality = result.get('quality_score', 0.0)
                
                logger.info(f"Attempt {attempt + 1} quality score: {quality:.2f}")
                
                if quality > best_quality:
                    best_result = result
                    best_quality = quality
                
                if quality >= min_quality:
                    logger.info(f"Quality threshold met: {quality:.2f} >= {min_quality:.2f}")
                    return result
                    
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                continue
        
        if best_result:
            logger.info(f"Returning best result with quality: {best_quality:.2f}")
            return best_result
        else:
            raise Exception("All transcription attempts failed")
    
    def adjust_translation_for_duration(
        self,
        translation_data: Dict,
        target_duration: float,
        current_duration: float,
        target_language: str
    ) -> Dict:
        """
        Adjust translation text length to fit within target duration using Gemini
        
        Args:
            translation_data: Original translation data
            target_duration: Target duration in seconds
            current_duration: Current estimated duration in seconds
            target_language: Target language code
            
        Returns:
            Adjusted translation data
        """
        try:
            ratio = current_duration / target_duration
            reduction_percent = (ratio - 1.0) * 100
            
            logger.info(f"Adjusting translation: current={current_duration:.1f}s, target={target_duration:.1f}s, reduction needed={reduction_percent:.1f}%")

            lang_name = LANGUAGE_NAMES.get(target_language, target_language)
            
            # Define response schema
            response_schema = {
                "type": "OBJECT",
                "properties": {
                    "transcription": {
                        "type": "ARRAY",
                        "items": {
                            "type": "OBJECT",
                            "properties": {
                                "start_time": {"type": "NUMBER"},
                                "end_time": {"type": "NUMBER"},
                                "text": {"type": "STRING"}
                            },
                            "required": ["start_time", "end_time", "text"]
                        }
                    }
                },
                "required": ["transcription"]
            }
            
            prompt = (
                f"The following {lang_name} translation needs to be shortened by approximately {reduction_percent:.0f}% "
                f"to fit within the original video duration.\n\n"
                f"Instructions:\n"
                f"1. Shorten the text in each segment while preserving the core meaning\n"
                f"2. Remove unnecessary words, redundancies, and filler phrases\n"
                f"3. Keep the EXACT same start_time and end_time for each segment\n"
                f"4. Maintain the natural flow and readability in {lang_name}\n"
                f"5. Prioritize keeping important information over minor details\n\n"
                f"Original translation:\n{json.dumps(translation_data, indent=2, ensure_ascii=False)}\n\n"
                f"Return the shortened version maintaining the exact JSON structure."
            )
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            
            thinking = self._build_thinking_config(Config.TRANSLATION_MODEL)
            config = types.GenerateContentConfig(
                temperature=0.3,
                max_output_tokens=65536,
                response_mime_type="application/json",
                response_schema=response_schema,
                **({'thinking_config': thinking} if thinking else {}),
            )

            response = self.client.models.generate_content(
                model=Config.TRANSLATION_MODEL,
                contents=contents,
                config=config,
            )

            # Parse response
            adjusted_data = json.loads(response.text)
            
            # Verify structure
            if 'transcription' not in adjusted_data or not adjusted_data['transcription']:
                logger.error("Adjusted translation missing transcription data")
                return translation_data  # Return original if adjustment failed
            
            # Log the adjustment
            original_text_len = sum(len(seg['text']) for seg in translation_data['transcription'])
            adjusted_text_len = sum(len(seg['text']) for seg in adjusted_data['transcription'])
            actual_reduction = ((original_text_len - adjusted_text_len) / original_text_len) * 100
            
            logger.info(f"Translation adjusted: {original_text_len} -> {adjusted_text_len} chars ({actual_reduction:.1f}% reduction)")
            
            return adjusted_data
            
        except Exception as e:
            logger.error(f"Failed to adjust translation for duration: {e}")
            return translation_data  # Return original on error
