import logging
from typing import List, Dict
from datetime import datetime
from .researcher import MarketNewsResearcher

logger = logging.getLogger(__name__)

class MarketOrchestrator:
    def __init__(self):
        self.researcher = MarketNewsResearcher()

    async def run_market_analysis(self, video_urls: List[str]):
        """Runs the market analysis on a list of videos (manual trigger)."""
        results = await self.researcher.get_market_summary(video_urls)
        return results

    async def run_scheduled_analysis(self, channel_handle: str = "@markets", max_videos: int = 2):
        """Auto-discovers latest videos from a channel and summarizes them (scheduled trigger)."""
        videos = await self.researcher.discover_latest_videos(channel_handle, max_videos)
        
        if not videos:
            logger.warning("No videos discovered — nothing to summarize.")
            return []

        video_urls = [v["url"] for v in videos]
        results = await self.researcher.get_market_summary(video_urls)
        return results

    def format_slack_message(self, results: List[Dict]) -> str:
        """Formats results into a rich Slack message matching Market Quick Take style."""
        if not results:
            return "❌ No market news found or processed."

        date_str = datetime.now().strftime('%Y-%m-%d')
        msg = f"*📅 Market Quick Take — {date_str}*\n\n"

        for i, res in enumerate(results, 1):
            title = res.get('title', 'Market Update')
            url = res.get('url', '')
            summary = res.get('summary', 'No summary available.').strip()

            msg += f"*📹 Source {i}: \"{title}\"*\n"
            if url:
                msg += f"🔗 {url}\n\n"

            msg += f"{summary}\n\n"
            msg += "───────────────────────────\n\n"

        msg += "_🤖 Automated GCP Market Summary Agent v2.0_"
        return msg
