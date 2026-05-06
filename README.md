# Gemini Video Voiceover Translator

Translate the narration of a video into another language while keeping the
original timing, optionally preserving the background music. End-to-end on
Google Cloud: Vertex AI Gemini for transcription/translation, Cloud TTS
(Gemini 2.5 Flash or Chirp 3 HD) for the new voice, Demucs for vocal
isolation, FFmpeg for everything else.

A live deploy of this repo is running at
`https://gemini-voiceover-713488125678.us-central1.run.app`.

---

## Pipeline at a glance

```
                              ┌───────────────────────────┐
                              │   Browser (web upload)    │
                              └─────────────┬─────────────┘
                                            │ POST /upload  (≤ 32 MiB)
                                            ▼
┌──────────────────────────── Cloud Run (Flask + gunicorn) ───────────────────────────┐
│                                                                                      │
│  ┌──────────────────┐                                                                │
│  │ Save upload      │ ───► gs://…/uploads/<id>.mp4                                   │
│  └────────┬─────────┘                                                                │
│           ▼                                                                          │
│  ┌──────────────────┐                                                                │
│  │ FFmpeg extract   │ ───► audio.wav (44.1 kHz stereo)                               │
│  │  + probe info    │                                                                │
│  └────────┬─────────┘                                                                │
│           ▼                                                                          │
│  ┌──────────────────┐    ┌──────────────────────────────────┐                        │
│  │ Demucs separate  │ ─► │ vocals.wav      background.wav   │                        │
│  │ (htdemucs/mdx)   │    └──────────────────────────────────┘                        │
│  └────────┬─────────┘    (skipped in `replace_all` mode)                             │
│           │                                                                          │
│           ▼  vocals.wav + video frames                                               │
│  ┌─────────────────────────────────────┐    Vertex AI Gemini 2.5 Flash               │
│  │ Transcribe (multimodal)             │ ─► [{start_time, end_time, text}, …]        │
│  │  + quality_score validate / regen   │                                             │
│  └────────┬────────────────────────────┘                                             │
│           ▼                                                                          │
│  ┌─────────────────────────────────────┐    Gemini 2.5 Flash                         │
│  │ Translate to target language        │ ─► segments translated                      │
│  │  uses LANGUAGE_NAMES (zh/nl/pl/ru…) │                                             │
│  └────────┬────────────────────────────┘                                             │
│           ▼                                                                          │
│  ╔═════════════════════════════════════╗                                             │
│  ║  REVIEW (background thread waits)   ║ ◄── GET  /api/review/<id>                   │
│  ║  bound by REVIEW_TIMEOUT_SEC (30 m) ║ ──► POST /api/approve/<id>  (with edits)    │
│  ╚════════════════╤════════════════════╝                                             │
│                   ▼  approved + (optionally edited) translation                      │
│  ┌─────────────────────────────────────┐    Vertex AI Cloud TTS                      │
│  │ Generate TTS — parallel             │   ┌───────────────────────────────────┐    │
│  │  ThreadPoolExecutor                 │ ► │ TTS_PARALLEL_WORKERS = 5          │    │
│  │  Gemini 2.5 Flash TTS  /  Chirp 3   │   │ retries = TTS_MAX_RETRIES         │    │
│  └────────┬────────────────────────────┘   └───────────────────────────────────┘    │
│           ▼  N × segment_NNN_*.wav (24 kHz)                                          │
│  ┌─────────────────────────────────────┐                                             │
│  │ Duration adjustment loop            │  Gemini shortens overruns;                  │
│  │  (≤ MAX_DURATION_ADJUSTMENT_ATTEMPTS)│  regenerates ONLY changed indices          │
│  └────────┬────────────────────────────┘                                             │
│           ▼                                                                          │
│  ┌─────────────────────────────────────┐                                             │
│  │ Per-segment time-stretch (atempo)   │  pitch-preserving                           │
│  │  AudioSynchronizer                  │  bounded by MIN/MAX_SPEAKING_RATE           │
│  └────────┬────────────────────────────┘                                             │
│           ▼                                                                          │
│  ┌─────────────────────────────────────┐                                             │
│  │ Concat with drift correction        │  truncate overruns +                        │
│  │  _build_concat_timeline (pure)      │  10 ms afade-out on cuts                    │
│  └────────┬────────────────────────────┘                                             │
│           ▼                                                                          │
│  ┌─────────────────────────────────────┐                                             │
│  │ loudnorm I=-16 : TP=-1.5 : LRA=11   │  single pass, applied once                  │
│  │  (ENABLE_LOUDNORM)                  │                                             │
│  └────────┬────────────────────────────┘                                             │
│           ▼                                                                          │
│  ┌─────────────────────────────────────┐                                             │
│  │ Mix with background.wav             │  vocal_balance                              │
│  │  (preserve_music mode only)         │                                             │
│  └────────┬────────────────────────────┘                                             │
│           ▼                                                                          │
│  ┌─────────────────────────────────────┐                                             │
│  │ FFmpeg mux: video copy + AAC        │  OUTPUT_AUDIO_BITRATE = 192k                │
│  │                                     │  stereo, 48 kHz                             │
│  └────────┬────────────────────────────┘                                             │
└───────────┼──────────────────────────────────────────────────────────────────────────┘
            ▼
  ┌──────────────────────────────────────────────┐
  │  gs://<project>-gemini-voiceover/outputs/    │ ─► signed URL ─► browser download   │
  └──────────────────────────────────────────────┘
```

---

## Supported languages

All twelve languages share the six universal Gemini personas (Zephyr, Puck,
Charon, Kore, Fenrir, Aoede). Chirp 3 HD voices follow the
`<lang>-Chirp3-HD-<Persona>` pattern but coverage varies per language —
when a language is known to have gaps, the UI surfaces a recommendation.

| Code  | Language                    | Recommended TTS |
|-------|-----------------------------|-----------------|
| en-US | English (US)                | (default)       |
| pt-BR | Brazilian Portuguese        | (default)       |
| es-ES | Spanish (Spain)             | (default)       |
| fr-FR | French (France)             | (default)       |
| de-DE | German (Germany)            | (default)       |
| it-IT | Italian (Italy)             | (default)       |
| ja-JP | Japanese (Japan)            | (default)       |
| ko-KR | Korean (South Korea)        | (default)       |
| nl-NL | Dutch (Netherlands)         | (default)       |
| pl-PL | Polish (Poland)             | (default)       |
| ru-RU | Russian (Russia)            | (default)       |
| zh-CN | Chinese (Mandarin, China)   | **Gemini TTS**  |

The frontend hits `GET /api/tts-recommendation/<lang>` whenever the
language or backend selector changes, and renders an inline hint when
`is_override` is true.

---

## Configuration

Authentication is **Application Default Credentials only** (no API keys).
Locally: `gcloud auth application-default login`. On Cloud Run: the
attached service account.

Required:

```env
GOOGLE_CLOUD_PROJECT=your-gcp-project-id
GOOGLE_CLOUD_LOCATION=us-central1
```

Storage (GCS strongly recommended in production; local mode is ephemeral):

```env
STORAGE_BACKEND=gcs
GCS_BUCKET_NAME=your-gcs-bucket
GCS_TEMP_FILE_RETENTION_DAYS=7
```

Models:

```env
TRANSCRIPTION_MODEL=gemini-2.5-flash
TRANSLATION_MODEL=gemini-2.5-flash
GEMINI_TTS_MODEL=gemini-2.5-flash-tts        # NOT ...-preview-tts
TTS_BACKEND=gemini                            # gemini | chirp3
```

Performance / sync (defaults shown):

```env
TTS_PARALLEL_WORKERS=5                        # parallel TTS calls
TTS_MAX_RETRIES=5                             # honoured by retry loop
ENABLE_AUDIO_SYNC=True
MAX_TIMING_DIFFERENCE_SEC=0.5
ENFORCE_ORIGINAL_DURATION=True
MAX_DURATION_ADJUSTMENT_ATTEMPTS=3
MIN_SPEAKING_RATE=0.85
MAX_SPEAKING_RATE=1.15
REVIEW_TIMEOUT_SEC=1800                       # 30 min cap on awaiting approval
```

Final-render audio:

```env
OUTPUT_AUDIO_BITRATE=192k
OUTPUT_AUDIO_SAMPLE_RATE=48000
OUTPUT_AUDIO_CHANNELS=2
ENABLE_LOUDNORM=True
LOUDNORM_TARGET_I=-16
LOUDNORM_TP=-1.5
LOUDNORM_LRA=11
```

Full list with comments: `.env.example`.

---

## Local development

Requires Python 3.11+, FFmpeg, libsndfile, and (for Demucs) PyTorch.

```bash
gcloud auth application-default login
cp .env.example .env       # edit GOOGLE_CLOUD_PROJECT / GCS_BUCKET_NAME
pip install -r requirements.txt
python app.py              # serves on http://localhost:8080
```

Run the test suite (no FFmpeg or live cloud needed — heavy deps are stubbed
in `tests/conftest.py`):

```bash
pip install pytest
pytest -q
```

---

## Deploy to Cloud Run

```bash
gcloud config set project <PROJECT_ID>
./deploy.sh
```

The script:

1. Verifies `gcloud` is installed and a project is set.
2. Creates `gs://<PROJECT_ID>-gemini-voiceover` in `us-central1` if it
   doesn't exist (override with `GCS_BUCKET_NAME=…`).
3. Runs `gcloud run deploy --source .`, building the container via Cloud
   Build, with `--memory 4Gi --cpu 2 --timeout 3600` and the env vars
   above wired in.
4. Prints the resulting service URL.

Tunables you can override before invoking:

```bash
MEMORY=8Gi CPU=4 TTS_PARALLEL_WORKERS=8 \
  REVIEW_TIMEOUT_SEC=900 ./deploy.sh
```

APIs that must be enabled on the project (the script doesn't check; do
this once):

```bash
gcloud services enable \
  run.googleapis.com \
  cloudbuild.googleapis.com \
  storage.googleapis.com \
  texttospeech.googleapis.com \
  aiplatform.googleapis.com \
  artifactregistry.googleapis.com
```

---

## Project layout

```
gemini-voiceover/
├── app.py                      # Flask routes + background processing thread
├── config.py                   # All env-driven configuration
├── deploy.sh                   # Cloud Run deploy + GCS bucket bootstrap
├── Dockerfile                  # python:3.11-slim + ffmpeg, gunicorn 600s
├── requirements.txt
├── modules/
│   ├── gemini_client.py        # Vertex AI: transcribe, translate, shorten
│   ├── google_tts_client.py    # Vertex AI Cloud TTS (parallel synth)
│   ├── audio_separator.py      # Demucs vocal/music separation
│   ├── audio_synchronizer.py   # Per-segment atempo time-stretch
│   ├── video_processor.py      # FFmpeg: extract, concat, mux, loudnorm
│   ├── file_manager.py         # Local + GCS storage abstraction
│   ├── gcs_client.py           # GCS bucket operations + lifecycle
│   ├── gcs_url_generator.py    # Signed URL generation
│   └── error_handler.py        # Gemini-specific error mapping
├── templates/index.html        # Single-page upload/review/download UI
├── static/
│   ├── css/style.css
│   └── js/app.js               # Polls /status, renders review, fetches recs
└── tests/                      # pytest, 39 cases, no live cloud calls
```

---

## API endpoints

| Method | Path                                     | Purpose                                  |
|--------|------------------------------------------|------------------------------------------|
| GET    | `/`                                      | Upload UI                                |
| POST   | `/upload`                                | Start a translation job                  |
| GET    | `/status/<id>`                           | Poll job state + progress                |
| GET    | `/api/review/<id>`                       | Fetch transcription + translation        |
| POST   | `/api/approve/<id>`                      | Approve (and optionally edit) translation|
| GET    | `/download/<id>`                         | Fetch the rendered video (or signed URL) |
| GET    | `/api/voices/<backend>/<lang>`           | List voices for a backend + language     |
| GET    | `/api/voices/<lang>`                     | Voices for default backend (legacy)      |
| GET    | `/api/tts-recommendation/<lang>`         | Recommended TTS for a language           |

---

## Known limitations

- **Upload cap is 32 MiB.** Cloud Run's HTTP/1 request body limit;
  enabling `--use-http2` requires an h2c-capable worker (gunicorn-sync /
  gthread doesn't qualify). For larger files the path forward is direct
  upload to GCS via signed URL, then job kick-off — not implemented.
- **State is in-memory.** `processing_status` lives in the Flask process
  dict; if Cloud Run scales beyond one instance, `/status/<id>` and
  `/api/approve/<id>` may hit a different replica and return 404.
  Move to Redis or Firestore to scale horizontally.
- **`MAX_CONCURRENT_JOBS` is informational.** No semaphore enforces it
  yet; the only backpressure is gunicorn's thread pool (8 by default).
- **Mandarin Chirp 3 HD personas may 404.** Coverage varies per voice in
  Vertex; the UI nudges users toward Gemini TTS for `zh-CN` for that
  reason. The fix is dynamic voice-list discovery against
  `texttospeech.list_voices(language_code=…)`.

---

## License

Apache 2.0 — see `LICENSE`.
