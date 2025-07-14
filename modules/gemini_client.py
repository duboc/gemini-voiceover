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

# Set up logging
logger = logging.getLogger(__name__)


class GeminiClient:
    def __init__(self):
        self.client = genai.Client(api_key=Config.GEMINI_API_KEY)
    
    def transcribe_audio(self, audio_file_path: str) -> Dict:
        """Transcribe audio file and return timestamped JSON"""
        try:
            # Read audio file
            with open(audio_file_path, 'rb') as f:
                audio_data = f.read()
            
            mime_type = mimetypes.guess_type(audio_file_path)[0] or 'audio/wav'
            
            # Create prompt for timestamped transcription
            prompt = ("Please transcribe this audio file and return the result as a JSON object "
                     "with timestamps. Use this structure: "
                     '{"transcription": [{"start_time": 0.0, "end_time": 5.2, "text": "segment text"}]} '
                     "Include precise timestamps in seconds. Return only valid JSON.")
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                        types.Part.from_bytes(
                            data=audio_data,
                            mime_type=mime_type
                        )
                    ],
                ),
            ]
            
            config = types.GenerateContentConfig(
                temperature=0.1,
                response_mime_type="application/json",
            )
            
            response = self.client.models.generate_content(
                model=Config.TRANSCRIPTION_MODEL,
                contents=contents,
                config=config,
            )
            
            # Clean and parse JSON response
            transcription_data = self._parse_json_response(response.text, "transcription")
            return transcription_data
            
        except Exception as e:
            raise Exception(f"Transcription failed: {str(e)}")
    
    def translate_text(self, transcription_data: Dict, target_language: str) -> Dict:
        """Translate transcription data to target language"""
        try:
            language_names = {
                'pt-BR': 'Brazilian Portuguese',
                'es': 'Spanish'
            }
            
            target_lang_name = language_names.get(target_language, target_language)
            
            prompt = (f"Please translate the following transcription data to {target_lang_name}. "
                     f"Maintain the exact same JSON structure and timestamps, only translate the text content. "
                     f"Input JSON: {json.dumps(transcription_data, indent=2)} "
                     f"Return the translated version with the same structure. "
                     f"Keep all timestamps exactly the same. Return only valid JSON.")
            
            contents = [
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_text(text=prompt),
                    ],
                ),
            ]
            
            config = types.GenerateContentConfig(
                temperature=0.2,
                response_mime_type="application/json",
            )
            
            response = self.client.models.generate_content(
                model=Config.TRANSLATION_MODEL,
                contents=contents,
                config=config,
            )
            
            # Clean and parse JSON response
            translation_data = self._parse_json_response(response.text, "translation")
            return translation_data
            
        except Exception as e:
            raise Exception(f"Translation failed: {str(e)}")
    
    def generate_speech(self, translation_data: Dict, voice_name: str, output_dir: str) -> List[str]:
        """Generate speech from translated text segments"""
        try:
            logger.info(f"Generating speech with voice '{voice_name}' for {len(translation_data['transcription'])} segments")
            audio_files = []
            
            for i, segment in enumerate(translation_data['transcription']):
                text = segment['text']
                start_time = segment['start_time']
                end_time = segment['end_time']
                
                logger.info(f"Generating speech for segment {i}: '{text[:50]}...' ({start_time:.1f}s - {end_time:.1f}s)")
                
                contents = [
                    types.Content(
                        role="user",
                        parts=[
                            types.Part.from_text(text=text),
                        ],
                    ),
                ]
                
                config = types.GenerateContentConfig(
                    temperature=0.8,
                    response_modalities=["audio"],
                    speech_config=types.SpeechConfig(
                        voice_config=types.VoiceConfig(
                            prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                voice_name=voice_name
                            )
                        ),
                    ),
                )
                
                audio_data = b""
                chunk_count = 0
                for chunk in self.client.models.generate_content_stream(
                    model=Config.TTS_MODEL,
                    contents=contents,
                    config=config,
                ):
                    chunk_count += 1
                    if (chunk.candidates and 
                        chunk.candidates[0].content and 
                        chunk.candidates[0].content.parts and
                        chunk.candidates[0].content.parts[0].inline_data):
                        
                        inline_data = chunk.candidates[0].content.parts[0].inline_data
                        if inline_data.data:
                            audio_data += inline_data.data
                
                logger.info(f"Received {chunk_count} chunks, total audio data: {len(audio_data)} bytes")
                
                if audio_data:
                    filename = f"segment_{i:03d}_{start_time:.1f}_{end_time:.1f}.wav"
                    filepath = os.path.join(output_dir, filename)
                    
                    if not audio_data.startswith(b'RIFF'):
                        logger.info(f"Converting audio data to WAV format for segment {i}")
                        audio_data = self._convert_to_wav(audio_data, "audio/L16;rate=24000")
                    
                    with open(filepath, 'wb') as f:
                        f.write(audio_data)
                    
                    logger.info(f"Saved audio segment {i} to: {filepath} ({len(audio_data)} bytes)")
                    audio_files.append(filepath)
                else:
                    logger.warning(f"No audio data received for segment {i}: '{text}'")
            
            logger.info(f"Speech generation completed: {len(audio_files)} files generated")
            return audio_files
            
        except Exception as e:
            logger.error(f"Speech generation failed: {str(e)}", exc_info=True)
            raise Exception(f"Speech generation failed: {str(e)}")
    
    def _convert_to_wav(self, audio_data: bytes, mime_type: str) -> bytes:
        """Convert audio data to WAV format"""
        parameters = self._parse_audio_mime_type(mime_type)
        bits_per_sample = parameters["bits_per_sample"]
        sample_rate = parameters["rate"]
        num_channels = 1
        data_size = len(audio_data)
        bytes_per_sample = bits_per_sample // 8
        block_align = num_channels * bytes_per_sample
        byte_rate = sample_rate * block_align
        chunk_size = 36 + data_size
        
        header = struct.pack(
            "<4sI4s4sIHHIIHH4sI",
            b"RIFF",
            chunk_size,
            b"WAVE",
            b"fmt ",
            16,
            1,
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b"data",
            data_size
        )
        return header + audio_data
    
    def _parse_audio_mime_type(self, mime_type: str) -> Dict[str, int]:
        """Parse audio MIME type for format parameters"""
        bits_per_sample = 16
        rate = 24000
        
        parts = mime_type.split(";")
        for param in parts:
            param = param.strip()
            if param.lower().startswith("rate="):
                try:
                    rate_str = param.split("=", 1)[1]
                    rate = int(rate_str)
                except (ValueError, IndexError):
                    pass
            elif param.startswith("audio/L"):
                try:
                    bits_per_sample = int(param.split("L", 1)[1])
                except (ValueError, IndexError):
                    pass
        
        return {"bits_per_sample": bits_per_sample, "rate": rate}
    
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
        """Clean common JSON formatting issues"""
        # Remove any text before the first {
        start_idx = text.find('{')
        if start_idx > 0:
            text = text[start_idx:]
        
        # Remove any text after the last }
        end_idx = text.rfind('}')
        if end_idx > 0:
            text = text[:end_idx + 1]
        
        # Fix common issues
        text = text.replace('\n', ' ')  # Remove newlines
        text = text.replace('\r', ' ')  # Remove carriage returns
        text = text.replace('\t', ' ')  # Remove tabs
        
        # Fix trailing commas
        import re
        text = re.sub(r',(\s*[}\]])', r'\1', text)
        
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
