#!/bin/bash
# init_gcp.sh: Initial setup for GCP project

# Try to load PROJECT_ID from .env
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        clean_line=$(echo "$line" | tr -d '\r')
        if [[ $clean_line == GCP_PROJECT_ID=* ]]; then
            PROJECT_ID="${clean_line#*=}"
            break
        fi
    done < .env
fi

# Fallback to default if not found
PROJECT_ID=${PROJECT_ID:-"gen-lang-client-0904402483"}

echo "🔐 Authenticating with Google Cloud..."
gcloud auth login

echo "🎯 Setting project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

echo "🚀 Enabling required APIs..."
gcloud services enable \
  aiplatform.googleapis.com \
  secretmanager.googleapis.com \
  run.googleapis.com \
  artifactregistry.googleapis.com \
  cloudbuild.googleapis.com \
  iam.googleapis.com \
  compute.googleapis.com \
  cloudscheduler.googleapis.com \
  youtube.googleapis.com

echo "✅ Initialization complete!"
