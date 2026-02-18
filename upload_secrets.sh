#!/bin/bash
# upload_secrets.sh: Upload secrets from .env to GCP Secret Manager

# Load .env file
if [ -f .env ]; then
    while IFS= read -r line || [ -n "$line" ]; do
        clean_line=$(echo "$line" | tr -d '\r')
        [[ $clean_line =~ ^#.* ]] && continue
        [[ -z $clean_line ]] && continue
        export "$clean_line"
    done < .env
fi

PROJECT_ID=${GCP_PROJECT_ID:-$(gcloud config get-value project)}

echo "🛰️ Uploading secrets to project: $PROJECT_ID"

create_and_upload_secret() {
    SECRET_NAME=$1
    SECRET_VALUE=$2

    if [ -z "$SECRET_VALUE" ]; then
        echo "⚠️ $SECRET_NAME is empty in .env, skipping..."
        return
    fi

    # Check if secret exists
    gcloud secrets describe $SECRET_NAME --project=$PROJECT_ID > /dev/null 2>&1
    if [ $? -ne 0 ]; then
        echo "🆕 Creating secret: $SECRET_NAME"
        gcloud secrets create $SECRET_NAME --replication-policy="automatic" --project=$PROJECT_ID
    fi

    echo "⬆️ Uploading version for: $SECRET_NAME"
    echo -n "$SECRET_VALUE" | gcloud secrets versions add $SECRET_NAME --data-file=- --project=$PROJECT_ID
}

# Upload Slack secrets
create_and_upload_secret "SLACK_BOT_TOKEN" "$SLACK_BOT_TOKEN"
create_and_upload_secret "SLACK_SIGNING_SECRET" "$SLACK_SIGNING_SECRET"
create_and_upload_secret "SLACK_CHANNEL_ID" "$SLACK_CHANNEL_ID"

# Upload YouTube API Key
create_and_upload_secret "YOUTUBE_API_KEY" "$YOUTUBE_API_KEY"

# Upload Cron Secret (for Cloud Scheduler auth)
create_and_upload_secret "CRON_SECRET" "$CRON_SECRET"

echo "✅ All secrets processed!"
