import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

class Config:
    # Gemini API Configuration
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
    
    # Flask Configuration
    SECRET_KEY = os.getenv('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'
    PORT = int(os.getenv('FLASK_PORT', 8080))
    
    # File Processing Configuration
    MAX_FILE_SIZE_MB = int(os.getenv('MAX_FILE_SIZE_MB', 500))
    MAX_CONTENT_LENGTH = MAX_FILE_SIZE_MB * 1024 * 1024  # Convert to bytes
    UPLOAD_FOLDER = os.getenv('UPLOAD_FOLDER', 'static/uploads')
    TEMP_FOLDER = os.getenv('TEMP_FOLDER', 'static/temp')
    OUTPUT_FOLDER = os.getenv('OUTPUT_FOLDER', 'static/outputs')
    
    # Processing Configuration
    MAX_CONCURRENT_JOBS = int(os.getenv('MAX_CONCURRENT_JOBS', 3))
    CLEANUP_TEMP_FILES_HOURS = int(os.getenv('CLEANUP_TEMP_FILES_HOURS', 24))

    # Review wait: how long the background thread polls for user approval
    # before giving up. 30 minutes by default — long enough for a thoughtful
    # review, short enough to bound 'forgotten' jobs that hold a worker.
    REVIEW_TIMEOUT_SEC = int(os.getenv('REVIEW_TIMEOUT_SEC', 1800))
    
    # Gemini Model Configuration
    TRANSCRIPTION_MODEL = os.getenv('TRANSCRIPTION_MODEL', 'gemini-2.5-flash')
    TRANSLATION_MODEL = os.getenv('TRANSLATION_MODEL', 'gemini-2.5-flash')
    GEMINI_TTS_MODEL = os.getenv('GEMINI_TTS_MODEL', 'gemini-2.5-flash-tts')
    
    # Supported formats and languages
    ALLOWED_VIDEO_EXTENSIONS = {'mp4', 'mov'}
    SUPPORTED_LANGUAGES = {
        'en-US': 'English (US)',
        'pt-BR': 'Brazilian Portuguese',
        'es-ES': 'Spanish (Spain)',
        'fr-FR': 'French (France)',
        'de-DE': 'German (Germany)',
        'it-IT': 'Italian (Italy)',
        'ja-JP': 'Japanese (Japan)',
        'ko-KR': 'Korean (South Korea)',
        'nl-NL': 'Dutch (Netherlands)',
        'pl-PL': 'Polish (Poland)',
        'ru-RU': 'Russian (Russia)',
        'zh-CN': 'Chinese (Mandarin, China)'
    }
    
    # TTS Backend Configuration
    TTS_BACKEND = os.getenv('TTS_BACKEND', 'gemini')  # Options: gemini, chirp3

    # TTS Backend Options (for UI)
    TTS_BACKENDS = {
        'gemini': 'Gemini 2.5 Flash TTS (Modern, Universal)',
        'chirp3': 'Vertex AI Chirp 3 HD (Premium Quality)'
    }

    # Per-language recommended TTS backend. Used to nudge users toward the
    # backend known to have full voice coverage in that language. Mandarin
    # Chirp 3 HD voices for several personas may not exist in Vertex AI.
    RECOMMENDED_TTS_BACKEND = {
        'zh-CN': 'gemini',
    }

    @classmethod
    def get_recommended_tts_backend(cls, language_code: str) -> str:
        """Return the recommended TTS backend for a language, or the default."""
        return cls.RECOMMENDED_TTS_BACKEND.get(language_code, cls.TTS_BACKEND)
    
    # Available Gemini TTS voices (all languages supported)
    GEMINI_VOICES = {
        'Zephyr': 'Zephyr (Natural, Balanced)',
        'Puck': 'Puck (Warm, Friendly)',
        'Charon': 'Charon (Professional, Clear)',
        'Kore': 'Kore (Friendly, Energetic)',
        'Fenrir': 'Fenrir (Deep, Authoritative)',
        'Aoede': 'Aoede (Smooth, Pleasant)'
    }
    
    # Default Gemini voice
    DEFAULT_GEMINI_VOICE = 'Zephyr'
    
    # Chirp 3 HD Voices (language-specific)
    # Follows pattern: [language_code]-Chirp3-HD-[VoiceName]
    # Using same personas as Gemini: Zephyr, Puck, Charon, Kore, Fenrir, Aoede
    CHIRP3_VOICES = {}
    DEFAULT_CHIRP3_VOICES = {}
    
    # Helper to populate Chirp 3 voices
    _PERSONAS = {
        'Zephyr': 'Zephyr (Natural, Balanced)',
        'Puck': 'Puck (Warm, Friendly)',
        'Charon': 'Charon (Professional, Clear)',
        'Kore': 'Kore (Friendly, Energetic)',
        'Fenrir': 'Fenrir (Deep, Authoritative)',
        'Aoede': 'Aoede (Smooth, Pleasant)'
    }
    
    # Initialize voices for all supported languages
    _LANGS = [
        'en-US', 'pt-BR', 'es-ES', 'fr-FR', 'de-DE', 
        'it-IT', 'ja-JP', 'ko-KR', 'nl-NL', 'pl-PL', 
        'ru-RU', 'zh-CN'
    ]
    
    for lang in _LANGS:
        CHIRP3_VOICES[lang] = {}
        for persona, desc in _PERSONAS.items():
            voice_id = f"{lang}-Chirp3-HD-{persona}"
            CHIRP3_VOICES[lang][voice_id] = f"{persona} (Chirp 3 HD)"
        
        # Set default
        DEFAULT_CHIRP3_VOICES[lang] = f"{lang}-Chirp3-HD-Zephyr"
    
    # Legacy Google Cloud TTS voices (kept for backward compatibility)
    AVAILABLE_VOICES = {
        'en-US': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'pt-BR': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'es-ES': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'fr-FR': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'de-DE': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'it-IT': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'ja-JP': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'ko-KR': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'nl-NL': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'pl-PL': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'ru-RU': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        },
        'zh-CN': {
            'Zephyr': 'Zephyr (Recommended)',
            'Puck': 'Puck (Warm)',
            'Charon': 'Charon (Professional)',
            'Kore': 'Kore (Friendly)',
            'Fenrir': 'Fenrir (Deep)',
            'Aoede': 'Aoede (Smooth)'
        }
    }
    
    # Default voices for each language
    DEFAULT_VOICES = {
        'en-US': 'Zephyr',
        'pt-BR': 'Zephyr',
        'es-ES': 'Zephyr',
        'fr-FR': 'Zephyr',
        'de-DE': 'Zephyr',
        'it-IT': 'Zephyr',
        'ja-JP': 'Zephyr',
        'ko-KR': 'Zephyr',
        'nl-NL': 'Zephyr',
        'pl-PL': 'Zephyr',
        'ru-RU': 'Zephyr',
        'zh-CN': 'Zephyr'
    }
    
    # Google Cloud TTS Configuration (legacy - kept for backward compatibility)
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
    TTS_SPEAKING_RATE = float(os.getenv('TTS_SPEAKING_RATE', '1.0'))  # 0.25 to 2.0

    # Final video audio encoding (AAC). Default 192k stereo @ 48kHz keeps
    # the rendered file on par with consumer video sources.
    OUTPUT_AUDIO_BITRATE = os.getenv('OUTPUT_AUDIO_BITRATE', '192k')
    OUTPUT_AUDIO_SAMPLE_RATE = int(os.getenv('OUTPUT_AUDIO_SAMPLE_RATE', '48000'))
    OUTPUT_AUDIO_CHANNELS = int(os.getenv('OUTPUT_AUDIO_CHANNELS', '2'))

    # Loudness normalisation applied once to the concatenated track so that
    # per-segment TTS loudness variation is smoothed out. Defaults aim for
    # broadcast-grade -16 LUFS integrated; suitable for streaming platforms.
    ENABLE_LOUDNORM = os.getenv('ENABLE_LOUDNORM', 'True').lower() == 'true'
    LOUDNORM_TARGET_I = os.getenv('LOUDNORM_TARGET_I', '-16')
    LOUDNORM_TP = os.getenv('LOUDNORM_TP', '-1.5')
    LOUDNORM_LRA = os.getenv('LOUDNORM_LRA', '11')
    
    # Audio Synchronization Configuration
    ENABLE_AUDIO_SYNC = os.getenv('ENABLE_AUDIO_SYNC', 'True').lower() == 'true'
    MAX_TIMING_DIFFERENCE_SEC = float(os.getenv('MAX_TIMING_DIFFERENCE_SEC', '0.5'))
    SYNC_METHOD = os.getenv('SYNC_METHOD', 'stretch')  # Options: stretch, pad, trim, tempo_only
    PRESERVE_TOTAL_DURATION = os.getenv('PRESERVE_TOTAL_DURATION', 'True').lower() == 'true'  # Prevent duration extension
    
    # TTS Rate Limiting & Batching Configuration
    TTS_BATCH_SIZE = int(os.getenv('TTS_BATCH_SIZE', '10'))  # Number of segments per API call
    TTS_MAX_TEXT_LENGTH = int(os.getenv('TTS_MAX_TEXT_LENGTH', '2000'))  # Max characters per batch
    TTS_RATE_LIMIT_DELAY = float(os.getenv('TTS_RATE_LIMIT_DELAY', '6.5'))  # Delay between batches (seconds)
    TTS_MAX_RETRIES = int(os.getenv('TTS_MAX_RETRIES', '5'))  # Max retry attempts for rate limiting
    TTS_ENABLE_BATCHING = os.getenv('TTS_ENABLE_BATCHING', 'True').lower() == 'true'  # Enable segment batching

    # Parallel TTS generation: number of concurrent synthesise calls.
    # Vertex AI TTS quotas typically allow 100-300 RPM; 5 workers gives
    # ~3-5x speedup without risking rate limits when combined with the
    # exponential-backoff retry on ResourceExhausted.
    TTS_PARALLEL_WORKERS = int(os.getenv('TTS_PARALLEL_WORKERS', '5'))
    
    # Smart Batching Configuration (for 30-second chunks)
    TTS_BATCH_DURATION_SEC = float(os.getenv('TTS_BATCH_DURATION_SEC', '30.0'))  # Target duration for combined segments
    TTS_SMART_BATCHING = os.getenv('TTS_SMART_BATCHING', 'True').lower() == 'true'  # Enable intelligent text combination
    TTS_MIN_BATCH_SEGMENTS = int(os.getenv('TTS_MIN_BATCH_SEGMENTS', '3'))  # Minimum segments to combine
    
    # Duration Management Configuration
    ENFORCE_ORIGINAL_DURATION = os.getenv('ENFORCE_ORIGINAL_DURATION', 'True').lower() == 'true'  # Ensure audio fits video
    DURATION_TOLERANCE_SEC = float(os.getenv('DURATION_TOLERANCE_SEC', '1.0'))  # Acceptable duration difference
    MAX_DURATION_ADJUSTMENT_ATTEMPTS = int(os.getenv('MAX_DURATION_ADJUSTMENT_ATTEMPTS', '3'))  # Max retries
    ALLOW_TEXT_SHORTENING = os.getenv('ALLOW_TEXT_SHORTENING', 'True').lower() == 'true'  # Allow Gemini to shorten text
    MIN_SPEAKING_RATE = float(os.getenv('MIN_SPEAKING_RATE', '0.85'))  # Minimum tempo (85% speed)
    MAX_SPEAKING_RATE = float(os.getenv('MAX_SPEAKING_RATE', '1.15'))  # Maximum tempo (115% speed)
    
    # Google Cloud Storage Configuration
    GCS_BUCKET_NAME = os.getenv('GCS_BUCKET_NAME')
    STORAGE_BACKEND = os.getenv('STORAGE_BACKEND', 'local')  # Options: local, gcs
    GCS_ENABLE_LIFECYCLE = os.getenv('GCS_ENABLE_LIFECYCLE', 'True').lower() == 'true'
    GCS_TEMP_FILE_RETENTION_DAYS = int(os.getenv('GCS_TEMP_FILE_RETENTION_DAYS', 7))
    
    # Audio separation models (Demucs-based)
    SEPARATION_MODELS = {
        'htdemucs': 'High Quality (HTDEMUCS) - Best Results',
        'mdx_extra': 'Balanced (MDX-Extra) - Good Quality, Faster',
        'mdx': 'Fast (MDX) - Quick Processing'
    }
    
    # Processing modes
    PROCESSING_MODES = {
        'preserve_music': 'Preserve Background Music (AI Separation)',
        'replace_all': 'Replace Entire Audio Track (Fast & Simple)'
    }
    
    # Default separation settings
    DEFAULT_SEPARATION_MODEL = 'htdemucs'
    DEFAULT_PROCESSING_MODE = 'preserve_music'
    DEFAULT_VOCAL_MUSIC_BALANCE = 0.8  # 0.0 = all music, 1.0 = all vocals (increased for louder vocals)
    SEPARATION_QUALITY_THRESHOLD = 0.3  # Minimum separation quality (higher for Demucs)
    ENABLE_FALLBACK = True  # Enable automatic fallback to replace_all mode
    
    @staticmethod
    def validate_config():
        """Validate that required configuration is present"""
        # Google Cloud Project is required for Vertex AI (Gemini & TTS)
        if not Config.GOOGLE_CLOUD_PROJECT:
            # Try to get from default environment
            import google.auth
            try:
                _, project = google.auth.default()
                if project:
                    Config.GOOGLE_CLOUD_PROJECT = project
            except:
                pass
                
            if not Config.GOOGLE_CLOUD_PROJECT:
                raise ValueError("GOOGLE_CLOUD_PROJECT is required for Vertex AI. Please set it in your .env file or ensure ADC is configured.")
        
        # Validate GCS configuration if using GCS storage
        if Config.STORAGE_BACKEND == 'gcs':
            if not Config.GCS_BUCKET_NAME:
                raise ValueError("GCS_BUCKET_NAME is required when using GCS storage backend. Please set it in your .env file.")
        
        # Create necessary directories (always needed for local temp processing)
        for folder in [Config.UPLOAD_FOLDER, Config.TEMP_FOLDER, Config.OUTPUT_FOLDER]:
            os.makedirs(folder, exist_ok=True)
