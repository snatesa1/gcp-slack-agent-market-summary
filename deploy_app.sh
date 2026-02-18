#!/bin/bash

# Configuration
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        clean_line=$(echo "$line" | tr -d '\r')
        [[ $clean_line =~ ^#.* ]] && continue
        [[ -z $clean_line ]] && continue
        export "$clean_line"
    done < .env
fi

PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project)}
SERVICE_NAME="market-summary-agent"
REGION="asia-southeast1"

# Service Account Logic: Use VERTEX from .env if available, else fallback to default
if [ -n "$VERTEX" ]; then
    SA_EMAIL=$VERTEX
    echo "👤 Using service account from .env: $SA_EMAIL"
else
    PROJECT_NUMBER=$(gcloud projects describe $PROJECT_ID --format="value(projectNumber)")
    SA_EMAIL="$PROJECT_NUMBER-compute@developer.gserviceaccount.com"
    echo "👤 Using default compute service account: $SA_EMAIL"
fi

echo "🚀 Deploying $SERVICE_NAME to Google Cloud Run in $REGION..."

# 1. Grant Permissions
echo "🔑 Granting IAM permissions to service account..."
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"

gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/aiplatform.user"

# 2. Build and Push Image
gcloud builds submit --tag gcr.io/$PROJECT_ID/$SERVICE_NAME

# 3. Deploy to Cloud Run
gcloud run deploy $SERVICE_NAME \
  --image gcr.io/$PROJECT_ID/$SERVICE_NAME \
  --platform managed \
  --region $REGION \
  --allow-unauthenticated \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --set-env-vars="GOOGLE_CLOUD_PROJECT=$PROJECT_ID,VERTEX_MODEL=${VERTEX_MODEL:-gemini-2.5-flash}" \
  --service-account $SA_EMAIL

# 4. Create/Update Cloud Scheduler Job (7:00 PM SGT = 11:00 UTC)
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region $REGION --format 'value(status.url)')
SCHEDULER_JOB="market-news-daily"

echo "⏰ Setting up Cloud Scheduler job: $SCHEDULER_JOB"

# Delete existing job if present (idempotent redeploy)
gcloud scheduler jobs delete $SCHEDULER_JOB --location=$REGION --quiet 2>/dev/null

gcloud scheduler jobs create http $SCHEDULER_JOB \
  --location=$REGION \
  --schedule="0 19 * * *" \
  --uri="$SERVICE_URL/cron/market-news" \
  --http-method=POST \
  --headers="X-Cron-Secret=$CRON_SECRET" \
  --time-zone="Asia/Singapore" \
  --attempt-deadline=300s

echo "✅ Deployment complete!"
echo "🌐 Service URL: $SERVICE_URL"
echo "⏰ Scheduler: $SCHEDULER_JOB (7:00 PM SGT daily)"
gcloud scheduler jobs describe $SCHEDULER_JOB --location=$REGION --format="table(name,schedule,timeZone,state)"
