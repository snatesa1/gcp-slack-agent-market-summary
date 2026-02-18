import logging
import os
import tempfile
from typing import List, Dict, Optional
from googleapiclient.discovery import build
from langchain_google_vertexai import VertexAI
from .config import settings

logger = logging.getLogger(__name__)

class MarketNewsResearcher:
    def __init__(self):
        self.llm = VertexAI(
            model_name=settings.VERTEX_MODEL,
            location=settings.VERTEX_LOCATION,
            temperature=0.2
        )

    async def discover_latest_videos(self, channel_handle: str = "@markets", max_results: int = 2) -> List[Dict]:
        """Uses YouTube Data API to discover the latest videos from a channel handle.
        
        Flow: resolve @handle → channelId, then search for latest uploads.
        Quota cost: ~200 units (channels.list=1 + search.list=100). Safe for daily use.
        """
        try:
            if not settings.YOUTUBE_API_KEY:
                logger.error("YOUTUBE_API_KEY not configured — cannot discover videos.")
                return []

            youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)

            # Step 1: Resolve @handle → channelId
            clean_handle = channel_handle.lstrip("@")
            channel_response = youtube.channels().list(
                part="id,snippet",
                forHandle=clean_handle
            ).execute()

            if not channel_response.get("items"):
                logger.error(f"Could not resolve YouTube handle: {channel_handle}")
                return []

            channel_id = channel_response["items"][0]["id"]
            channel_name = channel_response["items"][0]["snippet"]["title"]
            logger.info(f"✅ Resolved {channel_handle} → {channel_name} ({channel_id})")

            # Step 2: Search for latest videos from this channel
            search_response = youtube.search().list(
                part="id,snippet",
                channelId=channel_id,
                order="date",
                type="video",
                maxResults=max_results
            ).execute()

            videos = []
            for item in search_response.get("items", []):
                video_id = item["id"]["videoId"]
                videos.append({
                    "video_id": video_id,
                    "title": item["snippet"]["title"],
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "published_at": item["snippet"]["publishedAt"]
                })

            logger.info(f"🎬 Found {len(videos)} latest videos from {channel_name}")
            for v in videos:
                logger.info(f"  → {v['title']} ({v['published_at']})")

            return videos

        except Exception as e:
            logger.error(f"❌ Error discovering videos from {channel_handle}: {e}")
            return []


    def get_video_id(self, url: str) -> str:
        """Extracts video ID from YouTube URL."""
        if "v=" in url:
            return url.split("v=")[1].split("&")[0]
        elif "youtu.be/" in url:
            return url.split("youtu.be/")[1].split("?")[0]
        return url

    async def fetch_video_metadata(self, video_id: str) -> Dict[str, str]:
        """Fetches video title and description using YouTube Data API."""
        try:
            if not settings.YOUTUBE_API_KEY:
                logger.warning("YouTube API Key (YOUTUBE_API_KEY) not configured, skipping metadata fetch.")
                return {}
            
            youtube = build("youtube", "v3", developerKey=settings.YOUTUBE_API_KEY)
            request = youtube.videos().list(
                part="snippet",
                id=video_id
            )
            response = request.execute()
            
            if response.get("items"):
                snippet = response["items"][0]["snippet"]
                return {
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", "")
                }
            return {}
        except Exception as e:
            if "blocked" in str(e).lower() or "403" in str(e):
                logger.error(f"🛑 YouTube API Key blocked or restricted: {e}")
                logger.error("👉 FIX: Go to GCP Console -> API & Services -> Credentials.")
                logger.error("👉 Check 'API restrictions' for your key and ensure 'YouTube Data API v3' is enabled/allowed.")
            else:
                logger.error(f"Error fetching YouTube metadata for {video_id}: {e}")
            return {}

    async def fetch_youtube_transcript(self, video_id: str) -> str:
        """Fetches transcript for a YouTube video with cookie-based auth to bypass cloud IP blocks."""
        try:
            import http.cookiejar
            import requests as req
            from youtube_transcript_api import YouTubeTranscriptApi
            
            # Use cookies to bypass YouTube's cloud IP blocking
            cookie_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "cookies.txt")
            api_kwargs = {}
            
            if os.path.exists(cookie_path):
                logger.info(f"Loading YouTube cookies from {cookie_path}")
                cj = http.cookiejar.MozillaCookieJar(cookie_path)
                cj.load(ignore_discard=True, ignore_expires=True)
                session = req.Session()
                session.cookies = cj
                api_kwargs["http_client"] = session
            else:
                logger.warning("No cookies.txt found — transcript fetch may be blocked on cloud IPs")
            
            api = YouTubeTranscriptApi(**api_kwargs)
            logger.info(f"Fetching transcript for {video_id}")
            transcript_list = api.list(video_id)
            
            transcript_obj = None
            
            # Priority 1: Manually created English
            try:
                transcript_obj = transcript_list.find_manually_created_transcript(['en', 'en-US', 'en-GB'])
                logger.info(f"Found manually created English transcript for {video_id}")
            except Exception:
                pass
            
            # Priority 2: Auto-generated English
            if not transcript_obj:
                try:
                    transcript_obj = transcript_list.find_generated_transcript(['en', 'en-US', 'en-GB'])
                    logger.info(f"Found auto-generated English transcript for {video_id}")
                except Exception:
                    pass
            
            # Priority 3: Any available transcript
            if not transcript_obj:
                for t in transcript_list:
                    transcript_obj = t
                    logger.info(f"Using {t.language_code} transcript for {video_id}")
                    break
            
            if transcript_obj:
                fetched = transcript_obj.fetch()
                text = " ".join([snippet.text for snippet in fetched])
                logger.info(f"✅ Transcript fetched ({len(text)} chars) for {video_id}")
                return text
            
            logger.warning(f"No transcripts available for {video_id}")
            return ""
            
        except Exception as e:
            logger.warning(f"Transcript fetch failed for {video_id}: {e}")
            return ""

    async def _download_audio_pytube(self, video_url: str) -> Optional[str]:
        """Tries to download audio using pytube."""
        try:
            from pytube import YouTube
            logger.info(f"Attempting audio download via pytube: {video_url}")
            yt = YouTube(video_url)
            audio_stream = yt.streams.filter(only_audio=True).first()
            if not audio_stream:
                return None
            
            out_file = audio_stream.download(output_path=tempfile.gettempdir())
            base, ext = os.path.splitext(out_file)
            new_file = base + '.m4a'
            if os.path.exists(new_file):
                os.remove(new_file)
            os.rename(out_file, new_file)
            return new_file
        except Exception as e:
            logger.warning(f"pytube download failed for {video_url}: {e}")
            return None

    async def summarize_via_audio(self, video_url: str, metadata: Dict = None) -> str:
        """Fallback: Extracts audio and uses Gemini Flash multimodal to summarize."""
        import yt_dlp
        
        audio_path = None
        
        # Method A: Try yt-dlp first
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'm4a',
            }],
            'outtmpl': tempfile.gettempdir() + '/%(id)s.%(ext)s',
            'quiet': True,
            'no_warnings': True,
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'extra_headers': {
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
                'Upgrade-Insecure-Requests': '1',
            }
        }
        
        try:
            video_id = self.get_video_id(video_url)
            logger.info(f"Downloading audio via yt-dlp: {video_id}")
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(video_url, download=True)
                audio_path = ydl.prepare_filename(info).replace('.unknown_video', '.m4a').replace('.webm', '.m4a')
            
            if audio_path and not os.path.exists(audio_path):
                audio_path = audio_path.rsplit('.', 1)[0] + '.m4a'
        except Exception as e:
            logger.warning(f"yt-dlp fallback failed for {video_url}: {e}")

        # Method B: Try pytube if yt-dlp failed
        if not audio_path or not os.path.exists(audio_path):
            audio_path = await self._download_audio_pytube(video_url)

        if not audio_path or not os.path.exists(audio_path):
            return "Error: All audio extraction methods failed (yt-dlp and pytube)."

        try:
            # Using Vertex AI for multimodal (audio)
            from vertexai.generative_models import GenerativeModel, Part
            model = GenerativeModel(settings.VERTEX_MODEL)
            
            with open(audio_path, "rb") as f:
                audio_data = f.read()
            
            audio_part = Part.from_data(data=audio_data, mime_type="audio/mp4")
            
            metadata_str = ""
            if metadata:
                metadata_str = f"Context from Video Metadata:\nTitle: {metadata.get('title', 'N/A')}\nDescription: {metadata.get('description', 'N/A')[:1000]}\n"

            prompt = f"""
            You are a senior financial market analyst producing a structured daily market briefing.
            I have provided the audio of a market news video.
            
            {metadata_str}
            
            Produce a comprehensive "Market Quick Take" using the following structure.
            Extract as much detail as possible from the audio. Only include sections where relevant information is discussed.
            
            **Market drivers and catalysts** (1-2 line summary per asset class: Equities, Volatility, Digital Assets, Fixed Income, Currencies, Commodities)
            
            **Macro headlines** (bullet points — each headline should be a detailed 2-3 sentence paragraph explaining the event, its context, and market implications)
            
            **Equities** (regional breakdown: US, Europe, Asia — include specific index levels, percentage moves, and notable stock movers with reasons)
            
            **Fixed Income** (treasury yields, bond market moves, rate expectations)
            
            **Currencies** (major FX pairs, key moves, central bank implications)
            
            **Commodities** (gold, oil, metals — levels and catalysts)
            
            **Macro calendar highlights** (upcoming data releases mentioned, with times if available)
            
            **Earnings** (notable companies reporting this week if mentioned)
            
            Be specific with numbers, percentages, and price levels. Write professionally like a bank research note.
            """
            
            response = model.generate_content([prompt, audio_part])
            
            # Cleanup
            if os.path.exists(audio_path):
                os.remove(audio_path)
                
            return response.text
            
        except Exception as e:
            logger.error(f"Error during audio processing for {video_url}: {e}")
            return f"Error: Audio extracted but summarization failed: {str(e)}"

    async def summarize_transcript(self, transcript: str, metadata: Dict = None) -> str:
        """Summarizes the transcript using Gemini Flash, enriched with metadata."""
        if not transcript and not (metadata and metadata.get("description")):
            return ""
        
        metadata_str = ""
        if metadata:
            metadata_str = f"Title: {metadata.get('title', 'N/A')}\nDescription: {metadata.get('description', 'N/A')[:1000]}\n"

        prompt = f"""
        You are a senior financial market analyst producing a structured daily market briefing.
        Below is information from a market news video.

        {metadata_str}
        
        Transcript (if available):
        {transcript[:30000]}
        
        Produce a comprehensive "Market Quick Take" using the following structure.
        Extract as much detail as possible from the transcript. Only include sections where relevant information is discussed.
        
        **Market drivers and catalysts** (1-2 line summary per asset class: Equities, Volatility, Digital Assets, Fixed Income, Currencies, Commodities)
        
        **Macro headlines** (bullet points — each headline should be a detailed 2-3 sentence paragraph explaining the event, its context, and market implications)
        
        **Equities** (regional breakdown: US, Europe, Asia — include specific index levels, percentage moves, and notable stock movers with reasons)
        
        **Fixed Income** (treasury yields, bond market moves, rate expectations)
        
        **Currencies** (major FX pairs, key moves, central bank implications)
        
        **Commodities** (gold, oil, metals — levels and catalysts)
        
        **Macro calendar highlights** (upcoming data releases mentioned, with times if available)
        
        **Earnings** (notable companies reporting this week if mentioned)
        
        Be specific with numbers, percentages, and price levels. Write professionally like a bank research note.
        """
        
        try:
            response = self.llm.invoke(prompt)
            return response
        except Exception as e:
            logger.error(f"Error summarizing transcript: {e}")
            return f"Error during summarization: {str(e)}"

    async def get_market_summary(self, video_urls: List[str]) -> List[Dict]:
        """Processes a list of YouTube URLs and returns summaries."""
        results = []
        for url in video_urls:
            video_id = self.get_video_id(url)
            
            # 1. Fetch metadata (Official API)
            metadata = await self.fetch_video_metadata(video_id)
            
            # 2. Fetch transcript
            transcript = await self.fetch_youtube_transcript(video_id)
            
            if transcript or (metadata and metadata.get("description")):
                summary = await self.summarize_transcript(transcript, metadata)
            else:
                # 3. Fallback: Audio extraction (now passing metadata for context)
                summary = await self.summarize_via_audio(url, metadata)
                
            results.append({
                "url": url,
                "video_id": video_id,
                "title": metadata.get("title", "Market Update"),
                "summary": summary
            })
        return results
