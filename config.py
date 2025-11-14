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
    
    # Gemini Model Configuration
    TRANSCRIPTION_MODEL = os.getenv('TRANSCRIPTION_MODEL', 'gemini-2.5-flash')
    TRANSLATION_MODEL = os.getenv('TRANSLATION_MODEL', 'gemini-2.5-flash')
    TTS_MODEL = os.getenv('TTS_MODEL', 'gemini-2.5-pro-preview-tts')
    
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
    
    # Available TTS voices (Google Cloud Chirp v3)
    AVAILABLE_VOICES = {
        'en-US': {
            'en-US-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'en-US-Chirp3-HD-Puck': 'Puck (Warm)',
            'en-US-Chirp3-HD-Charon': 'Charon (Professional)',
            'en-US-Chirp3-HD-Kore': 'Kore (Friendly)',
            'en-US-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'en-US-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'pt-BR': {
            'pt-BR-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'pt-BR-Chirp3-HD-Puck': 'Puck (Warm)',
            'pt-BR-Chirp3-HD-Charon': 'Charon (Professional)',
            'pt-BR-Chirp3-HD-Kore': 'Kore (Friendly)',
            'pt-BR-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'pt-BR-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'es-ES': {
            'es-ES-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'es-ES-Chirp3-HD-Puck': 'Puck (Warm)',
            'es-ES-Chirp3-HD-Charon': 'Charon (Professional)',
            'es-ES-Chirp3-HD-Kore': 'Kore (Friendly)',
            'es-ES-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'es-ES-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'fr-FR': {
            'fr-FR-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'fr-FR-Chirp3-HD-Puck': 'Puck (Warm)',
            'fr-FR-Chirp3-HD-Charon': 'Charon (Professional)',
            'fr-FR-Chirp3-HD-Kore': 'Kore (Friendly)',
            'fr-FR-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'fr-FR-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'de-DE': {
            'de-DE-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'de-DE-Chirp3-HD-Puck': 'Puck (Warm)',
            'de-DE-Chirp3-HD-Charon': 'Charon (Professional)',
            'de-DE-Chirp3-HD-Kore': 'Kore (Friendly)',
            'de-DE-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'de-DE-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'it-IT': {
            'it-IT-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'it-IT-Chirp3-HD-Puck': 'Puck (Warm)',
            'it-IT-Chirp3-HD-Charon': 'Charon (Professional)',
            'it-IT-Chirp3-HD-Kore': 'Kore (Friendly)',
            'it-IT-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'it-IT-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'ja-JP': {
            'ja-JP-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'ja-JP-Chirp3-HD-Puck': 'Puck (Warm)',
            'ja-JP-Chirp3-HD-Charon': 'Charon (Professional)',
            'ja-JP-Chirp3-HD-Kore': 'Kore (Friendly)',
            'ja-JP-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'ja-JP-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'ko-KR': {
            'ko-KR-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'ko-KR-Chirp3-HD-Puck': 'Puck (Warm)',
            'ko-KR-Chirp3-HD-Charon': 'Charon (Professional)',
            'ko-KR-Chirp3-HD-Kore': 'Kore (Friendly)',
            'ko-KR-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'ko-KR-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'nl-NL': {
            'nl-NL-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'nl-NL-Chirp3-HD-Puck': 'Puck (Warm)',
            'nl-NL-Chirp3-HD-Charon': 'Charon (Professional)',
            'nl-NL-Chirp3-HD-Kore': 'Kore (Friendly)',
            'nl-NL-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'nl-NL-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'pl-PL': {
            'pl-PL-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'pl-PL-Chirp3-HD-Puck': 'Puck (Warm)',
            'pl-PL-Chirp3-HD-Charon': 'Charon (Professional)',
            'pl-PL-Chirp3-HD-Kore': 'Kore (Friendly)',
            'pl-PL-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'pl-PL-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'ru-RU': {
            'ru-RU-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'ru-RU-Chirp3-HD-Puck': 'Puck (Warm)',
            'ru-RU-Chirp3-HD-Charon': 'Charon (Professional)',
            'ru-RU-Chirp3-HD-Kore': 'Kore (Friendly)',
            'ru-RU-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'ru-RU-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        },
        'zh-CN': {
            'zh-CN-Chirp3-HD-Zephyr': 'Zephyr (Recommended)',
            'zh-CN-Chirp3-HD-Puck': 'Puck (Warm)',
            'zh-CN-Chirp3-HD-Charon': 'Charon (Professional)',
            'zh-CN-Chirp3-HD-Kore': 'Kore (Friendly)',
            'zh-CN-Chirp3-HD-Fenrir': 'Fenrir (Deep)',
            'zh-CN-Chirp3-HD-Aoede': 'Aoede (Smooth)'
        }
    }
    
    # Default voices for each language
    DEFAULT_VOICES = {
        'en-US': 'en-US-Chirp3-HD-Zephyr',
        'pt-BR': 'pt-BR-Chirp3-HD-Zephyr',
        'es-ES': 'es-ES-Chirp3-HD-Zephyr',
        'fr-FR': 'fr-FR-Chirp3-HD-Zephyr',
        'de-DE': 'de-DE-Chirp3-HD-Zephyr',
        'it-IT': 'it-IT-Chirp3-HD-Zephyr',
        'ja-JP': 'ja-JP-Chirp3-HD-Zephyr',
        'ko-KR': 'ko-KR-Chirp3-HD-Zephyr',
        'nl-NL': 'nl-NL-Chirp3-HD-Zephyr',
        'pl-PL': 'pl-PL-Chirp3-HD-Zephyr',
        'ru-RU': 'ru-RU-Chirp3-HD-Zephyr',
        'zh-CN': 'zh-CN-Chirp3-HD-Zephyr'
    }
    
    # Google Cloud TTS Configuration
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
    TTS_SPEAKING_RATE = float(os.getenv('TTS_SPEAKING_RATE', '1.0'))  # 0.25 to 2.0
    
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
        if not Config.GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY is required. Please set it in your .env file.")
        
        # Validate GCS configuration if using GCS storage
        if Config.STORAGE_BACKEND == 'gcs':
            if not Config.GCS_BUCKET_NAME:
                raise ValueError("GCS_BUCKET_NAME is required when using GCS storage backend. Please set it in your .env file.")
            if not Config.GOOGLE_CLOUD_PROJECT:
                raise ValueError("GOOGLE_CLOUD_PROJECT is required when using GCS storage backend. Please set it in your .env file.")
        
        # Create necessary directories (always needed for local temp processing)
        for folder in [Config.UPLOAD_FOLDER, Config.TEMP_FOLDER, Config.OUTPUT_FOLDER]:
            os.makedirs(folder, exist_ok=True)
