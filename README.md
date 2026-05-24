<div align="center">

<img src="https://img.shields.io/badge/NeuroFlux-Autonomous%20Content%20Engine-6366f1?style=for-the-badge&logo=data:image/svg+xml;base64,..." alt="NeuroFlux">

# NeuroFlux 🧠⚡

**Fully autonomous AI-powered short-form video pipeline.**  
Trend analysis → Script generation → Voiceover → Video rendering → Instagram publishing. No human in the loop.

[![Python](https://img.shields.io/badge/Python-3.12-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?style=flat-square&logo=docker&logoColor=white)](https://www.docker.com/)
[![Groq](https://img.shields.io/badge/AI-Groq%20%7C%20Llama--3.3--70B-f97316?style=flat-square)](https://console.groq.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-22c55e?style=flat-square)](LICENSE)

</div>

---

## 🎯 What It Does

NeuroFlux runs as a background daemon that continuously:

1. **Generates dynamic topics** — Groq-powered LLM picks viral content themes automatically
2. **Writes full narratives** — Hook, body, CTA, voiceover script, hashtags, caption
3. **Synthesises voiceover** — Microsoft Edge TTS renders studio-quality MP3
4. **Fetches B-roll footage** — Pexels API, auto-selecting best 9:16 portrait clips
5. **Renders the Reel** — FFmpeg stitches clips + audio into a polished vertical video
6. **Publishes to Instagram** — `instagrapi` posts the Reel with caption + hashtags

The scheduler re-runs the pipeline on a configurable interval (default: every hour). Each stage is **idempotent** — a crash at any step resumes from the last checkpoint, not from scratch.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                   orchestrator.py                   │  ← APScheduler daemon
│         State machine (4 pipeline phases)           │
└────┬────────────┬──────────────┬────────────┬───────┘
     │            │              │            │
 ai_engine   media_fetcher  video_renderer  publisher
 (Groq LLM)  (Pexels API)   (FFmpeg)      (Instagram)
     │            │              │            │
     └────────────┴──────────────┴────────────┘
                         │
                      db.py  ←  SQLite (aiosqlite + SQLAlchemy 2)
```

### Key Design Principles

| Principle | Implementation |
|---|---|
| **Fault-tolerance** | Each pipeline phase is persisted to DB; crashed runs resume mid-flight |
| **Back-pressure** | `asyncio.Semaphore` caps concurrent Pexels downloads |
| **Retry logic** | `tenacity` exponential back-off on all external API calls |
| **Structured logging** | `structlog` JSON logs, Docker-friendly |
| **Non-root container** | Dedicated `appuser` in Dockerfile |

---

## 📁 Project Structure

```
NeuroFlux/
├── orchestrator.py       # Main daemon + APScheduler
├── ai_engine.py          # Groq LLM: topic + narrative + TTS
├── media_fetcher.py      # Pexels video search + download
├── video_renderer.py     # FFmpeg composition pipeline
├── publisher.py          # Instagram Reels upload
├── db.py                 # SQLAlchemy 2 async models + migrations
├── config.py             # Pydantic-settings environment config
├── logger.py             # Structlog configuration
├── requirements.txt      # Pinned Python dependencies
├── Dockerfile            # Production multi-stage image
├── docker-compose.yml    # One-command local stack
├── .env.example          # ← copy to .env and fill in
├── assets/
│   ├── raw/              # Downloaded B-roll + generated audio
│   └── rendered/         # Final composed Reels
└── data/
    └── neuroflux.db      # SQLite state database (git-ignored)
```

---

## 🚀 Quick Start

### Prerequisites

| Tool | Version |
|------|---------|
| Docker + Docker Compose | ≥ 24 |
| FFmpeg (for local runs) | ≥ 6 |
| Python | ≥ 3.12 |

### 1. Clone

```bash
git clone https://github.com/<your-username>/NeuroFlux.git
cd NeuroFlux
```

### 2. Configure secrets

```bash
cp .env.example .env
# Open .env and fill in your API keys (see table below)
```

| Variable | Where to get it | Required |
|---|---|---|
| `GROQ_API_KEY` | [console.groq.com](https://console.groq.com/) — free tier | ✅ |
| `PEXELS_API_KEY` | [pexels.com/api](https://www.pexels.com/api/) — free tier | ✅ |
| `INSTAGRAM_USERNAME` | Your Instagram account | ✅ |
| `INSTAGRAM_PASSWORD` | Your Instagram account | ✅ |
| `INSTAGRAM_PROXY` | Residential proxy (e.g. iProyal) — only needed on cloud VPS | ⚠️ |

### 3a. Run with Docker (recommended)

```bash
docker compose up --build
```

> The container will start, initialise the SQLite database, and immediately run the first pipeline cycle.

### 3b. Run locally

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
python -m orchestrator
```

---

## ⚙️ Configuration Reference

All settings live in `.env` (loaded via `pydantic-settings`).

```dotenv
# How often the pipeline runs (seconds). Default: 3600 = every hour
SCHEDULE_INTERVAL_SECONDS=3600

# Number of Pexels clips to download concurrently
MAX_CONCURRENT_FETCHES=5

# AI model — any Groq-hosted model works
GROQ_MODEL=llama-3.3-70b-versatile

# Log verbosity: DEBUG | INFO | WARNING | ERROR
LOG_LEVEL=INFO
```

---

## 🔄 Pipeline State Machine

```
PENDING ──▶ AUDIO_GENERATED ──▶ MEDIA_FETCHED ──▶ RENDERED ──▶ PUBLISHED
   │               │                   │               │
   └───────────────┴───────────────────┴───────────────┘
           (any failure → stays in current state, retried next run)
```

Each `ContentItem` row in the database tracks exactly which phase completed. Restarting the daemon never re-does expensive work already finished.

---

## 🐳 Docker Details

```yaml
# docker-compose.yml highlights
restart: unless-stopped          # auto-restarts on crash
env_file: .env                   # secrets injected at runtime, never baked in
volumes:
  - ./assets:/app/assets         # rendered videos persist on host
  - ./data:/app/data             # SQLite DB persists on host
logging:
  driver: json-file
  options: { max-size: "50m", max-file: "3" }
```

View live logs:
```bash
docker compose logs -f
```

Stop the daemon:
```bash
docker compose down
```

---

## 🧪 Development

```bash
# Install dev dependencies
pip install -r requirements.txt

# Run a single pipeline cycle (no scheduler)
python -c "import asyncio; from orchestrator import Orchestrator; o=Orchestrator(); asyncio.run(o.run_pipeline())"

# Check structured logs
python -m orchestrator 2>&1 | python -m json.tool
```

---

## 🛡️ Security Notes

- **Never commit `.env`** — it is listed in `.gitignore`
- The Docker container runs as a **non-root user** (`appuser`)
- Use a **residential proxy** (`INSTAGRAM_PROXY`) when running from a cloud VPS to avoid Instagram IP bans
- Rotate your Pexels and Groq API keys periodically
- See [SECURITY.md](SECURITY.md) for responsible disclosure

---

## 🤝 Contributing

Pull requests are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

---

## 📄 License

MIT — see [LICENSE](LICENSE).

---

<div align="center">
Built with ⚡ by NeuroFlux contributors
</div>
