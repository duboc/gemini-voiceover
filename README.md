# Gemini Video Voiceover Translator

A professional Flask web application that translates video narration using Google Gemini AI and Google Cloud Text-to-Speech. Upload a video, select a target language, and get back a new video with high-quality AI-generated voiceover in the selected language while maintaining perfect timing synchronization.

## 🚀 Key Features

### **AI-Powered Translation Pipeline**
- **Gemini 2.5 Flash**: Accurate transcription and translation with timestamp preservation
- **Google Cloud TTS**: Professional Chirp v3 HD voices for broadcast-quality audio
- **Demucs Audio Separation**: State-of-the-art AI for vocal isolation and background music preservation
- **Intelligent Fallback**: Automatic quality assessment with graceful degradation

### **Professional Audio Processing**
- **Background Music Preservation**: AI separates vocals from music, preserves original atmosphere
- **Replace All Mode**: Fast processing option that replaces entire audio track
- **High-Quality Pipeline**: 24kHz TTS generation with quality preservation throughout
- **Robust Audio Mixing**: Advanced timing-based mixing with multiple fallback methods

### **Corporate-Ready Features**
- **Multiple Processing Modes**: Choose between music preservation or fast replacement
- **Language-Specific Voices**: Chirp v3 HD voices optimized for each target language
- **Real-Time Progress**: Detailed progress tracking with status updates
- **Reliable Processing**: Multi-level validation ensures successful completion

## 🎯 Supported Languages & Voices

### **Brazilian Portuguese (pt-BR)**
- pt-BR-Chirp3-HD-Zephyr (Recommended)
- pt-BR-Chirp3-HD-Puck
- pt-BR-Chirp3-HD-Charon
- pt-BR-Chirp3-HD-Kore
- pt-BR-Chirp3-HD-Fenrir
- pt-BR-Chirp3-HD-Aoede

### **Spanish (es)**
- es-ES-Chirp3-HD-Zephyr (Recommended)
- es-ES-Chirp3-HD-Puck
- es-ES-Chirp3-HD-Charon
- es-ES-Chirp3-HD-Kore
- es-ES-Chirp3-HD-Fenrir
- es-ES-Chirp3-HD-Aoede

## 🔄 Processing Workflow

### **Preserve Background Music Mode (Recommended)**
1. **Upload Video** → Select MP4/MOV file (max 500MB)
2. **Audio Extraction** → High-quality audio extraction (44.1kHz stereo)
3. **AI Separation** → Demucs separates vocals from background music
4. **Transcription** → Gemini AI transcribes vocal track with timestamps
5. **Translation** → Translate text to target language
6. **Voice Generation** → Google Cloud TTS generates new voiceover (24kHz)
7. **Audio Mixing** → Combine new vocals with preserved background music
8. **Video Assembly** → Create final video with mixed audio
9. **Download** → Get professional-quality translated video

### **Replace All Audio Mode (Fast)**
1. **Upload Video** → Select MP4/MOV file
2. **Audio Extraction** → Extract original audio for transcription
3. **Transcription** → Gemini AI transcribes with timestamps
4. **Translation** → Translate to target language
5. **Voice Generation** → Google Cloud TTS creates new voiceover
6. **Audio Replacement** → Replace entire audio track
7. **Video Assembly** → Create final video
8. **Download** → Get clean, fast-processed video

## 📋 Prerequisites

- **Python 3.8+**
- **FFmpeg** (for video/audio processing)
- **Google Gemini API key**
- **Google Cloud Project** (for TTS)
- **Demucs dependencies** (PyTorch, torchaudio)

## 🛠 Installation

### **1. Clone Repository**
```bash
git clone <repository-url>
cd gemini-voiceover
```

### **2. Install Python Dependencies**
```bash
pip install -r requirements.txt
```

### **3. Install FFmpeg**

**macOS** (using Homebrew):
```bash
brew install ffmpeg
```

**Ubuntu/Debian**:
```bash
sudo apt update
sudo apt install ffmpeg
```

**Windows**:
Download from [https://ffmpeg.org/download.html](https://ffmpeg.org/download.html)

### **4. Set Up Google Cloud Authentication**

**Option A: Service Account (Recommended for Production)**
```bash
# Create service account and download JSON key
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/service-account-key.json"
```

**Option B: Application Default Credentials (Development)**
```bash
gcloud auth application-default login
```

### **5. Configure Environment Variables**
```bash
cp .env.example .env
```

Edit `.env` with your configuration:
```env
# Required
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_CLOUD_PROJECT=your_google_cloud_project_id

# Optional
FLASK_SECRET_KEY=your_secret_key_here
FLASK_DEBUG=True
FLASK_PORT=5000
TTS_SPEAKING_RATE=1.0
```

### **6. Set Up Google Cloud Storage (Optional)**

**For Production Deployments**:
```bash
# Create a GCS bucket
gsutil mb gs://your-voiceover-bucket

# Set bucket permissions (if needed)
gsutil iam ch serviceAccount:your-service-account@project.iam.gserviceaccount.com:objectAdmin gs://your-voiceover-bucket
```

**Configure GCS in `.env`**:
```env
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=your-voiceover-bucket
GCS_ENABLE_LIFECYCLE=True
GCS_TEMP_FILE_RETENTION_DAYS=7
```

### **7. Get API Keys**

**Gemini API Key**:
- Go to [Google AI Studio](https://aistudio.google.com/)
- Create a new API key
- Add to `.env` file

**Google Cloud Project**:
- Go to [Google Cloud Console](https://console.cloud.google.com/)
- Create or select a project
- Enable Text-to-Speech API and Cloud Storage API
- Set up authentication

## 🚀 Usage

### **1. Start the Application**
```bash
python app.py
```

### **2. Open Web Interface**
```
http://localhost:8080
```

### **3. Process Videos**
1. **Upload**: Select MP4 or MOV file
2. **Configure**: Choose language, voice, and processing mode
3. **Advanced Settings** (for Preserve Music mode):
   - Select AI separation model (HTDEMUCS recommended)
   - Adjust vocal/music balance
4. **Process**: Click "Start Translation"
5. **Monitor**: Watch real-time progress
6. **Download**: Get your translated video

## ⚙️ Configuration

### **Required Settings**
```env
GEMINI_API_KEY=your_gemini_api_key_here
GOOGLE_CLOUD_PROJECT=your_google_cloud_project_id
```

### **Optional Settings**
```env
# Flask Configuration
FLASK_SECRET_KEY=your_secret_key_here
FLASK_DEBUG=True
FLASK_PORT=5000

# File Processing
MAX_FILE_SIZE_MB=500
MAX_CONCURRENT_JOBS=3
CLEANUP_TEMP_FILES_HOURS=24

# TTS Configuration
TTS_SPEAKING_RATE=1.0  # 0.25 to 2.0 (speed control)

# Model Configuration
TRANSCRIPTION_MODEL=gemini-2.5-flash
TRANSLATION_MODEL=gemini-2.5-flash
```

## 🏗 Project Structure

```
gemini-voiceover/
├── app.py                      # Main Flask application
├── config.py                   # Configuration management
├── requirements.txt            # Python dependencies
├── .env.example               # Environment template
├── modules/
│   ├── gemini_client.py       # Gemini API integration
│   ├── google_tts_client.py   # Google Cloud TTS client
│   ├── video_processor.py     # Video/audio processing
│   ├── audio_separator.py     # Demucs audio separation
│   └── file_manager.py        # File handling utilities
├── templates/
│   └── index.html             # Web interface
├── static/
│   ├── css/style.css          # Custom styles
│   ├── js/app.js              # Frontend JavaScript
│   ├── uploads/               # Uploaded files
│   ├── temp/                  # Processing files
│   └── outputs/               # Final videos
└── README.md
```

## 🔧 API Endpoints

- `GET /`: Main upload page
- `POST /upload`: Upload video and start processing
- `GET /status/<process_id>`: Get processing status
- `GET /download/<process_id>`: Download processed video

## 🎵 Audio Processing Modes

### **Preserve Background Music (AI Separation)**
- **Best for**: Corporate videos, promotional content with music
- **Process**: Demucs AI separates vocals from background music
- **Result**: New vocals mixed with original music and sound effects
- **Quality**: Highest quality, maintains production value
- **Time**: Longer processing (5-10 minutes for separation)

### **Replace Entire Audio Track (Fast & Simple)**
- **Best for**: Training videos, announcements, simple narration
- **Process**: Skips audio separation entirely
- **Result**: Clean new voiceover replaces all original audio
- **Quality**: Consistent, professional narration
- **Time**: Fastest processing (saves 5-10 minutes)

## 🛠 Troubleshooting

### **Debug Tools**
```bash
# Test basic setup
python test_app.py

# Comprehensive diagnostics
python debug_app.py
```

### **Common Issues**

**1. FFmpeg not found**
```bash
# Test FFmpeg installation
ffmpeg -version

# Run diagnostics
python debug_app.py
```

**2. Google Cloud TTS errors**
```bash
# Check authentication
gcloud auth application-default print-access-token

# Verify project and API
gcloud config list
```

**3. Demucs/PyTorch issues**
```bash
# Check PyTorch installation
python -c "import torch; print(torch.__version__)"

# Test CUDA availability (optional)
python -c "import torch; print(torch.cuda.is_available())"
```

**4. Audio processing failures**
- Check FFmpeg version (4.0+ recommended)
- Verify sufficient disk space (2-3x video size)
- Monitor system memory during processing
- Check logs for specific error messages

**5. No vocals in output video**
- Verify TTS generation completed successfully
- Check audio combination logs for errors
- Ensure final audio file exists and has content
- Try "Replace All" mode as fallback

### **Performance Optimization**

**For Faster Processing**:
- Use "Replace All" mode for simple content
- Choose MDX model for faster separation
- Process shorter video segments
- Ensure SSD storage for temp files

**For Best Quality**:
- Use "Preserve Music" mode
- Select HTDEMUCS model for separation
- Use higher vocal balance for clearer speech
- Ensure stable internet for API calls

## 🔬 Advanced Features

### **Audio Separation Models**
- **HTDEMUCS**: Highest quality, slower processing
- **MDX-Extra**: Balanced quality and speed
- **MDX**: Fastest processing, good quality

### **Voice Controls**
- **Speaking Rate**: 0.25x to 2.0x speed control
- **Natural Pauses**: Automatic pause insertion with markup
- **Language Optimization**: Voices optimized for each language

### **Quality Assurance**
- **Automatic validation** at each processing step
- **Multiple fallback methods** for reliable results
- **Quality scoring** for separation assessment
- **Comprehensive error recovery**

## 🤝 Development

### **Contributing**
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly with `debug_app.py`
5. Submit a pull request

### **Testing**
```bash
# Run basic tests
python test_app.py

# Run comprehensive diagnostics
python debug_app.py

# Test specific components
python -m modules.google_tts_client
python -m modules.audio_separator
```

## 🚀 Deployment to Google Cloud Run

You can easily deploy this application to Google Cloud Run using the provided script.

### Prerequisites
1. [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and initialized.
2. A Google Cloud Project with billing enabled.
3. `Cloud Run Admin` and `Artifact Registry Administrator` roles.

### Deploy
Run the deployment script:

```bash
./deploy.sh
```

The script will:
1. Check for your `GEMINI_API_KEY` (in `.env` or prompt you).
2. Build the container image remotely using Cloud Build.
3. Deploy the service to Cloud Run.
4. Output the public URL of your application.

Note: The deployment creates a public service (`--allow-unauthenticated`). Remove this flag in `deploy.sh` if you want to restrict access.


## 📄 License

This project is licensed under the Apache 2.0 License - see the LICENSE file for details.

## 🙏 Acknowledgments

- **Google Gemini AI** for transcription and translation
- **Google Cloud Text-to-Speech** for Chirp v3 HD voices
- **Demucs** for audio separation
- **FFmpeg** for video/audio processing
- **Flask** for the web framework
- **Bootstrap** for UI components

## ☁️ Google Cloud Storage Integration

### **Scalable File Storage**
- **Hybrid Storage**: Support for both local and Google Cloud Storage backends
- **Automatic Lifecycle**: Configurable retention policies for temporary files
- **Artifact Preservation**: All processing data saved for analysis and debugging
- **Signed URLs**: Secure, time-limited download links for GCS files

### **Storage Organization**
```
GCS Bucket Structure:
├── uploads/           # Original uploaded videos
├── outputs/           # Final translated videos  
├── artifacts/         # Processing artifacts by process_id
│   └── {process_id}/
│       ├── json/      # Transcriptions, translations
│       └── logs/      # Processing logs
├── processing/        # Temporary processing files (auto-cleanup)
└── temp/             # General temporary files (auto-cleanup)
```

### **Configuration Options**
```env
# Storage Backend Selection
STORAGE_BACKEND=gcs              # Options: local, gcs

# GCS Configuration  
GCS_BUCKET_NAME=your-bucket-name
GCS_ENABLE_LIFECYCLE=True
GCS_TEMP_FILE_RETENTION_DAYS=7
```

### **Benefits**
- **Scalability**: Handle larger files without local storage constraints
- **Reliability**: Built-in redundancy and durability
- **Cost Efficiency**: Automatic cleanup and pay-per-use pricing
- **Multi-Instance**: Support for distributed processing
- **Persistence**: Files survive server restarts and deployments

## 🆕 Recent Updates

### **v2.1 - Google Cloud Storage Integration**
- ✅ **Hybrid Storage System** - Local and GCS backend support
- ✅ **Automatic Lifecycle Management** - Configurable file retention
- ✅ **Artifact Storage** - Complete processing history preservation
- ✅ **Signed URL Downloads** - Secure, scalable file delivery
- ✅ **Graceful Fallback** - Automatic local storage if GCS unavailable

### **v2.0 - Professional Audio Processing**
- ✅ **Google Cloud TTS Integration** - Chirp v3 HD voices
- ✅ **Demucs Audio Separation** - Professional vocal isolation
- ✅ **Dual Processing Modes** - Preserve music or replace all
- ✅ **Enhanced Quality Pipeline** - 24kHz TTS with quality preservation
- ✅ **Robust Error Handling** - Multi-level validation and fallbacks
- ✅ **Corporate-Ready Features** - Reliable processing for business use

### **v1.0 - Initial Release**
- ✅ Basic video translation with Gemini AI
- ✅ Simple audio replacement
- ✅ Web interface with progress tracking
- ✅ Multiple language support
