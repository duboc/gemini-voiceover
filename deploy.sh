#!/bin/bash
# Cloud Run deploy script for Gemini Voiceover.
# Auth uses Application Default Credentials via the Cloud Run service account.

set -e

echo "🚀 Preparing to deploy Gemini Voiceover to Cloud Run..."

if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed."
    echo "   Install: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

echo "🔑 Using Application Default Credentials (ADC) via Cloud Run Service Account"

# ----- Project ---------------------------------------------------------------
PROJECT_ID=$(gcloud config get-value project 2>/dev/null || echo "")
if [ -z "$PROJECT_ID" ]; then
    echo "⚠️  No default Google Cloud project set."
    read -rp "Enter your Google Cloud Project ID: " PROJECT_ID
    gcloud config set project "$PROJECT_ID"
fi
echo "✅ Using Project ID: $PROJECT_ID"

# ----- Service / region ------------------------------------------------------
SERVICE_NAME="${SERVICE_NAME:-gemini-voiceover}"
REGION="${REGION:-us-central1}"

# ----- GCS bucket bootstrap --------------------------------------------------
# Cloud Run filesystems are ephemeral and per-instance; persistent storage and
# cross-instance state require GCS. Default bucket name is derived from the
# project ID; override by exporting GCS_BUCKET_NAME before running.
GCS_BUCKET_NAME="${GCS_BUCKET_NAME:-${PROJECT_ID}-gemini-voiceover}"

echo "🪣 Ensuring GCS bucket gs://$GCS_BUCKET_NAME exists in $REGION..."
if gcloud storage buckets describe "gs://$GCS_BUCKET_NAME" >/dev/null 2>&1; then
    echo "   ✅ Bucket already exists"
else
    echo "   📦 Creating bucket..."
    gcloud storage buckets create "gs://$GCS_BUCKET_NAME" \
        --project="$PROJECT_ID" \
        --location="$REGION" \
        --uniform-bucket-level-access
    echo "   ✅ Bucket created"
fi

# ----- Tunables (override via env before invoking) ---------------------------
TTS_PARALLEL_WORKERS="${TTS_PARALLEL_WORKERS:-5}"
ENABLE_LOUDNORM="${ENABLE_LOUDNORM:-True}"
OUTPUT_AUDIO_BITRATE="${OUTPUT_AUDIO_BITRATE:-192k}"
REVIEW_TIMEOUT_SEC="${REVIEW_TIMEOUT_SEC:-1800}"
# Cloud Run HTTP/1 caps the request body at 32 MiB. Going higher requires
# HTTP/2 (which gunicorn-sync/gthread does not speak as h2c), or routing
# uploads directly to GCS via signed URLs (a Lote 3 item).
MAX_FILE_SIZE_MB="${MAX_FILE_SIZE_MB:-32}"
MEMORY="${MEMORY:-8Gi}"
CPU="${CPU:-2}"

# Cloud Run inbound request timeout. 3600s (1h) is the gen2 max and lets the
# review-step polling loop run to completion; the worker-side budget is set
# in the Dockerfile via gunicorn --timeout.
CLOUD_RUN_TIMEOUT="${CLOUD_RUN_TIMEOUT:-3600}"

# Scale-to-zero saves cost when idle. Max pinned to 1 because
# processing_status lives in process memory — polling /status from a
# different replica returns 404. Raise max once state moves to
# Redis/Firestore.
MIN_INSTANCES="${MIN_INSTANCES:-0}"
MAX_INSTANCES="${MAX_INSTANCES:-1}"

echo ""
echo "📦 Deploying $SERVICE_NAME to Cloud Run ($REGION)..."
echo "   Memory:    $MEMORY"
echo "   CPU:       $CPU"
echo "   Instances: min=$MIN_INSTANCES max=$MAX_INSTANCES (single-instance until Lote 3)"
echo "   Timeout:   ${CLOUD_RUN_TIMEOUT}s"
echo "   Bucket:    $GCS_BUCKET_NAME"
echo "   Workers:   $TTS_PARALLEL_WORKERS parallel TTS"
echo "   Loudnorm:  $ENABLE_LOUDNORM"

gcloud run deploy "$SERVICE_NAME" \
    --source . \
    --platform managed \
    --region "$REGION" \
    --allow-unauthenticated \
    --memory "$MEMORY" \
    --cpu "$CPU" \
    --no-cpu-throttling \
    --cpu-boost \
    --min-instances "$MIN_INSTANCES" \
    --max-instances "$MAX_INSTANCES" \
    --timeout "$CLOUD_RUN_TIMEOUT" \
    --set-env-vars "GOOGLE_CLOUD_PROJECT=$PROJECT_ID" \
    --set-env-vars "GOOGLE_CLOUD_LOCATION=$REGION" \
    --set-env-vars "FLASK_DEBUG=False" \
    --set-env-vars "MAX_FILE_SIZE_MB=$MAX_FILE_SIZE_MB" \
    --set-env-vars "STORAGE_BACKEND=gcs" \
    --set-env-vars "GCS_BUCKET_NAME=$GCS_BUCKET_NAME" \
    --set-env-vars "REVIEW_TIMEOUT_SEC=$REVIEW_TIMEOUT_SEC" \
    --set-env-vars "TTS_PARALLEL_WORKERS=$TTS_PARALLEL_WORKERS" \
    --set-env-vars "ENABLE_LOUDNORM=$ENABLE_LOUDNORM" \
    --set-env-vars "OUTPUT_AUDIO_BITRATE=$OUTPUT_AUDIO_BITRATE" \
    --set-env-vars "GEMINI_API_LOCATION=global"

echo ""
echo "🎉 Deployment complete!"
echo "   Service URL: $(gcloud run services describe "$SERVICE_NAME" --region "$REGION" --format='value(status.url)' 2>/dev/null || echo 'check console')"
