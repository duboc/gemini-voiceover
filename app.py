import os
import json
import threading
import logging
from flask import Flask, request, render_template, jsonify, send_file, redirect, url_for
from werkzeug.utils import secure_filename
from config import Config
from modules.gemini_client import GeminiClient
from modules.video_processor import VideoProcessor
from modules.file_manager import FileManager
from modules.audio_separator import AudioSeparator
from modules.google_tts_client import GoogleTTSClient

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.config.from_object(Config)

# Initialize modules
gemini_client = GeminiClient()
video_processor = VideoProcessor()
file_manager = FileManager()

# Store processing status
processing_status = {}


@app.route('/')
def index():
    """Main upload page"""
    return render_template('index.html', 
                         languages=Config.SUPPORTED_LANGUAGES,
                         voices=Config.AVAILABLE_VOICES,
                         separation_models=Config.SEPARATION_MODELS,
                         processing_modes=Config.PROCESSING_MODES)


@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and start processing"""
    try:
        # Validate request
        if 'video' not in request.files:
            return jsonify({'error': 'No video file provided'}), 400
        
        file = request.files['video']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        # Validate file extension
        if not file_manager.validate_file_extension(file.filename, Config.ALLOWED_VIDEO_EXTENSIONS):
            return jsonify({'error': 'Invalid file format. Only MP4 and MOV files are supported.'}), 400
        
        # Get form data
        target_language = request.form.get('language', 'pt-BR')
        voice_name = request.form.get('voice', 'Zephyr')
        separation_model = request.form.get('separation_model', Config.DEFAULT_SEPARATION_MODEL)
        processing_mode = request.form.get('processing_mode', Config.DEFAULT_PROCESSING_MODE)
        vocal_balance = float(request.form.get('vocal_balance', Config.DEFAULT_VOCAL_MUSIC_BALANCE))
        
        if target_language not in Config.SUPPORTED_LANGUAGES:
            return jsonify({'error': 'Unsupported language'}), 400
        
        # Validate voice name (check if it exists in any language)
        valid_voice = False
        for lang_voices in Config.AVAILABLE_VOICES.values():
            if voice_name in lang_voices:
                valid_voice = True
                break
        
        if not valid_voice:
            return jsonify({'error': 'Unsupported voice'}), 400
        
        if separation_model not in Config.SEPARATION_MODELS:
            return jsonify({'error': 'Unsupported separation model'}), 400
        
        if processing_mode not in Config.PROCESSING_MODES:
            return jsonify({'error': 'Unsupported processing mode'}), 400
        
        if not (0.0 <= vocal_balance <= 1.0):
            return jsonify({'error': 'Invalid vocal balance value'}), 400
        
        # Save uploaded file
        video_path = file_manager.save_uploaded_file(file, "video")
        
        # Validate video file
        if not video_processor.validate_video_file(video_path):
            file_manager.cleanup_temp_files()
            return jsonify({'error': 'Invalid video file'}), 400
        
        # Generate processing ID
        import uuid
        process_id = str(uuid.uuid4())
        
        # Initialize processing status
        processing_status[process_id] = {
            'status': 'started',
            'progress': 0,
            'message': 'Processing started...',
            'error': None,
            'result_file': None
        }
        
        # Start processing in background thread
        thread = threading.Thread(
            target=process_video,
            args=(process_id, video_path, target_language, voice_name, separation_model, processing_mode, vocal_balance, file.filename)
        )
        thread.daemon = True
        thread.start()
        
        return jsonify({
            'success': True,
            'process_id': process_id,
            'message': 'Processing started'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/status/<process_id>')
def get_status(process_id):
    """Get processing status"""
    if process_id not in processing_status:
        return jsonify({'error': 'Invalid process ID'}), 404
    
    return jsonify(processing_status[process_id])


@app.route('/download/<process_id>')
def download_file(process_id):
    """Download processed file"""
    if process_id not in processing_status:
        return jsonify({'error': 'Invalid process ID'}), 404
    
    status = processing_status[process_id]
    if status['status'] != 'completed' or not status['result_file']:
        return jsonify({'error': 'File not ready'}), 400
    
    if not file_manager.file_exists(status['result_file']):
        return jsonify({'error': 'File not found'}), 404
    
    return send_file(status['result_file'], as_attachment=True)


def process_video(process_id: str, video_path: str, target_language: str, voice_name: str, 
                 separation_model: str, processing_mode: str, vocal_balance: float, original_filename: str):
    """Process video in background thread with Demucs separation and intelligent fallback"""
    temp_dir = None
    audio_separator = None
    use_fallback = False
    
    try:
        logger.info(f"Starting video processing for {process_id}: {original_filename}")
        logger.info(f"Target language: {target_language}, Voice: {voice_name}")
        logger.info(f"Separation model: {separation_model}, Processing mode: {processing_mode}")
        logger.info(f"Vocal balance: {vocal_balance}")
        
        # Initialize audio separator
        audio_separator = AudioSeparator()
        
        # Update status
        processing_status[process_id].update({
            'status': 'processing',
            'progress': 5,
            'message': 'Extracting audio from video...'
        })
        
        # Create temporary directory
        temp_dir = file_manager.create_temp_directory()
        logger.info(f"Created temporary directory: {temp_dir}")
        
        # Extract audio from video
        audio_path = os.path.join(temp_dir, "extracted_audio.wav")
        logger.info(f"Extracting audio to: {audio_path}")
        video_processor.extract_audio(video_path, audio_path)
        
        # Get video info
        video_info = video_processor.get_video_info(video_path)
        logger.info(f"Video info: {video_info}")
        
        # Check processing mode to determine if we need audio separation
        if processing_mode == 'preserve_music':
            # Update status
            processing_status[process_id].update({
                'progress': 15,
                'message': 'Separating vocals from background music...'
            })
            
            # Separate audio into components
            separation_dir = os.path.join(temp_dir, "separated")
            os.makedirs(separation_dir, exist_ok=True)
            logger.info(f"Starting audio separation with model: {separation_model}")
            
            try:
                separated_files = audio_separator.separate_audio(audio_path, separation_model, separation_dir)
                logger.info(f"Audio separation completed: {list(separated_files.keys())}")
                
                # Validate separation results
                if not audio_separator.validate_separation_result(separated_files, separation_model):
                    raise Exception("Audio separation validation failed - poor quality results")
                
                # Get vocal and background music tracks
                vocals_path = separated_files.get('vocals')
                background_music_path = audio_separator.get_background_music(separated_files, separation_model)
                
                if not vocals_path or not background_music_path:
                    raise Exception("Failed to extract vocals or background music from separation")
                    
            except Exception as e:
                logger.error(f"Audio separation failed: {e}")
                # Fallback: use original audio for transcription, no background music
                vocals_path = audio_path
                background_music_path = None
                logger.warning("Proceeding without audio separation - using original audio")
        else:
            # Skip audio separation for replace_all mode
            logger.info("Processing mode is 'replace_all' - skipping audio separation")
            processing_status[process_id].update({
                'progress': 15,
                'message': 'Skipping audio separation (replace all mode)...'
            })
            vocals_path = audio_path
            background_music_path = None
        
        # Update status
        processing_status[process_id].update({
            'progress': 30,
            'message': 'Transcribing vocal track...'
        })
        
        # Transcribe vocal track only
        logger.info("Starting vocal track transcription...")
        transcription_data = gemini_client.transcribe_audio(vocals_path)
        logger.info(f"Transcription completed: {len(transcription_data.get('transcription', []))} segments")
        
        # Save transcription for debugging
        transcription_file = os.path.join(temp_dir, "transcription.json")
        with open(transcription_file, 'w', encoding='utf-8') as f:
            json.dump(transcription_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Transcription saved to: {transcription_file}")
        
        # Update status
        processing_status[process_id].update({
            'progress': 50,
            'message': 'Translating text...'
        })
        
        # Translate text
        logger.info("Starting text translation...")
        translation_data = gemini_client.translate_text(transcription_data, target_language)
        logger.info(f"Translation completed: {len(translation_data.get('transcription', []))} segments")
        
        # Save translation for debugging
        translation_file = os.path.join(temp_dir, "translation.json")
        with open(translation_file, 'w', encoding='utf-8') as f:
            json.dump(translation_data, f, indent=2, ensure_ascii=False)
        logger.info(f"Translation saved to: {translation_file}")
        
        # Update status
        processing_status[process_id].update({
            'progress': 70,
            'message': 'Generating speech...'
        })
        
        # Initialize Google Cloud TTS client and generate speech segments
        google_tts_client = GoogleTTSClient()
        speech_dir = os.path.join(temp_dir, "speech_segments")
        os.makedirs(speech_dir, exist_ok=True)
        logger.info(f"Generating speech segments in: {speech_dir}")
        
        # Map voice name to full Google Cloud voice name
        full_voice_name = voice_name
        if voice_name in Config.AVAILABLE_VOICES.get(target_language, {}):
            full_voice_name = voice_name
        else:
            # Use default voice for the language if voice not found
            full_voice_name = Config.DEFAULT_VOICES.get(target_language, Config.DEFAULT_VOICES['pt-BR'])
            logger.warning(f"Voice {voice_name} not found for {target_language}, using default: {full_voice_name}")
        
        audio_files = google_tts_client.generate_speech_with_markup(translation_data, full_voice_name, speech_dir)
        logger.info(f"Generated {len(audio_files)} audio files with Google Cloud TTS: {audio_files}")
        
        # Update status
        processing_status[process_id].update({
            'progress': 85,
            'message': 'Combining audio segments...'
        })
        
        # Extract timestamps for audio combination
        timestamps = [(seg['start_time'], seg['end_time']) for seg in translation_data['transcription']]
        logger.info(f"Audio timestamps: {timestamps}")
        
        # Combine new vocal segments
        new_vocals_path = os.path.join(temp_dir, "new_vocals.wav")
        logger.info(f"Combining new vocal segments to: {new_vocals_path}")
        
        try:
            video_processor.combine_audio_segments(
                audio_files, timestamps, new_vocals_path, video_info['duration']
            )
            
            # Validate that the combined audio file was created and has content
            if not os.path.exists(new_vocals_path):
                raise Exception("Combined vocals file was not created")
            
            file_size = os.path.getsize(new_vocals_path)
            if file_size < 1000:  # Less than 1KB indicates likely failure
                raise Exception(f"Combined vocals file is too small: {file_size} bytes")
            
            logger.info(f"Successfully combined vocals: {new_vocals_path} ({file_size} bytes)")
            
        except Exception as e:
            logger.error(f"Failed to combine audio segments: {e}")
            # Create a fallback by concatenating all TTS files directly
            logger.info("Attempting fallback: direct concatenation of TTS files")
            
            try:
                # Create a simple concatenation as fallback
                concat_list_path = os.path.join(temp_dir, "fallback_concat.txt")
                with open(concat_list_path, 'w') as f:
                    for audio_file in audio_files:
                        if os.path.exists(audio_file):
                            f.write(f"file '{os.path.abspath(audio_file)}'\n")
                
                import ffmpeg
                (
                    ffmpeg
                    .input(concat_list_path, format='concat', safe=0)
                    .output(new_vocals_path, acodec='pcm_s16le', ar=24000, ac=1)
                    .overwrite_output()
                    .run(capture_stdout=True, capture_stderr=True)
                )
                
                logger.info("Fallback concatenation completed")
                
            except Exception as fallback_error:
                logger.error(f"Fallback concatenation also failed: {fallback_error}")
                raise Exception("Both primary and fallback audio combination methods failed")
        
        # Update status
        processing_status[process_id].update({
            'progress': 90,
            'message': 'Finalizing audio track...'
        })
        
        # Determine final audio path
        if background_music_path and audio_separator and processing_mode == 'preserve_music':
            logger.info("Mixing new vocals with background music...")
            final_audio_path = os.path.join(temp_dir, "final_mixed_audio.wav")
            
            try:
                audio_separator.mix_audio_tracks(
                    new_vocals_path, background_music_path, final_audio_path, vocal_balance
                )
                
                # Validate mixed audio
                if not os.path.exists(final_audio_path) or os.path.getsize(final_audio_path) < 1000:
                    logger.warning("Audio mixing failed, using vocals only")
                    final_audio_path = new_vocals_path
                else:
                    logger.info(f"Successfully mixed audio: {final_audio_path}")
                    
            except Exception as mix_error:
                logger.error(f"Audio mixing failed: {mix_error}")
                logger.warning("Using vocals only due to mixing failure")
                final_audio_path = new_vocals_path
        else:
            logger.info("Using new vocals only (no background music or replace_all mode)")
            final_audio_path = new_vocals_path
        
        # Final validation of audio file
        if not os.path.exists(final_audio_path):
            raise Exception("Final audio file does not exist")
        
        final_audio_size = os.path.getsize(final_audio_path)
        if final_audio_size < 1000:
            raise Exception(f"Final audio file is too small: {final_audio_size} bytes")
        
        logger.info(f"Final audio ready: {final_audio_path} ({final_audio_size} bytes)")
        
        # Update status
        processing_status[process_id].update({
            'progress': 95,
            'message': 'Creating final video...'
        })
        
        # Replace video audio with mixed result
        temp_output_path = os.path.join(temp_dir, "output_video.mp4")
        logger.info(f"Creating final video: {temp_output_path}")
        video_processor.replace_video_audio(video_path, final_audio_path, temp_output_path)
        
        # Save final output
        final_output_path = file_manager.save_output_file(temp_output_path, original_filename)
        logger.info(f"Final output saved to: {final_output_path}")
        
        # Update status - completed
        processing_status[process_id].update({
            'status': 'completed',
            'progress': 100,
            'message': 'Processing completed successfully!',
            'result_file': final_output_path
        })
        
        logger.info(f"Video processing completed successfully for {process_id}")
        
    except Exception as e:
        logger.error(f"Video processing failed for {process_id}: {str(e)}", exc_info=True)
        
        # Update status - error
        processing_status[process_id].update({
            'status': 'error',
            'message': f'Processing failed: {str(e)}',
            'error': str(e)
        })
        
    finally:
        # Cleanup temporary files
        if temp_dir:
            logger.info(f"Cleaning up temporary directory: {temp_dir}")
            file_manager.cleanup_temp_files(temp_dir)


@app.errorhandler(413)
def too_large(e):
    return jsonify({'error': 'File too large'}), 413


@app.errorhandler(500)
def internal_error(e):
    return jsonify({'error': 'Internal server error'}), 500


if __name__ == '__main__':
    try:
        Config.validate_config()
        app.run(host='0.0.0.0', port=Config.PORT, debug=Config.DEBUG)
    except Exception as e:
        print(f"Failed to start application: {e}")
