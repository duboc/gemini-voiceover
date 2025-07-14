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
        'pt-BR': 'Brazilian Portuguese',
        'es': 'Spanish'
    }
    
    # Available TTS voices (Google Cloud Chirp v3)
    AVAILABLE_VOICES = {
        'pt-BR': {
            'pt-BR-Chirp3-HD-Zephyr': 'Zephyr (Brazilian Portuguese)',
            'pt-BR-Chirp3-HD-Puck': 'Puck (Brazilian Portuguese)',
            'pt-BR-Chirp3-HD-Charon': 'Charon (Brazilian Portuguese)',
            'pt-BR-Chirp3-HD-Kore': 'Kore (Brazilian Portuguese)',
            'pt-BR-Chirp3-HD-Fenrir': 'Fenrir (Brazilian Portuguese)',
            'pt-BR-Chirp3-HD-Aoede': 'Aoede (Brazilian Portuguese)'
        },
        'es': {
            'es-ES-Chirp3-HD-Zephyr': 'Zephyr (Spanish)',
            'es-ES-Chirp3-HD-Puck': 'Puck (Spanish)',
            'es-ES-Chirp3-HD-Charon': 'Charon (Spanish)',
            'es-ES-Chirp3-HD-Kore': 'Kore (Spanish)',
            'es-ES-Chirp3-HD-Fenrir': 'Fenrir (Spanish)',
            'es-ES-Chirp3-HD-Aoede': 'Aoede (Spanish)'
        }
    }
    
    # Default voices for each language
    DEFAULT_VOICES = {
        'pt-BR': 'pt-BR-Chirp3-HD-Zephyr',
        'es': 'es-ES-Chirp3-HD-Zephyr'
    }
    
    # Google Cloud TTS Configuration
    GOOGLE_CLOUD_PROJECT = os.getenv('GOOGLE_CLOUD_PROJECT')
    TTS_SPEAKING_RATE = float(os.getenv('TTS_SPEAKING_RATE', '1.0'))  # 0.25 to 2.0
    
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
        
        # Create necessary directories
        for folder in [Config.UPLOAD_FOLDER, Config.TEMP_FOLDER, Config.OUTPUT_FOLDER]:
            os.makedirs(folder, exist_ok=True)
