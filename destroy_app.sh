#!/bin/bash
# destroy_app.sh: Cleanup all created resources

SERVICE_NAME="market-summary-agent"
SCHEDULER_JOB="market-news-daily"
REGION="asia-southeast1"

echo "⚠️  WARNING: This will delete the Cloud Run service and scheduler job."
read -p "Are you sure? (y/N): " confirm
if [[ $confirm != [yY] ]]; then
    echo "Deletion cancelled."
    exit 1
fi

PROJECT_ID=$(gcloud config get-value project)

# 1. Delete Cloud Scheduler Job
echo "🗑️ Deleting Cloud Scheduler job: $SCHEDULER_JOB..."
gcloud scheduler jobs delete $SCHEDULER_JOB --location=$REGION --quiet 2>/dev/null

# 2. Delete Cloud Run Service
echo "🗑️ Deleting Cloud Run service: $SERVICE_NAME..."
gcloud run services delete $SERVICE_NAME --region $REGION --quiet

echo "✅ Resources destroyed successfully."
