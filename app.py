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
from modules.audio_synchronizer import AudioSynchronizer
from modules.subtitle_generator import SubtitleGenerator

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
                         default_voices=Config.DEFAULT_VOICES,
                         separation_models=Config.SEPARATION_MODELS,
                         processing_modes=Config.PROCESSING_MODES,
                         tts_backends=Config.TTS_BACKENDS)


@app.route('/api/voices/<tts_backend>/<language_code>')
def get_voices_for_backend_and_language(tts_backend, language_code):
    """Get available voices for a specific TTS backend and language"""
    if language_code not in Config.SUPPORTED_LANGUAGES:
        return jsonify({'error': 'Unsupported language'}), 400
    
    if tts_backend not in Config.TTS_BACKENDS:
        return jsonify({'error': 'Unsupported TTS backend'}), 400
    
    # Get voices based on TTS backend selection
    if tts_backend == 'gemini':
        voices = Config.GEMINI_VOICES
        default_voice = Config.DEFAULT_GEMINI_VOICE
    elif tts_backend == 'chirp3':
        voices = Config.CHIRP3_VOICES.get(language_code, {})
        default_voice = Config.DEFAULT_CHIRP3_VOICES.get(language_code, '')
    else:
        return jsonify({'error': 'Invalid TTS backend'}), 400
    
    return jsonify({
        'voices': voices,
        'default_voice': default_voice,
        'language_name': Config.SUPPORTED_LANGUAGES[language_code],
        'tts_backend': tts_backend
    })


@app.route('/api/tts-recommendation/<language_code>')
def get_tts_recommendation(language_code):
    """Return the recommended TTS backend for a given language."""
    if language_code not in Config.SUPPORTED_LANGUAGES:
        return jsonify({'error': 'Unsupported language'}), 400

    recommended = Config.get_recommended_tts_backend(language_code)
    return jsonify({
        'language': language_code,
        'recommended': recommended,
        'is_override': language_code in Config.RECOMMENDED_TTS_BACKEND,
    })


@app.route('/api/voices/<language_code>')
def get_voices_for_language(language_code):
    """Legacy endpoint - Get available voices for a specific language (uses default backend)"""
    if language_code not in Config.SUPPORTED_LANGUAGES:
        return jsonify({'error': 'Unsupported language'}), 400
    
    # Use default TTS backend from config
    tts_backend = Config.TTS_BACKEND
    
    if tts_backend == 'gemini':
        voices = Config.GEMINI_VOICES
        default_voice = Config.DEFAULT_GEMINI_VOICE
    elif tts_backend == 'chirp3':
        voices = Config.CHIRP3_VOICES.get(language_code, {})
        default_voice = Config.DEFAULT_CHIRP3_VOICES.get(language_code, '')
    else:
        # Fallback to Gemini voices
        voices = Config.GEMINI_VOICES
        default_voice = Config.DEFAULT_GEMINI_VOICE
    
    return jsonify({
        'voices': voices,
        'default_voice': default_voice,
        'language_name': Config.SUPPORTED_LANGUAGES[language_code],
        'tts_backend': tts_backend
    })


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
        target_language = request.form.get('language', 'en-US')
        tts_backend = request.form.get('tts_backend', Config.TTS_BACKEND)
        voice_name = request.form.get('voice', Config.DEFAULT_GEMINI_VOICE)
        separation_model = request.form.get('separation_model', Config.DEFAULT_SEPARATION_MODEL)
        processing_mode = request.form.get('processing_mode', Config.DEFAULT_PROCESSING_MODE)
        vocal_balance = float(request.form.get('vocal_balance', Config.DEFAULT_VOCAL_MUSIC_BALANCE))
        enable_subtitles = request.form.get('enable_subtitles', 'false').lower() == 'true'
        subtitle_language = request.form.get('subtitle_language', target_language)

        if target_language not in Config.SUPPORTED_LANGUAGES:
            return jsonify({'error': 'Unsupported language'}), 400
        
        if tts_backend not in Config.TTS_BACKENDS:
            return jsonify({'error': 'Unsupported TTS backend'}), 400
        
        # Validate voice name based on TTS backend
        if tts_backend == 'gemini':
            if voice_name not in Config.GEMINI_VOICES:
                return jsonify({'error': 'Unsupported voice for Gemini TTS'}), 400
        elif tts_backend == 'chirp3':
            # Validate Chirp 3 voice
            valid_voices = Config.CHIRP3_VOICES.get(target_language, {})
            if voice_name not in valid_voices:
                return jsonify({'error': f'Unsupported voice for Chirp 3 and language {target_language}'}), 400
        else:
            return jsonify({'error': 'Invalid TTS backend'}), 400
        
        if separation_model not in Config.SEPARATION_MODELS:
            return jsonify({'error': 'Unsupported separation model'}), 400
        
        if processing_mode not in Config.PROCESSING_MODES:
            return jsonify({'error': 'Unsupported processing mode'}), 400
        
        if not (0.0 <= vocal_balance <= 1.0):
            return jsonify({'error': 'Invalid vocal balance value'}), 400

        if enable_subtitles and subtitle_language not in Config.SUPPORTED_LANGUAGES:
            return jsonify({'error': 'Unsupported subtitle language'}), 400

        # Save uploaded file
        video_path = file_manager.save_uploaded_file(file, "video")
        
        # For GCS files, download locally for validation
        local_video_path = video_path
        if video_path.startswith('gs://'):
            local_video_path = os.path.join("/tmp", f"validate_{os.path.basename(video_path)}")
            file_manager.download_file(video_path, local_video_path)
        
        # Validate video file
        if not video_processor.validate_video_file(local_video_path):
            file_manager.cleanup_temp_files()
            if video_path.startswith('gs://') and os.path.exists(local_video_path):
                os.remove(local_video_path)
            return jsonify({'error': 'Invalid video file'}), 400
        
        # Clean up temp validation file
        if video_path.startswith('gs://') and os.path.exists(local_video_path):
            os.remove(local_video_path)
        
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
            args=(process_id, video_path, target_language, voice_name, tts_backend, separation_model, processing_mode, vocal_balance, file.filename, enable_subtitles, subtitle_language)
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


@app.route('/api/review/<process_id>')
def get_review_data(process_id):
    """Get transcription and translation for review"""
    if process_id not in processing_status:
        return jsonify({'error': 'Invalid process ID'}), 404
    
    status = processing_status[process_id]
    
    if 'transcription_data' not in status or 'translation_data' not in status:
        return jsonify({'error': 'Review data not available'}), 404
    
    return jsonify({
        'transcription': status['transcription_data'],
        'translation': status['translation_data'],
        'target_language': status.get('target_language', 'unknown')
    })


@app.route('/api/approve/<process_id>', methods=['POST'])
def approve_translation(process_id):
    """Approve translation and continue with video generation"""
    if process_id not in processing_status:
        return jsonify({'error': 'Invalid process ID'}), 404
    
    status = processing_status[process_id]
    
    if status.get('status') != 'awaiting_review':
        return jsonify({'error': 'Not in review state'}), 400
    
    # Get edited translation if provided
    data = request.get_json()
    if data and 'translation' in data:
        # User edited the translation
        status['translation_data'] = data['translation']
        logger.info(f"User updated translation for {process_id}")
    
    # Signal to continue processing
    status['approved'] = True
    status['status'] = 'processing'
    status['message'] = 'Generating speech with approved translation...'
    
    return jsonify({'success': True, 'message': 'Translation approved, continuing processing'})


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
    
    result_file = status['result_file']
    
    # Handle GCS files with enhanced URL generation
    if result_file.startswith('gs://'):
        download_info = file_manager.get_download_info(result_file)
        
        if download_info['type'] == 'gcs' and download_info.get('url'):
            url_type = download_info.get('url_type', 'unknown')
            logger.info(f"Redirecting to {url_type} for download: {process_id}")
            
            # Log any warnings about the URL type
            if download_info.get('error'):
                logger.warning(f"Download URL warning: {download_info['error']}")
            
            # Redirect to the generated URL (signed, token-based, or direct)
            return redirect(download_info['url'])
            
        else:
            # Enhanced fallback: download to temp and serve
            error_msg = download_info.get('error', 'Failed to generate download URL')
            logger.error(f"Download URL generation failed for {process_id}: {error_msg}")
            
            try:
                logger.info(f"Attempting fallback download for {process_id}")
                import tempfile
                import os
                
                # Create a secure temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix='.mp4') as temp_file:
                    temp_path = temp_file.name
                
                # Download from GCS to temp file
                file_manager.download_file(result_file, temp_path)
                
                # Generate a proper filename
                original_name = os.path.basename(result_file)
                if not original_name.endswith('.mp4'):
                    original_name = f"translated_video_{process_id}.mp4"
                
                # Serve the file and schedule cleanup
                def cleanup_temp_file():
                    try:
                        if os.path.exists(temp_path):
                            os.remove(temp_path)
                    except:
                        pass
                
                # Use Flask's after_request to clean up
                @app.after_request
                def cleanup_after_request(response):
                    cleanup_temp_file()
                    return response
                
                logger.info(f"Serving fallback download for {process_id}")
                return send_file(temp_path, as_attachment=True, download_name=original_name)
                
            except Exception as e:
                logger.error(f"Fallback download failed for {process_id}: {str(e)}")
                return jsonify({'error': f"Download failed: {str(e)}"}), 500
    else:
        # Local file
        logger.info(f"Serving local file download for {process_id}")
        return send_file(result_file, as_attachment=True)


def process_video(process_id: str, video_path: str, target_language: str, voice_name: str,
                 tts_backend: str, separation_model: str, processing_mode: str, vocal_balance: float, original_filename: str,
                 enable_subtitles: bool = False, subtitle_language: str = ''):
    """Process video in background thread with Demucs separation and intelligent fallback"""
    temp_dir = None
    audio_separator = None
    use_fallback = False
    
    try:
        logger.info(f"Starting video processing for {process_id}: {original_filename}")
        logger.info(f"Target language: {target_language}, Voice: {voice_name}, TTS Backend: {tts_backend}")
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
        
        # Download video file if it's in GCS
        local_video_path = video_path
        if video_path.startswith('gs://'):
            local_video_path = os.path.join(temp_dir, "input_video.mp4")
            file_manager.download_file(video_path, local_video_path)
            logger.info(f"Downloaded video from GCS to: {local_video_path}")
        
        # Extract audio from video
        audio_path = os.path.join(temp_dir, "extracted_audio.wav")
        logger.info(f"Extracting audio to: {audio_path}")
        video_processor.extract_audio(local_video_path, audio_path)
        
        # Get video info
        video_info = video_processor.get_video_info(local_video_path)
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
            'message': 'Transcribing vocal track with video context...'
        })
        
        # Transcribe vocal track with video context for better accuracy
        logger.info("Starting vocal track transcription with video context...")
        try:
            transcription_data = gemini_client.validate_and_regenerate(
                vocals_path, 
                local_video_path,
                min_quality=0.6,
                max_attempts=2
            )
            quality_score = transcription_data.get('quality_score', 0.0)
            logger.info(f"Transcription completed: {len(transcription_data.get('transcription', []))} segments (quality: {quality_score:.2f})")
        except Exception as e:
            logger.warning(f"Video-enhanced transcription failed, trying audio-only: {e}")
            transcription_data = gemini_client.transcribe_audio(vocals_path)
            logger.info(f"Audio-only transcription completed: {len(transcription_data.get('transcription', []))} segments")
        
        # Save transcription for debugging and as artifact
        transcription_content = json.dumps(transcription_data, indent=2, ensure_ascii=False)
        transcription_file = os.path.join(temp_dir, "transcription.json")
        with open(transcription_file, 'w', encoding='utf-8') as f:
            f.write(transcription_content)
        logger.info(f"Transcription saved to: {transcription_file}")
        
        # Save transcription artifact
        try:
            file_manager.save_artifact(transcription_content, "transcription.json", process_id, "json")
        except Exception as e:
            logger.warning(f"Failed to save transcription artifact: {e}")
        
        # Update status
        processing_status[process_id].update({
            'progress': 50,
            'message': 'Translating text...'
        })
        
        # Translate text
        logger.info("Starting text translation...")
        translation_data = gemini_client.translate_text(transcription_data, target_language)
        
        # Store target language in translation data for later use
        translation_data['target_language'] = target_language
        
        logger.info(f"Translation completed: {len(translation_data.get('transcription', []))} segments")
        
        # Save translation for debugging and as artifact
        translation_content = json.dumps(translation_data, indent=2, ensure_ascii=False)
        translation_file = os.path.join(temp_dir, "translation.json")
        with open(translation_file, 'w', encoding='utf-8') as f:
            f.write(translation_content)
        logger.info(f"Translation saved to: {translation_file}")
        
        # Save translation artifact
        try:
            file_manager.save_artifact(translation_content, "translation.json", process_id, "json")
        except Exception as e:
            logger.warning(f"Failed to save translation artifact: {e}")
        
        # REVIEW STEP: Wait for user to approve translation
        processing_status[process_id].update({
            'status': 'awaiting_review',
            'progress': 60,
            'message': 'Please review the transcription and translation',
            'transcription_data': transcription_data,
            'translation_data': translation_data,
            'target_language': target_language,
            'approved': False
        })
        
        logger.info(f"Waiting for user approval for {process_id}")
        
        # Wait for user approval (poll every 2 seconds)
        import time
        max_wait_time = Config.REVIEW_TIMEOUT_SEC
        wait_time = 0
        while not processing_status[process_id].get('approved', False) and wait_time < max_wait_time:
            time.sleep(2)
            wait_time += 2

            # Check if user cancelled or error occurred
            if processing_status[process_id].get('status') == 'cancelled':
                logger.info(f"Processing cancelled by user for {process_id}")
                return

        if wait_time >= max_wait_time:
            raise Exception(
                f"Review timeout: User did not approve translation within "
                f"{max_wait_time}s ({max_wait_time // 60} minutes)"
            )
        
        # Get potentially updated translation data
        translation_data = processing_status[process_id]['translation_data']
        logger.info(f"User approved translation for {process_id}")
        
        # Initialize TTS client based on backend selection
        speech_dir = os.path.join(temp_dir, "speech_segments")
        os.makedirs(speech_dir, exist_ok=True)
        
        # Initialize Google TTS Client (Unified for both Gemini and Chirp)
        google_tts_client = GoogleTTSClient()
        
        if tts_backend == 'gemini':
            # Gemini 3.1 Flash TTS
            processing_status[process_id].update({
                'status': 'processing',
                'progress': 70,
                'message': 'Generating speech with Gemini 3.1 Flash TTS...'
            })
            
            logger.info(f"Using Gemini 3.1 Flash TTS for speech generation")
            
            # Validate voice
            if voice_name not in Config.GEMINI_VOICES:
                voice_name = Config.DEFAULT_GEMINI_VOICE
                logger.warning(f"Invalid Gemini voice, using default: {voice_name}")
            
            logger.info(f"Generating speech with Gemini voice: {voice_name}")
            
            # Determine model name from config
            model_name = Config.GEMINI_TTS_MODEL
            
            audio_files = google_tts_client.generate_speech(
                translation_data, 
                voice_name, 
                speech_dir,
                model_name=model_name
            )
            
            logger.info(f"Generated {len(audio_files)} audio files with Gemini TTS")
            
        elif tts_backend == 'chirp3':
            # Vertex AI / Google Cloud TTS with Chirp 3 HD
            processing_status[process_id].update({
                'status': 'processing',
                'progress': 70,
                'message': 'Generating speech with Vertex AI Chirp 3 HD...'
            })
            
            logger.info(f"Using Vertex AI Chirp 3 HD for speech generation")
            
            # Validate voice
            valid_voices = Config.CHIRP3_VOICES.get(target_language, {})
            if voice_name not in valid_voices:
                voice_name = Config.DEFAULT_CHIRP3_VOICES.get(target_language, '')
                if not voice_name:
                    raise Exception(f"No Chirp 3 voices available for language {target_language}")
                logger.warning(f"Invalid Chirp 3 voice, using default: {voice_name}")
            
            logger.info(f"Generating speech with Chirp 3 voice: {voice_name}")
            
            # Chirp 3 HD does not use model_name param in the same way (or uses 'chirp-3-hd' implied by voice name?)
            # The docs say: "voice=texttospeech.VoiceSelectionParams(name='en-US-Chirp3-HD-Charon', ...)"
            # We don't strictly need model_name for Chirp if voice name is specific.
            
            audio_files = google_tts_client.generate_speech(
                translation_data, 
                voice_name, 
                speech_dir
            )
            logger.info(f"Generated {len(audio_files)} audio files with Chirp 3 HD")
            
        else:
            raise Exception(f"Unsupported TTS backend: {tts_backend}")
        
        # Fail-fast: every TTS call rejected → no audio files were produced.
        # Without this guard, the pipeline cheerfully proceeds to mux a
        # silent track into the final video (real bug seen with zh-CN +
        # Cloud TTS API mismatch).
        if not audio_files or len(audio_files) == 0:
            raise Exception(
                "TTS produced no audio files (0 segments synthesised). "
                "Check the TTS backend, voice name, and language code; "
                "see Cloud Run logs for per-segment errors."
            )

        # Update status
        processing_status[process_id].update({
            'progress': 80,
            'message': 'Synchronizing audio timing...'
        })
        
        # Extract timestamps for audio combination
        timestamps = [(seg['start_time'], seg['end_time']) for seg in translation_data['transcription']]
        logger.info(f"Audio timestamps: {timestamps}")
        
        # Apply audio synchronization if enabled
        if Config.ENABLE_AUDIO_SYNC:
            logger.info("Synchronizing audio segments...")
            audio_synchronizer = AudioSynchronizer()
            
            # DURATION ADJUSTMENT LOOP: Ensure speech fits naturally
            if getattr(Config, 'ENFORCE_ORIGINAL_DURATION', True):
                max_attempts = getattr(Config, 'MAX_DURATION_ADJUSTMENT_ATTEMPTS', 3)
                logger.info(f"Checking for duration mismatches (max attempts: {max_attempts})...")
                
                for attempt in range(max_attempts):
                    # Analyze current timing
                    timing_analysis = audio_synchronizer.analyze_timing_accuracy(audio_files, timestamps)
                    
                    # Identify segments requiring excessive speedup
                    segments_to_fix = [item for item in timing_analysis['timing_data'] if item.get('needs_shortening', False)]
                    
                    if not segments_to_fix:
                        logger.info("All segments fit within duration limits (no excessive shortening needed).")
                        break
                    
                    logger.info(f"Duration check attempt {attempt+1}: Found {len(segments_to_fix)} segments requiring shortening.")
                    
                    adjustments_made = False
                    for item in segments_to_fix:
                        idx = item['segment']
                        current_duration = item['actual_duration']
                        target_duration = item['expected_duration']
                        
                        logger.info(f"Fixing segment {idx}: {current_duration:.2f}s > {target_duration:.2f}s (needs shortening)")
                        
                        try:
                            # Construct partial data for just this segment
                            segment_data = {
                                'transcription': [translation_data['transcription'][idx]]
                            }
                            
                            # Request shortened translation from Gemini
                            adjusted_segment_data = gemini_client.adjust_translation_for_duration(
                                segment_data,
                                target_duration,
                                current_duration,
                                target_language
                            )
                            
                            # Update main translation data
                            if adjusted_segment_data and 'transcription' in adjusted_segment_data and adjusted_segment_data['transcription']:
                                new_text = adjusted_segment_data['transcription'][0]['text']
                                old_text = translation_data['transcription'][idx]['text']
                                
                                if new_text != old_text:
                                    logger.info(f"Segment {idx} updated: '{old_text[:30]}...' -> '{new_text[:30]}...'")
                                    translation_data['transcription'][idx]['text'] = new_text
                                    adjustments_made = True
                        except Exception as e:
                            logger.error(f"Failed to adjust segment {idx}: {e}")
                    
                    if adjustments_made:
                        changed_indices = [item['segment'] for item in segments_to_fix]
                        logger.info(
                            f"Regenerating TTS only for shortened segments: {changed_indices}"
                        )
                        new_files = google_tts_client.generate_speech_segments(
                            translation_data,
                            voice_name,
                            speech_dir,
                            segment_indices=changed_indices,
                            model_name=model_name if tts_backend == 'gemini' else None,
                        )
                        # Replace in-place; new_files come back ordered by segment index
                        for replacement in new_files:
                            # Filename pattern is segment_{idx:03d}_*.wav
                            basename = os.path.basename(replacement)
                            try:
                                idx = int(basename.split('_')[1])
                            except (IndexError, ValueError):
                                continue
                            if 0 <= idx < len(audio_files):
                                audio_files[idx] = replacement
                    else:
                        logger.warning("No adjustments could be made despite duration issues. Continuing...")
                        break

            # Final Synchronization (Fine-tuning)
            # Analyze timing before final sync
            timing_analysis = audio_synchronizer.analyze_timing_accuracy(audio_files, timestamps)
            logger.info(f"Final timing analysis: {timing_analysis['segments_out_of_sync']}/{timing_analysis['total_segments']} out of sync")
            
            # Synchronize segments
            sync_dir = os.path.join(temp_dir, "synchronized")
            os.makedirs(sync_dir, exist_ok=True)
            audio_files = audio_synchronizer.synchronize_segments(audio_files, timestamps, sync_dir)
            logger.info("Audio synchronization completed")
        
        # Update status
        processing_status[process_id].update({
            'progress': 85,
            'message': 'Combining audio segments...'
        })
        
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
        
        # Replace video audio (and optionally burn-in subtitles)
        temp_output_path = os.path.join(temp_dir, "output_video.mp4")
        logger.info(f"Creating final video: {temp_output_path}")

        if enable_subtitles:
            processing_status[process_id].update({
                'message': 'Generating subtitles and encoding video...'
            })

            if subtitle_language and subtitle_language != target_language:
                logger.info(f"Translating subtitles to {subtitle_language} (differs from voiceover {target_language})")
                subtitle_data = gemini_client.translate_text(transcription_data, subtitle_language)
            else:
                subtitle_data = translation_data

            subtitle_generator = SubtitleGenerator()
            srt_path = os.path.join(temp_dir, "subtitles.srt")
            subtitle_generator.generate_srt(subtitle_data['transcription'], srt_path)

            video_processor.replace_video_audio_with_subtitles(
                local_video_path, final_audio_path, srt_path, temp_output_path,
            )
        else:
            video_processor.replace_video_audio(local_video_path, final_audio_path, temp_output_path)
        
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
