# Technical Context

## Development Environment
- **OS**: macOS (Local Development)
- **IDE**: VS Code
- **Language**: Python 3.11+
- **Framework**: Flask

## Technology Stack

### Backend
- **Web Framework**: Flask
- **WSGI Server**: Gunicorn (Production)
- **Audio Processing**:
  - `ffmpeg-python`: Wrapper for FFmpeg operations
  - `demucs`: AI Music Source Separation
  - `torchaudio`: Audio manipulation
  - `soundfile`: Audio I/O
- **AI Integration**:
  - `google-genai`: Gemini API SDK (Transcription, Translation, TTS)
  - `google-cloud-texttospeech`: Legacy/Chirp integration
  - `google-cloud-storage`: Cloud file storage

### Frontend
- **Structure**: HTML5, CSS3, JavaScript (Vanilla)
- **Styling**: Custom CSS (Responsive)
- **Interactivity**: DOM manipulation, Fetch API

### Infrastructure & Deployment
- **Platform**: Google Cloud Run
- **Containerization**: Docker
  - Base Image: `python:3.11-slim`
  - System Dependencies: `ffmpeg`, `libsndfile1`, `git`, `build-essential`
- **Storage**: Google Cloud Storage (Production), Local (Development)

## Dependencies
### System Requirements
- **FFmpeg**: Essential for all audio/video processing
- **libsndfile**: Required by torchaudio/soundfile
- **Git**: For installing dependencies from source

### Python Packages
See `requirements.txt` for version pinning. Key libraries:
- `flask`
- `google-genai`
- `demucs`
- `torch`
- `ffmpeg-python`
- `gunicorn`

## Configuration
- **Environment Variables**: Managed via `.env` (local) and Cloud Run variables
- **Secrets**: API Keys (Gemini, etc.)

## Development Constraints
- **Audio Processing**: Heavy compute required for Demucs separation. Cloud Run instance needs sufficient memory/CPU.
- **Timeouts**: Gunicorn timeout increased to 120s to handle model loading and processing start.
- **Storage**: Cloud Run filesystem is in-memory and ephemeral. Large files must be processed in streams or chunks, or stored in GCS.
