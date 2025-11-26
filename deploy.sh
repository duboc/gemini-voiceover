#!/bin/bash

# Cloud Run Deployment Script for Gemini Voiceover

# Exit on error
set -e

echo "🚀 Preparing to deploy Gemini Voiceover to Cloud Run..."

# Check if gcloud is installed
if ! command -v gcloud &> /dev/null; then
    echo "❌ Error: gcloud CLI is not installed."
    echo "Please install it from: https://cloud.google.com/sdk/docs/install"
    exit 1
fi

# (Optional) Check for optional env vars if needed, but main auth is via ADC
echo "🔑 Using Application Default Credentials (ADC) via Cloud Run Service Account"

# Project ID
PROJECT_ID=$(gcloud config get-value project)
if [ -z "$PROJECT_ID" ]; then
    echo "⚠️  No default Google Cloud project set."
    read -p "Enter your Google Cloud Project ID: " PROJECT_ID
    gcloud config set project $PROJECT_ID
fi

echo "✅ Using Project ID: $PROJECT_ID"

# Service Name
SERVICE_NAME="gemini-voiceover"
REGION="us-central1"

echo "📦 Deploying to Cloud Run (this may take a few minutes)..."
echo "   - Building container from source"
echo "   - Deploying to region: $REGION"
echo "   - Service name: $SERVICE_NAME"

gcloud run deploy $SERVICE_NAME \
    --source . \
    --platform managed \
    --region $REGION \
    --allow-unauthenticated \
    --use-http2 \
    --memory 4Gi \
    --cpu 2 \
    --set-env-vars GOOGLE_CLOUD_PROJECT=$PROJECT_ID \
    --set-env-vars GOOGLE_CLOUD_LOCATION=$REGION \
    --set-env-vars FLASK_DEBUG=False \
    --set-env-vars MAX_FILE_SIZE_MB=500 \
    --timeout 300

echo ""
echo "🎉 Deployment Complete!"
