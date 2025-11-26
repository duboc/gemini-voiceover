# Gemini Video Voiceover Translator - Project Brief

## Project Overview
A professional Flask web application that translates video narration using Google Gemini AI and Gemini TTS 2.5 Flash. The application processes uploaded videos by:
1. Extracting and separating audio (vocals from background music using Demucs AI)
2. Transcribing vocals using Gemini 2.5 Flash (with video context for accuracy)
3. Translating text to target language with Gemini AI
4. **User review and editing of translations**
5. Generating new voiceover with Gemini TTS 2.5 Flash (6 universal voices)
6. Synchronizing audio timing with intelligent stretch/compression
7. Mixing new vocals with preserved background music
8. Creating final translated video

## Core Requirements

### **AI-Powered Translation Pipeline**
- Gemini 2.5 Flash for transcription (audio + video multimodal)
- Gemini 2.5 Flash for translation with quality validation
- Automatic quality checking and regeneration (min 0.6 quality score)

### **Modern Text-to-Speech**
- Gemini TTS 2.5 Flash with superior voice quality
- 6 universal voices working across all languages
- 24kHz sample rate for professional audio
- Smart batching with rate limit management

### **Interactive Quality Control**
- User review workflow before TTS generation
- Side-by-side transcription/translation comparison
- Editable translation segments
- Prevents wasting API quota on poor translations

### **Professional Audio Processing**
- Demucs AI for high-quality vocal isolation (3 model options)
- Audio synchronization with time-stretching
- Background music preservation with mixing controls
- Multiple processing modes (preserve music vs replace all)

### **Scalable Storage**
- Google Cloud Storage integration
- Hybrid local/GCS storage support
- Lifecycle management for temporary files
- Artifact preservation (transcriptions, translations)

## Technical Stack

### **Backend**
- Flask (Python) - Web framework
- FFmpeg - Video/audio processing
- Demucs - AI audio separation

### **AI Services**
- **Gemini 2.5 Flash** - Transcription, translation, quality validation
- **Gemini TTS 2.5 Flash** - Voice generation (NEW)
- Google Cloud Storage - File persistence

### **Storage**
- Local files (development)
- Google Cloud Storage (production)
- Hybrid mode support

### **Languages Supported**
- English (en-US)
- Portuguese (pt-BR)
- Spanish (es)
- French (fr-FR)
- German (de-DE)
- Italian (it-IT)
- Japanese (ja-JP)
- Korean (ko-KR)

## Key Features

### **Core Functionality**
- ✅ Real-time progress tracking
- ✅ **Translation review and editing workflow**
- ✅ **Audio synchronization with timing correction**
- ✅ Multiple voice options (6 universal voices)
- ✅ Intelligent fallback mechanisms
- ✅ Professional audio quality (24kHz TTS)
- ✅ Corporate-ready reliability

### **Audio Processing**
- ✅ 3 Demucs separation models (htdemucs, mdx_extra, mdx)
- ✅ Vocal/music balance control
- ✅ **Time-stretching for timing accuracy**
- ✅ Pitch preservation
- ✅ Quality-aware processing

### **User Experience**
- ✅ Beautiful, modern web interface
- ✅ **Interactive review section**
- ✅ Dynamic voice selection
- ✅ Processing mode controls
- ✅ Real-time status updates
- ✅ Responsive mobile design

### **Quality & Reliability**
- ✅ **Multimodal transcription (audio + video)**
- ✅ **Quality validation and regeneration**
- ✅ **User review before TTS**
- ✅ Comprehensive error handling
- ✅ Automatic retry on rate limiting
- ✅ Detailed logging

## Architecture

### **Processing Pipeline**
```
Upload → Extract Audio → Separate Vocals → Transcribe (Gemini + Video) 
  → Translate (Gemini) → REVIEW (User Edits) → Approve 
  → Generate TTS (Gemini 2.5) → Synchronize → Mix → Final Video
```

### **Module Structure**
```
modules/
├── gemini_client.py          # AI transcription/translation
├── gemini_tts_client.py      # TTS 2.5 Flash voice generation
├── audio_synchronizer.py     # Timing synchronization
├── audio_separator.py        # Demucs vocal separation
├── video_processor.py        # FFmpeg operations
├── file_manager.py           # Storage management
├── gcs_client.py            # Google Cloud Storage
└── gcs_url_generator.py     # Secure download URLs
```

### **API Integration**
- **Gemini AI API** - Transcription, translation, validation
- **Gemini TTS 2.5 Flash** - Voice synthesis
- **Google Cloud Storage API** - File persistence
- **Demucs** - Audio separation

## Configuration

### **Environment Variables**
```env
# Gemini API
GEMINI_API_KEY=your_api_key
GEMINI_TTS_MODEL=gemini-2.5-flash-preview-tts
TTS_BACKEND=gemini

# Audio Sync
ENABLE_AUDIO_SYNC=True
AUDIO_SYNC_MAX_STRETCH=1.3
AUDIO_SYNC_TOLERANCE=0.2

# TTS Settings
TTS_ENABLE_BATCHING=True
TTS_BATCH_SIZE=10
TTS_RATE_LIMIT_DELAY=6.5

# Storage
STORAGE_BACKEND=gcs  # or 'local'
GCS_BUCKET_NAME=your_bucket
```

### **Voice Options**
All voices work with all languages:
- **Zephyr** (Default) - Balanced, professional
- **Puck** - Energetic, dynamic
- **Charon** - Deep, authoritative
- **Kore** - Smooth, warm
- **Fenrir** - Strong, commanding
- **Aoede** - Soft, melodic

## Current Status

### **Production Ready** ✅
- Complete translation pipeline
- User review workflow
- Audio synchronization
- Rate limit management
- Error handling and logging
- Storage integration
- Quality validation

### **Recent Achievements**
- Migrated to Gemini TTS 2.5 Flash
- Implemented review workflow
- Fixed critical audio batching bug
- Added audio synchronization
- Enhanced transcription with video context

## Future Enhancements

### **Near-Term**
1. Voice cloning capabilities
2. Emotion/style control
3. Batch video processing
4. Quality metrics dashboard
5. A/B testing for voices

### **Long-Term**
1. Real-time translation
2. Multi-speaker support
3. Automatic subtitle generation
4. Video editing tools
5. RESTful API access

## Success Metrics

### **Quality**
- TTS: 24kHz, natural prosody
- Timing: < 200ms accuracy
- Separation: High-quality isolation
- Translation: User-validated

### **Performance**
- Upload: < 1 minute
- Processing: 5-15 minutes total
- Review: User-controlled
- Download: Instant (signed URLs)

### **Reliability**
- Comprehensive error handling
- Automatic retry on failures
- Quality validation
- Graceful degradation

The Gemini Video Voiceover Translator is a production-ready system combining state-of-the-art AI with professional audio processing and quality control workflows.
