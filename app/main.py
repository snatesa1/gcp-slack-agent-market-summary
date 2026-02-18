import hmac
import hashlib
import time
import logging
import os
import requests
from fastapi import FastAPI, Request, Form, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from .config import settings
from .orchestrator import MarketOrchestrator

app = FastAPI(title="GCP Market Summary Agent")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────
# 🔐 Security Helpers
# ─────────────────────────────────────────────

async def verify_slack_signature(request: Request):
    """Verifies the signature of the request from Slack."""
    timestamp = request.headers.get("X-Slack-Request-Timestamp")
    signature = request.headers.get("X-Slack-Signature")
    
    if not timestamp or not signature:
        return False
        
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
        
    body = await request.body()
    sig_basestring = f"v0:{timestamp}:{body.decode('utf-8')}"
    
    my_signature = "v0=" + hmac.new(
        settings.SLACK_SIGNING_SECRET.encode("utf-8"),
        sig_basestring.encode("utf-8"),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(my_signature, signature)


def verify_cron_secret(request: Request) -> bool:
    """Verifies the cron secret header from Cloud Scheduler."""
    incoming = request.headers.get("X-Cron-Secret", "")
    expected = settings.CRON_SECRET
    if not expected:
        logger.warning("⚠️ CRON_SECRET not configured — skipping auth check.")
        return True  # Allow in dev/testing
    return hmac.compare_digest(incoming, expected)


# ─────────────────────────────────────────────
# 📤 Slack Delivery (Proactive — like Trading Bot)
# ─────────────────────────────────────────────

async def send_slack_message(channel: str, text: str):
    """Posts a message to a Slack channel using the Bot Token (chat.postMessage)."""
    try:
        resp = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {settings.SLACK_BOT_TOKEN}"},
            json={"channel": channel, "text": text},
            timeout=10
        )
        data = resp.json()
        if not data.get("ok"):
            logger.error(f"🔥 Slack API error: {data.get('error')}")
        else:
            logger.info(f"✅ Message posted to {channel}")
    except Exception as e:
        logger.error(f"🔥 Failed to send Slack message: {e}")


# ─────────────────────────────────────────────
# 🏥 Health Check
# ─────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "environment": "production" if os.getenv("K_SERVICE") else "development"}


# ─────────────────────────────────────────────
# ⏰ Scheduled Endpoint (Cloud Scheduler)
# ─────────────────────────────────────────────

async def run_scheduled_market_news():
    """Background task: discover latest videos, summarize, post to Slack."""
    orchestrator = MarketOrchestrator()
    
    try:
        results = await orchestrator.run_scheduled_analysis(
            channel_handle="@markets",
            max_videos=2
        )
        
        if not results:
            logger.warning("No videos found — sending fallback message.")
            await send_slack_message(
                settings.SLACK_CHANNEL_ID,
                "📭 No new Bloomberg Market videos found today."
            )
            return
        
        message = orchestrator.format_slack_message(results)
        await send_slack_message(settings.SLACK_CHANNEL_ID, message)
        
    except Exception as e:
        logger.error(f"❌ Scheduled market news failed: {e}")
        await send_slack_message(
            settings.SLACK_CHANNEL_ID,
            f"❌ *Market Summary Failed*\nReason: `{str(e)}`"
        )


@app.post("/cron/market-news")
async def cron_market_news(background_tasks: BackgroundTasks, request: Request):
    """Triggered by Cloud Scheduler at 7 PM SGT daily."""
    if not verify_cron_secret(request):
        raise HTTPException(status_code=401, detail="Invalid cron secret")
    
    if not settings.SLACK_CHANNEL_ID:
        raise HTTPException(status_code=500, detail="SLACK_CHANNEL_ID not configured")
    
    background_tasks.add_task(run_scheduled_market_news)
    return {"status": "accepted", "message": "Market news task queued"}


# ─────────────────────────────────────────────
# 💬 Slack Slash Command (/marketnews)
# ─────────────────────────────────────────────

async def run_manual_market_news(response_url: str):
    """Background task for manual /marketnews trigger — now uses auto-discovery."""
    orchestrator = MarketOrchestrator()
    
    try:
        results = await orchestrator.run_scheduled_analysis(
            channel_handle="@markets",
            max_videos=2
        )
        message = orchestrator.format_slack_message(results)
        
        requests.post(response_url, json={
            "text": message,
            "replace_original": "false",
            "response_type": "in_channel"
        }, timeout=10)
        
    except Exception as e:
        logger.error(f"Error in manual market news task: {e}")
        requests.post(response_url, json={
            "text": f"❌ Failed to process market news: `{str(e)}`",
            "replace_original": "false"
        }, timeout=10)


@app.post("/slack/events")
async def slack_events(background_tasks: BackgroundTasks, request: Request):
    """Unified endpoint for Slack slash commands."""
    if not await verify_slack_signature(request):
        raise HTTPException(status_code=401, detail="Invalid signature")

    form_data = await request.form()
    command = form_data.get("command")
    
    if command == "/marketnews":
        response_url = form_data.get("response_url")
        background_tasks.add_task(run_manual_market_news, response_url)
        return JSONResponse(content={
            "response_type": "ephemeral",
            "text": "🗞️ Discovering & summarizing latest Bloomberg market videos... ⏳"
        })

    return {"status": "ignored"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
