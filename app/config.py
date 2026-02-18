from pydantic_settings import BaseSettings
from google.cloud import secretmanager
import os
import google.auth
import logging

logger = logging.getLogger(__name__)

class Settings(BaseSettings):
    PROJECT_ID: str = ""
    _secrets: dict = {}
    
    # Internal secret IDs
    _SECRET_IDS = [
        "SLACK_BOT_TOKEN",
        "SLACK_SIGNING_SECRET",
        "YOUTUBE_API_KEY",
        "SLACK_CHANNEL_ID",
        "CRON_SECRET"
    ]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.PROJECT_ID:
            try:
                _, project_id = google.auth.default()
                self.PROJECT_ID = project_id or os.getenv("GOOGLE_CLOUD_PROJECT", "default-project")
            except Exception:
                self.PROJECT_ID = os.getenv("GOOGLE_CLOUD_PROJECT", "default-project")

    def _get_secret_manager_value(self, secret_id: str) -> str:
        try:
            client = secretmanager.SecretManagerServiceClient()
            name = f"projects/{self.PROJECT_ID}/secrets/{secret_id}/versions/latest"
            response = client.access_secret_version(request={"name": name})
            return response.payload.data.decode("UTF-8")
        except Exception as e:
            logger.warning(f"⚠️ Secret {secret_id} not found in Secret Manager or access denied: {e}")
            return os.getenv(secret_id, "")

    @property
    def SLACK_BOT_TOKEN(self) -> str:
        if "SLACK_BOT_TOKEN" not in self._secrets:
            self._secrets["SLACK_BOT_TOKEN"] = self._get_secret_manager_value("SLACK_BOT_TOKEN")
        return self._secrets["SLACK_BOT_TOKEN"]

    @property
    def SLACK_SIGNING_SECRET(self) -> str:
        if "SLACK_SIGNING_SECRET" not in self._secrets:
            self._secrets["SLACK_SIGNING_SECRET"] = self._get_secret_manager_value("SLACK_SIGNING_SECRET")
        return self._secrets["SLACK_SIGNING_SECRET"]


    @property
    def VERTEX_LOCATION(self) -> str:
        return "asia-southeast1"

    @property
    def YOUTUBE_API_KEY(self) -> str:
        if "YOUTUBE_API_KEY" not in self._secrets:
            # Try to get from Secret Manager first
            val = self._get_secret_manager_value("YOUTUBE_API_KEY")
            if not val:
                # Fallback to env var
                val = os.getenv("YOUTUBE_API_KEY", "")
            self._secrets["YOUTUBE_API_KEY"] = val
        return self._secrets["YOUTUBE_API_KEY"]

    @property
    def SLACK_CHANNEL_ID(self) -> str:
        if "SLACK_CHANNEL_ID" not in self._secrets:
            val = self._get_secret_manager_value("SLACK_CHANNEL_ID")
            if not val:
                val = os.getenv("SLACK_CHANNEL_ID", "")
            self._secrets["SLACK_CHANNEL_ID"] = val
        return self._secrets["SLACK_CHANNEL_ID"]

    @property
    def CRON_SECRET(self) -> str:
        if "CRON_SECRET" not in self._secrets:
            val = self._get_secret_manager_value("CRON_SECRET")
            if not val:
                val = os.getenv("CRON_SECRET", "")
            self._secrets["CRON_SECRET"] = val
        return self._secrets["CRON_SECRET"]

    @property
    def VERTEX_MODEL(self) -> str:
        return os.getenv("VERTEX_MODEL", "gemini-2.5-flash")

settings = Settings()
