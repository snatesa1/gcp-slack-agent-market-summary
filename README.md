# 📈 GCP Slack Agent — Market Summary

### *A production-grade, serverless AI agent that delivers daily Bloomberg market briefings to Slack*

[![Google Cloud](https://img.shields.io/badge/Google%20Cloud-Cloud%20Run-4285F4?style=for-the-badge&logo=google-cloud&logoColor=white)](https://cloud.google.com/run)
[![Python](https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Gemini](https://img.shields.io/badge/Gemini-2.5%20Flash-8E75B2?style=for-the-badge&logo=google&logoColor=white)](https://cloud.google.com/vertex-ai)
[![Slack](https://img.shields.io/badge/Slack-Bot-4A154B?style=for-the-badge&logo=slack&logoColor=white)](https://api.slack.com/)

---

*Automatically discovers the latest Bloomberg Markets YouTube videos, extracts transcripts, summarizes them with Gemini AI, and delivers structured "Market Quick Takes" to your Slack channel — every day at 7:00 PM SGT.*

---

## 📑 Table of Contents

- [Overview](#-overview)
- [High-Level Architecture](#-high-level-architecture)
- [Request Flow Diagrams](#-request-flow-diagrams)
- [Project Structure](#-project-structure)
- [Core System Design Patterns](#-core-system-design-patterns)
- [Component Deep Dive](#-component-deep-dive)
- [Technology Stack](#-technology-stack)
- [Key Learnings](#-key-learnings)
- [Setup & Deployment Guide](#-setup--deployment-guide)
- [Shell Scripts Reference](#-shell-scripts-reference)
- [Environment Variables & Secrets](#-environment-variables--secrets)
- [API Endpoints](#-api-endpoints)
- [Sample Slack Output](#-sample-slack-output)
- [Troubleshooting](#-troubleshooting)
- [License](#-license)

---

## 🎯 Overview

This project is a **fully serverless, event-driven AI agent** running on Google Cloud that:

1. 🔍 **Discovers** the latest 1–2 videos from Bloomberg Markets YouTube channel using the YouTube Data API v3
2. 📝 **Extracts** video transcripts (with multi-strategy fallbacks: transcript API → yt-dlp → pytube)
3. 🧠 **Summarizes** content using Google's Gemini 2.5 Flash via Vertex AI, producing structured "Market Quick Takes"
4. 📤 **Delivers** rich, formatted summaries to a Slack channel via Bot Token (proactive push)

It supports both **automated daily delivery** (via Cloud Scheduler) and **on-demand** Slack slash commands (`/marketnews`).

---

## 🏗️ High-Level Architecture

```mermaid
graph TB
    subgraph "Trigger Layer"
        CS["⏰ Cloud Scheduler<br/><i>7:00 PM SGT Daily</i>"]
        SU["👤 Slack User<br/><i>/marketnews command</i>"]
    end

    subgraph "Google Cloud Platform"
        subgraph "Cloud Run (Serverless)"
            FA["🚀 FastAPI Server<br/><i>main.py</i>"]
            OR["🎼 Market Orchestrator<br/><i>orchestrator.py</i>"]
            RES["🔬 Market Researcher<br/><i>researcher.py</i>"]
            CFG["⚙️ Config (Pydantic)<br/><i>config.py</i>"]
        end

        SM["🔐 Secret Manager"]
        VA["🧠 Vertex AI<br/><i>Gemini 2.5 Flash</i>"]
    end

    subgraph "External APIs"
        YT["📹 YouTube Data API v3"]
        YTT["📜 YouTube Transcript API"]
        SL["💬 Slack API"]
    end

    CS -->|"POST /cron/market-news<br/>X-Cron-Secret header"| FA
    SU -->|"/marketnews slash command"| FA
    FA --> OR
    OR --> RES
    CFG -->|"Lazy-loaded secrets"| SM
    RES -->|"Discover videos"| YT
    RES -->|"Fetch transcripts"| YTT
    RES -->|"Summarize with LLM"| VA
    FA -->|"Post message"| SL

    style CS fill:#4285F4,stroke:#333,color:#fff
    style FA fill:#009688,stroke:#333,color:#fff
    style VA fill:#8E75B2,stroke:#333,color:#fff
    style SM fill:#F4B400,stroke:#333,color:#fff
    style SL fill:#4A154B,stroke:#333,color:#fff
    style YT fill:#FF0000,stroke:#333,color:#fff
```

---

## 🔄 Request Flow Diagrams

### Scheduled Flow (Cloud Scheduler → Slack)

```mermaid
sequenceDiagram
    participant CS as ⏰ Cloud Scheduler
    participant CR as 🚀 Cloud Run (FastAPI)
    participant OR as 🎼 Orchestrator
    participant RES as 🔬 Researcher
    participant YT as 📹 YouTube API
    participant AI as 🧠 Gemini Flash
    participant SL as 💬 Slack

    CS->>CR: POST /cron/market-news
    Note over CR: Verify X-Cron-Secret (HMAC)

    CR->>CR: Queue background task
    CR-->>CS: 200 OK (accepted)

    Note over CR: Background Task Begins

    CR->>OR: run_scheduled_analysis()
    OR->>RES: discover_latest_videos("@markets", 2)

    RES->>YT: channels.list(forHandle="markets")
    YT-->>RES: channelId

    RES->>YT: search.list(channelId, order=date)
    YT-->>RES: Latest 2 video URLs

    loop For each video
        OR->>RES: get_market_summary(url)

        RES->>YT: videos.list(id=videoId)
        YT-->>RES: Title + Description

        RES->>RES: fetch_youtube_transcript(videoId)
        alt Transcript Available
            RES->>AI: summarize_transcript(text)
            AI-->>RES: Structured summary
        else Transcript Blocked
            RES->>RES: Download audio (yt-dlp → pytube)
            RES->>AI: summarize_via_audio(audio_file)
            AI-->>RES: Multimodal summary
        end
    end

    OR->>OR: format_slack_message(results)
    CR->>SL: chat.postMessage(channel, message)
    SL-->>CR: ✅ Message posted
```

### Manual Flow (Slash Command → Slack)

```mermaid
sequenceDiagram
    participant U as 👤 User
    participant SL as 💬 Slack
    participant CR as 🚀 Cloud Run
    participant BG as 🔄 Background Task

    U->>SL: /marketnews
    SL->>CR: POST /slack/events (form data)

    Note over CR: Verify Slack Signature (HMAC-SHA256)

    CR-->>SL: 200 "Discovering & summarizing... ⏳"
    SL-->>U: Ephemeral message shown

    CR->>BG: run_manual_market_news(response_url)

    Note over BG: Same pipeline as scheduled flow

    BG->>SL: POST response_url (delayed response)
    SL-->>U: Full Market Quick Take displayed
```

---

## 📂 Project Structure

```
gcp-slack-agent-market-summary/
├── 📁 app/                          # Core application package
│   ├── __init__.py                  # Package initializer
│   ├── main.py                      # FastAPI entrypoint, routes, security
│   ├── config.py                    # Centralized config (Pydantic + Secret Manager)
│   ├── orchestrator.py              # Workflow coordination layer
│   └── researcher.py               # YouTube discovery, transcript, AI summarization
│
├── 🐳 Dockerfile                    # Production container (Python 3.11-slim + ffmpeg)
├── 📦 requirements.txt              # Python dependencies
├── 🍪 cookies.txt                   # YouTube auth cookies (Netscape format)
├── 🔧 convert_cookies.py            # JSON → Netscape cookie converter utility
├── 🔒 .env                          # Local secrets (git-ignored)
├── 🚫 .gitignore                    # Git exclusions
│
├── 🛠️ Shell Scripts (DevOps)
│   ├── init_gcp.sh                  # One-time GCP project setup & API enablement
│   ├── upload_secrets.sh            # Push .env secrets → GCP Secret Manager
│   ├── deploy_app.sh                # Build, deploy Cloud Run + setup Scheduler
│   └── destroy_app.sh               # Tear down all cloud resources
│
└── 📖 README.md                     
```

---

## 🧩 Core System Design Patterns

This project is a showcase of **production-grade design patterns** commonly used in cloud-native applications.

### 1. 🎼 Orchestrator Pattern

> **File:** `orchestrator.py`

The `MarketOrchestrator` acts as the **single coordination point** between the entrypoint (`main.py`) and the business logic (`researcher.py`). It **does not** contain any business logic itself — it merely **sequences and coordinates** sub-tasks.

```mermaid
graph LR
    A["main.py<br/><i>API Layer</i>"] --> B["orchestrator.py<br/><i>Coordination</i>"]
    B --> C["researcher.py<br/><i>Business Logic</i>"]

    style A fill:#009688,stroke:#333,color:#fff
    style B fill:#FF9800,stroke:#333,color:#fff
    style C fill:#2196F3,stroke:#333,color:#fff
```

**Why it matters:**
- **Separation of Concerns**: API handling ≠ business logic ≠ workflow coordination
- **Testability**: Orchestrator can be tested independently by mocking the researcher
- **Extensibility**: Adding new data sources (e.g., Reuters, CNBC) only requires adding to the researcher, not rewiring the API

```python
# orchestrator.py — Pure coordination, no business logic
class MarketOrchestrator:
    async def run_scheduled_analysis(self, channel_handle, max_videos):
        videos = await self.researcher.discover_latest_videos(channel_handle, max_videos)
        video_urls = [v["url"] for v in videos]
        results = await self.researcher.get_market_summary(video_urls)
        return results
```

---

### 2. 🔗 Chain of Responsibility / Multi-Strategy Fallback

> **File:** `researcher.py` — `get_market_summary()`, `fetch_youtube_transcript()`, `summarize_via_audio()`

The system uses a **cascading fallback chain** that gracefully degrades through multiple strategies to ensure maximum reliability:

```mermaid
graph TD
    A["🎯 Start: Process Video"] --> B{"Transcript API<br/>available?"}
    B -->|Yes| C["📜 Summarize Transcript<br/><i>Cheapest, fastest</i>"]
    B -->|No / Blocked| D{"yt-dlp audio<br/>download?"}
    D -->|Success| E["🔊 Gemini Multimodal<br/><i>Audio summarization</i>"]
    D -->|Failed| F{"pytube audio<br/>download?"}
    F -->|Success| E
    F -->|Failed| G["❌ All methods failed"]

    style C fill:#4CAF50,stroke:#333,color:#fff
    style E fill:#FF9800,stroke:#333,color:#fff
    style G fill:#F44336,stroke:#333,color:#fff
```

**Why it matters:**
- **Resilience**: YouTube frequently blocks transcript access from cloud IPs — this handles it
- **Cost optimization**: Transcript → text LLM (cheap) before falling back to audio → multimodal (expensive)
- **Zero human intervention**: The agent self-heals through fallback strategies

---

### 3. 🔐 Lazy-Loaded Singleton Configuration

> **File:** `config.py`

The `Settings` class implements a **lazy-loading pattern** with in-memory caching for secrets. Secrets are fetched from GCP Secret Manager **on first access only**, then cached for the lifetime of the process.

```mermaid
graph TD
    A["Code requests<br/>settings.SLACK_BOT_TOKEN"] --> B{"In _secrets<br/>cache?"}
    B -->|Yes| C["Return cached value"]
    B -->|No| D["Fetch from Secret Manager"]
    D --> E{"Found?"}
    E -->|Yes| F["Cache + Return"]
    E -->|No| G["Fallback to os.getenv()"]
    G --> F

    style C fill:#4CAF50,stroke:#333,color:#fff
    style F fill:#4CAF50,stroke:#333,color:#fff
```

**Why it matters:**
- **Cold start optimization**: Secrets not needed at startup aren't fetched, reducing Cloud Run cold start latency
- **Cost reduction**: Secret Manager API calls are minimized (one per secret per process lifetime)
- **Environment parity**: Falls back to `os.getenv()` for local development without Secret Manager

```python
# config.py — Lazy-loaded property with caching
@property
def SLACK_BOT_TOKEN(self) -> str:
    if "SLACK_BOT_TOKEN" not in self._secrets:
        self._secrets["SLACK_BOT_TOKEN"] = self._get_secret_manager_value("SLACK_BOT_TOKEN")
    return self._secrets["SLACK_BOT_TOKEN"]
```

---

### 4. ⚡ Async Background Task Pattern (3-Second Rule)

> **File:** `main.py`

Slack requires a response within **3 seconds** or the command appears to fail. This project uses FastAPI's `BackgroundTasks` to immediately acknowledge the request, then process asynchronously.

```mermaid
sequenceDiagram
    participant SL as Slack
    participant FA as FastAPI
    participant BG as Background Worker

    SL->>FA: /marketnews (POST)
    Note over FA: < 3 seconds!
    FA-->>SL: 200 "Summarizing... ⏳"
    FA->>BG: add_task(run_manual_market_news)
    Note over BG: 30-120 seconds
    BG->>SL: POST response_url (final result)
```

**Why it matters:**
- **UX compliance**: Slack's 3-second timeout is a hard constraint
- **Non-blocking**: The main event loop remains free to serve health checks and other requests
- **Error isolation**: Background task failures don't crash the main process

---

### 5. 🔒 Defense-in-Depth Security

> **File:** `main.py` — `verify_slack_signature()`, `verify_cron_secret()`

The API implements **two distinct authentication mechanisms** for its two entry points:

| Endpoint | Auth Method | Algorithm |
|----------|-------------|-----------|
| `/slack/events` | Slack Signature Verification | HMAC-SHA256 with signing secret + timestamp (replay protection) |
| `/cron/market-news` | Shared Secret Header | HMAC-safe comparison via `hmac.compare_digest()` |

```mermaid
graph TD
    A["Incoming Request"] --> B{"Endpoint?"}
    B -->|/slack/events| C["Verify Slack Signature"]
    B -->|/cron/market-news| D["Verify Cron Secret"]

    C --> C1["Check X-Slack-Request-Timestamp<br/><i>< 5 min (replay attack protection)</i>"]
    C1 --> C2["Compute HMAC-SHA256<br/><i>v0:timestamp:body</i>"]
    C2 --> C3["hmac.compare_digest()<br/><i>Timing-safe comparison</i>"]

    D --> D1["Extract X-Cron-Secret header"]
    D1 --> D2["hmac.compare_digest()<br/><i>Timing-safe comparison</i>"]

    C3 -->|Valid| E["✅ Process Request"]
    C3 -->|Invalid| F["❌ 401 Unauthorized"]
    D2 -->|Valid| E
    D2 -->|Invalid| F

    style E fill:#4CAF50,stroke:#333,color:#fff
    style F fill:#F44336,stroke:#333,color:#fff
```

**Why it matters:**
- **Replay attack prevention**: Timestamp validation ensures old requests can't be resent
- **Timing-safe comparison**: Prevents timing side-channel attacks on secret comparison
- **Zero-trust**: Both external triggers (Slack and Scheduler) are independently verified

---

### 6. 🔄 Proactive Message Delivery (Push Model)

Instead of the traditional request-response model, this agent **proactively pushes** messages to Slack using `chat.postMessage` — the same pattern used by professional trading desk bots.

```mermaid
graph LR
    subgraph "Traditional (Pull)"
        U1["User asks"] --> B1["Bot responds"]
    end

    subgraph "This Agent (Push)"
        T["Scheduler trigger"] --> A["Agent runs analysis"]
        A --> P["Agent pushes to channel"]
        P --> U2["Users see summary"]
    end

    style T fill:#4285F4,stroke:#333,color:#fff
    style P fill:#4A154B,stroke:#333,color:#fff
```

---

## 🔍 Component Deep Dive

### `main.py` — API Gateway & Security Layer

| Responsibility | Implementation |
|---|---|
| HTTP routing | FastAPI with `@app.get`, `@app.post` decorators |
| Slack signature verification | HMAC-SHA256 with replay protection (5-min window) |
| Cron authentication | Shared secret via `X-Cron-Secret` header |
| Background processing | FastAPI `BackgroundTasks` for async execution |
| Slack delivery | Direct `chat.postMessage` via Bot Token |
| Health checks | `/health` endpoint with environment detection |

### `config.py` — Centralized Configuration

| Responsibility | Implementation |
|---|---|
| Secret management | GCP Secret Manager with `os.getenv()` fallback |
| Lazy loading | Python `@property` with `_secrets` dict cache |
| Project ID resolution | Auto-detect via `google.auth.default()` → env var fallback |
| Validation | Pydantic `BaseSettings` for type safety |

### `orchestrator.py` — Workflow Coordinator

| Responsibility | Implementation |
|---|---|
| Task sequencing | Discovery → summarization → formatting pipeline |
| Message formatting | Structured "Market Quick Take" Slack messages |
| Dual trigger support | Unified method for both scheduled and manual flows |

### `researcher.py` — Intelligence Layer

| Responsibility | Implementation |
|---|---|
| Video discovery | YouTube Data API v3 (`channels.list` → `search.list`) |
| Metadata fetching | YouTube Data API v3 (`videos.list`) |
| Transcript extraction | `youtube_transcript_api` with cookie-based auth |
| Audio fallback | yt-dlp (primary) → pytube (secondary) |
| AI summarization | Vertex AI Gemini Flash (text + multimodal audio) |
| Structured prompting | Bank-research-note-style prompt engineering |

---

## 🛠️ Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Runtime** | Python 3.11-slim | Core language |
| **Framework** | FastAPI + Uvicorn | Async HTTP server |
| **AI/LLM** | Vertex AI (Gemini 2.5 Flash) | Text & multimodal summarization |
| **LLM SDK** | LangChain + `langchain-google-vertexai` | LLM abstraction layer |
| **YouTube** | YouTube Data API v3 | Video discovery & metadata |
| **Transcripts** | `youtube-transcript-api` | Caption extraction |
| **Audio** | yt-dlp + pytube + ffmpeg | Audio extraction fallback |
| **Slack** | Slack SDK + Bot Token | Message delivery & slash commands |
| **Secrets** | GCP Secret Manager | Secure credential storage |
| **Compute** | Cloud Run (serverless) | Containerized deployment |
| **Scheduling** | Cloud Scheduler | Daily cron trigger |
| **Container** | Docker | Reproducible builds |
| **Config** | Pydantic Settings | Type-safe configuration |

---

## 🧠 Key Learnings

### 1. Slack's 3-Second Timeout Is Non-Negotiable ⏱️

Slack enforces a strict 3-second deadline for slash command responses. Any heavy processing (LLM calls, API calls) **must** be offloaded to a background task. The initial response should be a lightweight acknowledgment:

```python
# ✅ Correct: Acknowledge immediately, process in background
background_tasks.add_task(run_manual_market_news, response_url)
return JSONResponse(content={"text": "Summarizing... ⏳"})
```

The `response_url` provided by Slack allows posting the final result as a **delayed response** up to 30 minutes later.

---

### 2. YouTube Blocks Cloud IPs Aggressively 🚫

YouTube's bot protection actively blocks transcript requests from Google Cloud, AWS, and Azure IP ranges. The solutions implemented:

- **Cookie-based authentication** using `cookies.txt` in Netscape format (extracted from a browser session)
- **Multi-strategy fallback**: If transcripts are blocked, fall back to audio download + Gemini multimodal processing
- **Quota awareness**: YouTube Data API has a daily quota of 10,000 units; this agent uses ~200 units per run

---

### 3. Secret Manager Over Environment Variables 🔐

Storing secrets as Cloud Run environment variables is convenient but insecure (visible in GCP Console, audit logs, etc.). GCP Secret Manager provides:

- **Versioned secrets** with automatic rotation support
- **IAM-based access control** (least privilege)
- **Audit logging** for compliance
- **Lazy loading** avoids unnecessary API calls during cold starts

---

### 4. Prompt Engineering for Structured Output 📝

The summarization prompt is designed like a **bank research note template**, ensuring consistent, actionable output across all runs:

```
Produce a comprehensive "Market Quick Take" using the following structure:
- Market drivers and catalysts (per asset class)
- Macro headlines (detailed 2-3 sentence paragraphs)
- Equities (regional: US, Europe, Asia — with specific levels)
- Fixed Income (yields, rate expectations)
- Currencies (major FX pairs)
- Commodities (gold, oil, metals)
- Macro calendar highlights
- Earnings
```

This **constrained prompting** technique ensures:
- Deterministic output structure
- Comprehensive coverage (no asset class missed)
- Professional tone consistency

---

### 5. Timing-Safe String Comparison Prevents Side-Channel Attacks 🔒

Using `==` for secret comparison leaks information via timing differences. `hmac.compare_digest()` compares in constant time:

```python
# ❌ VULNERABLE to timing attacks
return incoming_secret == expected_secret

# ✅ SAFE — constant-time comparison
return hmac.compare_digest(incoming_secret, expected_secret)
```

---

### 6. Cloud Run Is Not "Always-On" — Design Accordingly ☁️

Cloud Run containers can be **cold-started** at any time. Key implications:
- **No persistent state**: Every invocation may be a fresh container
- **Lazy initialization**: Don't load all secrets at startup — load on first use
- **Idempotent operations**: Scheduler may retry; your handler must be safe to re-execute
- **Health checks**: Cloud Run probes `/health` to verify container readiness

---

## 🚀 Setup & Deployment Guide

### Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) (`gcloud` CLI)
- [Docker](https://docs.docker.com/get-docker/)
- A [Slack App](https://api.slack.com/apps) with:
  - **Bot Token** (`xoxb-...`) with `chat:write` scope
  - **Signing Secret** (from App Credentials)
  - A configured **Slash Command** pointing to `<Cloud Run URL>/slack/events`
- [YouTube Data API Key](https://console.cloud.google.com/apis/credentials) (GCP Console)

### Step-by-Step

```bash
# 1. Clone the repository
git clone https://github.com/snatesa1/gcp-slack-agent-market-summary.git
cd gcp-slack-agent-market-summary

# 2. Create .env file with your secrets
cat > .env << 'EOF'
GCP_PROJECT_ID=your-gcp-project-id
SLACK_BOT_TOKEN=xoxb-your-slack-bot-token
SLACK_SIGNING_SECRET=your-signing-secret
SLACK_CHANNEL_ID=C0XXXXXXXXX
YOUTUBE_API_KEY=AIzaSy...your-api-key
CRON_SECRET=your-random-cron-secret
VERTEX_MODEL=gemini-2.5-flash
VERTEX=your-service-account@project.iam.gserviceaccount.com
EOF

# 3. Initialize GCP project (enables APIs)
bash init_gcp.sh

# 4. Upload secrets to Secret Manager
bash upload_secrets.sh

# 5. Deploy to Cloud Run + configure Cloud Scheduler
bash deploy_app.sh
```

---

## 📜 Shell Scripts Reference

| Script | Purpose | When to Use |
|--------|---------|-------------|
| `init_gcp.sh` | Authenticates, sets project, enables 9 GCP APIs | **Once** per project setup |
| `upload_secrets.sh` | Reads `.env` and pushes secrets to GCP Secret Manager | When secrets change |
| `deploy_app.sh` | Builds image, deploys to Cloud Run, creates Cloud Scheduler job | Every deployment |
| `destroy_app.sh` | Deletes Cloud Run service and Scheduler job | Teardown / cleanup |
| `convert_cookies.py` | Converts browser-exported JSON cookies to Netscape format | When refreshing YouTube cookies |

### Deployment Pipeline Flow

```mermaid
graph LR
    A["🔧 init_gcp.sh<br/><i>One-time setup</i>"] --> B["🔐 upload_secrets.sh<br/><i>Push secrets</i>"]
    B --> C["🚀 deploy_app.sh<br/><i>Build + Deploy</i>"]
    C --> D["✅ Live on Cloud Run<br/><i>+ Scheduler active</i>"]
    D -.->|"Teardown"| E["🗑️ destroy_app.sh"]

    style A fill:#4285F4,stroke:#333,color:#fff
    style B fill:#F4B400,stroke:#333,color:#000
    style C fill:#0F9D58,stroke:#333,color:#fff
    style D fill:#4CAF50,stroke:#333,color:#fff
    style E fill:#F44336,stroke:#333,color:#fff
```

---

## 🔑 Environment Variables & Secrets

| Variable | Location | Description |
|----------|----------|-------------|
| `GCP_PROJECT_ID` | `.env` | Google Cloud project ID |
| `SLACK_BOT_TOKEN` | Secret Manager | Slack Bot OAuth Token (`xoxb-...`) |
| `SLACK_SIGNING_SECRET` | Secret Manager | Slack app signing secret for request verification |
| `SLACK_CHANNEL_ID` | Secret Manager | Target Slack channel for proactive messages |
| `YOUTUBE_API_KEY` | Secret Manager | YouTube Data API v3 key |
| `CRON_SECRET` | Secret Manager | Shared secret for Cloud Scheduler authentication |
| `VERTEX_MODEL` | Env var | Gemini model name (default: `gemini-2.5-flash`) |
| `VERTEX` | `.env` | Service account email for Cloud Run |

---

## 📡 API Endpoints

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| `GET` | `/health` | None | Health check — returns environment status |
| `POST` | `/cron/market-news` | `X-Cron-Secret` header | Triggered by Cloud Scheduler for daily runs |
| `POST` | `/slack/events` | Slack signature (HMAC-SHA256) | Receives `/marketnews` slash command |

---

## 📬 Sample Slack Output

```
📅 Market Quick Take — 2026-02-21

📹 Source 1: "Bloomberg Open: Feb 21, 2026"
🔗 https://www.youtube.com/watch?v=...

**Market drivers and catalysts**
• Equities: S&P 500 hit fresh all-time highs...
• Fixed Income: 10Y UST yield fell 3bps to 4.22%...
• Currencies: DXY weakened 0.3% to 103.42...
• Commodities: Gold surged to $2,180/oz...

**Macro headlines**
• Fed Chair Powell signaled patience on rate cuts...
• EU PMI data surprised to the upside at 51.2...

───────────────────────────

🤖 Automated GCP Market Summary Agent v2.0
```

---

## 🔧 Troubleshooting

| Issue | Cause | Fix |
|-------|-------|-----|
| `YouTube API Key blocked or restricted` | API key restrictions in GCP Console | Go to GCP Console → API & Services → Credentials → ensure YouTube Data API v3 is enabled |
| `Transcript fetch failed` | YouTube blocks cloud IPs | Refresh `cookies.txt` from a browser session using `convert_cookies.py` |
| `Slack command shows timeout` | Response took > 3 seconds | Processing is in background; result will appear via `response_url` |
| `Secret not found in Secret Manager` | Secret not uploaded | Run `bash upload_secrets.sh` |
| `Model not found` error | Model deprecated or wrong region | Update `VERTEX_MODEL` in `.env` (currently `gemini-2.5-flash`) |
| Windows line ending issues in scripts | `.env` has `\r\n` | Scripts handle this with `tr -d '\r'` |

---

## 📄 License

This project is for educational and personal use. Bloomberg Markets content is property of Bloomberg LP.

---

<div align="center">

*Built with ❤️ using Google Cloud, Gemini AI, and FastAPI*

**⭐ Star this repo if you found it useful!**

</div>
