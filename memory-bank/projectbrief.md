# Gemini Video Voiceover Translator - Project Brief

## Project Overview
A professional Flask web application that translates video narration using Google Gemini AI and Google Cloud Text-to-Speech. The application processes uploaded videos by:
1. Extracting and separating audio (vocals from background music)
2. Transcribing vocals using Gemini AI
3. Translating text to target language
4. Generating new voiceover with Google Cloud TTS
5. Mixing new vocals with preserved background music
6. Creating final translated video

## Core Requirements
- **AI-Powered Translation Pipeline**: Gemini 2.5 Flash for transcription/translation
- **Professional Audio Processing**: Google Cloud TTS with Chirp v3 HD voices
- **Background Music Preservation**: Demucs AI for vocal isolation
- **Multiple Processing Modes**: Preserve music vs. replace all audio
- **File Storage Integration**: Google Cloud Storage for scalability and persistence

## Current Task
Integrate Google Cloud Storage to replace local file storage for:
- Uploaded video files
- Temporary processing artifacts
- Final translated videos
- All intermediate files (transcriptions, audio segments, etc.)

## Technical Stack
- **Backend**: Flask (Python)
- **AI Services**: Google Gemini API, Google Cloud TTS
- **Audio Processing**: Demucs, FFmpeg
- **Storage**: Local files → Google Cloud Storage (current task)
- **Languages**: Portuguese (pt-BR), Spanish (es)

## Key Features
- Real-time progress tracking
- Multiple voice options per language
- Intelligent fallback mechanisms
- Professional audio quality (24kHz TTS)
- Corporate-ready reliability
