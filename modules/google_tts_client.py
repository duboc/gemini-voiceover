import os
import logging
from typing import List, Dict
from google.cloud import texttospeech
from config import Config

# Set up logging
logger = logging.getLogger(__name__)


class GoogleTTSClient:
    def __init__(self):
        """Initialize Google Cloud Text-to-Speech client"""
        try:
            self.client = texttospeech.TextToSpeechClient()
            logger.info("Google Cloud TTS client initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Google Cloud TTS client: {e}")
            raise Exception(f"Google Cloud TTS initialization failed: {str(e)}")
    
    def generate_speech(self, translation_data: Dict, voice_name: str, output_dir: str) -> List[str]:
        """
        Generate speech from translated text segments using Google Cloud TTS
        """
        try:
            logger.info(f"Generating speech with Google Cloud TTS voice '{voice_name}' for {len(translation_data['transcription'])} segments")
            audio_files = []
            
            # Extract language code from voice name (e.g., pt-BR-Chirp3-HD-Zephyr -> pt-BR)
            language_code = voice_name.split('-')[0] + '-' + voice_name.split('-')[1]
            
            for i, segment in enumerate(translation_data['transcription']):
                text = segment['text']
                start_time = segment['start_time']
                end_time = segment['end_time']
                
                logger.info(f"Generating speech for segment {i}: '{text[:50]}...' ({start_time:.1f}s - {end_time:.1f}s)")
                
                try:
                    # Create synthesis input
                    synthesis_input = texttospeech.SynthesisInput(text=text)
                    
                    # Configure voice
                    voice = texttospeech.VoiceSelectionParams(
                        language_code=language_code,
                        name=voice_name
                    )
                    
                    # Configure audio output with high quality
                    audio_config = texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                        sample_rate_hertz=24000,  # High quality sample rate
                        speaking_rate=Config.TTS_SPEAKING_RATE
                    )
                    
                    # Perform the text-to-speech request
                    response = self.client.synthesize_speech(
                        input=synthesis_input,
                        voice=voice,
                        audio_config=audio_config
                    )
                    
                    # Save the audio file
                    filename = f"segment_{i:03d}_{start_time:.1f}_{end_time:.1f}.wav"
                    filepath = os.path.join(output_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.audio_content)
                    
                    file_size = os.path.getsize(filepath)
                    logger.info(f"Saved audio segment {i} to: {filepath} ({file_size} bytes)")
                    audio_files.append(filepath)
                    
                except Exception as e:
                    logger.error(f"Failed to generate speech for segment {i}: {e}")
                    # Continue with other segments even if one fails
                    continue
            
            logger.info(f"Google Cloud TTS generation completed: {len(audio_files)} files generated")
            return audio_files
            
        except Exception as e:
            logger.error(f"Google Cloud TTS generation failed: {str(e)}", exc_info=True)
            raise Exception(f"Speech generation failed: {str(e)}")
    
    def generate_speech_with_markup(self, translation_data: Dict, voice_name: str, output_dir: str) -> List[str]:
        """
        Generate speech using markup for better control over pauses and pacing
        """
        try:
            logger.info(f"Generating speech with markup using voice '{voice_name}'")
            audio_files = []
            
            # Extract language code from voice name
            language_code = voice_name.split('-')[0] + '-' + voice_name.split('-')[1]
            
            for i, segment in enumerate(translation_data['transcription']):
                text = segment['text']
                start_time = segment['start_time']
                end_time = segment['end_time']
                
                # Add natural pauses and pacing to the text
                enhanced_text = self._enhance_text_with_markup(text)
                
                logger.info(f"Generating speech for segment {i} with markup: '{enhanced_text[:50]}...'")
                
                try:
                    # Create synthesis input with markup
                    synthesis_input = texttospeech.SynthesisInput(markup=enhanced_text)
                    
                    # Configure voice
                    voice = texttospeech.VoiceSelectionParams(
                        language_code=language_code,
                        name=voice_name
                    )
                    
                    # Configure audio output with high quality
                    audio_config = texttospeech.AudioConfig(
                        audio_encoding=texttospeech.AudioEncoding.LINEAR16,
                        sample_rate_hertz=24000,  # High quality sample rate
                        speaking_rate=Config.TTS_SPEAKING_RATE
                    )
                    
                    # Perform the text-to-speech request
                    response = self.client.synthesize_speech(
                        input=synthesis_input,
                        voice=voice,
                        audio_config=audio_config
                    )
                    
                    # Save the audio file
                    filename = f"segment_{i:03d}_{start_time:.1f}_{end_time:.1f}.wav"
                    filepath = os.path.join(output_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.audio_content)
                    
                    file_size = os.path.getsize(filepath)
                    logger.info(f"Saved enhanced audio segment {i} to: {filepath} ({file_size} bytes)")
                    audio_files.append(filepath)
                    
                except Exception as e:
                    logger.error(f"Failed to generate speech with markup for segment {i}: {e}")
                    # Fallback to regular text synthesis
                    try:
                        synthesis_input = texttospeech.SynthesisInput(text=text)
                        response = self.client.synthesize_speech(
                            input=synthesis_input,
                            voice=voice,
                            audio_config=audio_config
                        )
                        
                        filename = f"segment_{i:03d}_{start_time:.1f}_{end_time:.1f}.wav"
                        filepath = os.path.join(output_dir, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(response.audio_content)
                        
                        audio_files.append(filepath)
                        logger.info(f"Fallback: Saved regular audio segment {i}")
                        
                    except Exception as fallback_error:
                        logger.error(f"Both markup and regular synthesis failed for segment {i}: {fallback_error}")
                        continue
            
            logger.info(f"Enhanced TTS generation completed: {len(audio_files)} files generated")
            return audio_files
            
        except Exception as e:
            logger.error(f"Enhanced TTS generation failed: {str(e)}", exc_info=True)
            raise Exception(f"Enhanced speech generation failed: {str(e)}")
    
    def _enhance_text_with_markup(self, text: str) -> str:
        """
        Enhance text with markup tags for more natural speech
        """
        try:
            # Add natural pauses after punctuation
            enhanced_text = text
            
            # Add short pauses after commas
            enhanced_text = enhanced_text.replace(',', ', [pause short]')
            
            # Add longer pauses after periods and exclamation marks
            enhanced_text = enhanced_text.replace('.', '. [pause]')
            enhanced_text = enhanced_text.replace('!', '! [pause]')
            enhanced_text = enhanced_text.replace('?', '? [pause]')
            
            # Add pauses around ellipses
            enhanced_text = enhanced_text.replace('...', '[pause long]')
            
            # Add emphasis pauses around important words (basic heuristic)
            # This is a simple implementation - could be enhanced with NLP
            emphasis_words = ['importante', 'atenção', 'cuidado', 'novo', 'especial', 
                            'importante', 'atención', 'cuidado', 'nuevo', 'especial']
            
            for word in emphasis_words:
                if word in enhanced_text.lower():
                    enhanced_text = enhanced_text.replace(word, f'[pause short] {word} [pause short]')
                    enhanced_text = enhanced_text.replace(word.capitalize(), f'[pause short] {word.capitalize()} [pause short]')
            
            return enhanced_text
            
        except Exception as e:
            logger.warning(f"Failed to enhance text with markup: {e}")
            return text  # Return original text if enhancement fails
    
    def list_available_voices(self, language_code: str = None) -> List[Dict]:
        """
        List available voices for the specified language
        """
        try:
            voices = self.client.list_voices(language_code=language_code)
            
            available_voices = []
            for voice in voices.voices:
                if 'Chirp3-HD' in voice.name:  # Filter for Chirp v3 HD voices
                    available_voices.append({
                        'name': voice.name,
                        'language_codes': voice.language_codes,
                        'ssml_gender': voice.ssml_gender.name
                    })
            
            logger.info(f"Found {len(available_voices)} Chirp v3 HD voices for language: {language_code}")
            return available_voices
            
        except Exception as e:
            logger.error(f"Failed to list voices: {e}")
            return []
    
    def test_voice(self, voice_name: str, test_text: str = "Hello, this is a test.") -> bool:
        """
        Test if a voice is available and working
        """
        try:
            # Extract language code from voice name
            language_code = voice_name.split('-')[0] + '-' + voice_name.split('-')[1]
            
            synthesis_input = texttospeech.SynthesisInput(text=test_text)
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16
            )
            
            response = self.client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            
            # Check if we got audio content
            if response.audio_content and len(response.audio_content) > 0:
                logger.info(f"Voice {voice_name} test successful")
                return True
            else:
                logger.warning(f"Voice {voice_name} test failed - no audio content")
                return False
                
        except Exception as e:
            logger.error(f"Voice {voice_name} test failed: {e}")
            return False
