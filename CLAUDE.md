# Blipr — YouTube to TikTok Pipeline

## What This Is
Converts a YouTube URL into vertical (9:16) short clips ready for TikTok. Runs the full pipeline locally: download → transcribe → AI clip selection → ffmpeg render → subtitles → publish via Postiz.

## Architecture

```
app/
  main.py             — FastAPI app, all routes (no separate routers dir)
  config.py           — Pydantic Settings; reads .env; use get_settings() everywhere
  models.py           — Pydantic request/response models
  services/
    pipeline.py       — orchestrates the full job flow
    downloader.py     — yt-dlp wrapper
    transcriber.py    — OpenAI Whisper (chunked, with overlap)
    analyzer.py       — GPT-4o-mini clip selection + heuristic fallback
    clipper.py        — ffmpeg clip extraction + blur background
    subtitles.py      — .srt generation + ffmpeg burn-in (libass)
    postiz.py         — Postiz API: upload video, create scheduled post
    r2.py             — Cloudflare R2 upload/delete (boto3, S3-compat)
    state.py          — in-memory job state (lost on restart)
    preview.py        — subtitle preview rendering

frontend/src/
  App.tsx             — routing (activePage state), caption generation, publish handlers
  components/
    PipelinePanel.tsx — job progress + clip review
    ClipReviewTable.tsx — approve/reject clips, publish form per clip
    ChannelsPage.tsx  — TikTok connection status via /api/publishing/tiktok/integrations
    OverviewPage.tsx, HistoryPage.tsx, Sidebar.tsx, ...

jobs/<job_id>/        — per-job files on disk (source.mp4, transcript.json, clip_g01_01.mp4, ...)
postiz/               — Docker Compose for local Postiz dev instance
```

## Dev Setup
```bash
# Backend
source .venv/bin/activate
uvicorn app.main:app --reload --port 8000

# Frontend
cd frontend && npm run dev  # http://127.0.0.1:5173

# Build + serve from FastAPI
cd frontend && npm run build
uvicorn app.main:app --reload  # serves frontend/dist
```

## VPS (Postiz only — Blipr runs locally)
- Host alias: `hetzner-openclaw` → `178.156.223.0`
- Postiz stack: `/root/postiz/docker-compose.yml`
- Restart Postiz: `ssh hetzner-openclaw "cd /root/postiz && docker compose restart postiz"`
- Full restart: `ssh hetzner-openclaw "cd /root/postiz && docker compose down && docker compose up -d"`
- Postiz logs: `ssh hetzner-openclaw "docker logs postiz --tail 50"`
- Postiz UI: `https://postiz.blipr.co`

## Critical Constraints
- Postiz `STORAGE_PROVIDER=local` — videos must be served from `postiz.blipr.co/uploads/...` (not R2 CDN) because TikTok verifies domain ownership
- TikTok sandbox app (`sbawhib3paxvaxudx7`) is **unaudited** — posts are `SELF_ONLY` (private); user must manually make public from TikTok app
- In-memory job state: restarting the backend loses all active job tracking
- `get_settings()` reloads `.env` on each call — no restart needed for config changes
- clip_id format: `{job_id}:{clip_index}` (colon-separated, split with `split(":", 1)`)

## Key Env Vars
- `TIKTOK_PUBLISH_MODE`: `postiz` (real) or `mock` (skip posting)
- `POSTIZ_API_URL` or `POSTIZ_BASE_URL`: Postiz base URL
- `TIKTOK_INTEGRATION_ID` or `POSTIZ_TIKTOK_INTEGRATION_ID`: TikTok integration ID
- `OPENAI_API_KEY`: used for Whisper transcription + GPT-4o-mini analysis + caption generation

## Key Docs (load on demand)
- @docs/tiktok-flow.md — TikTok posting architecture and known errors
- @docs/r2-setup.md — Cloudflare R2 configuration (currently unused by postiz.py)
