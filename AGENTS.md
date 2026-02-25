# AGENTS.md

## Cursor Cloud specific instructions

### Overview

ClipMaker is a YouTube-to-viral-clips pipeline with a **Python FastAPI backend** and a **React/Vite/TypeScript frontend**. See `README.md` for full documentation including config variables and usage flow.

### Running services (development)

| Service | Command | Port | Notes |
|---|---|---|---|
| Backend | `source .venv/bin/activate && uvicorn app.main:app --reload --port 8000` | 8000 | Run from repo root. API docs at `/docs`. |
| Frontend | `npm run dev` (from `frontend/`) | 5173 | Vite proxies `/api`, `/jobs`, `/static` to backend. |

Both must run simultaneously for the full dev experience.

### Key gotchas

- The VM needs `python3.12-venv` installed (`sudo apt-get install -y python3.12-venv`) before creating the virtualenv. This is a one-time system dep.
- The `.env` file is gitignored. At minimum set `TIKTOK_PUBLISH_MODE=mock` for local dev. Without `OPENAI_API_KEY`, transcription will fail but moment selection falls back to heuristic.
- If `YTDLP_COOKIES_FILE` is set (via secrets) but the file doesn't exist locally, YouTube downloads will fail immediately. Clear or unset it for basic dev testing.
- The backend stores job state in memory; restarting the server loses active job tracking.
- `frontend/dist` must exist for the backend's static file mount to work without errors. Run `npm run build` in `frontend/` at least once, or the backend SPA fallback uses `static/index.html`.

### Lint / Type checks

- **Frontend TypeScript**: `cd frontend && npx tsc -b --noEmit`
- **Frontend build**: `cd frontend && npm run build` (runs `tsc -b && vite build`)
- No Python linter or formatter is configured in this repo.

### Postiz stack (optional)

The Postiz Docker Compose stack (9 containers) is only needed when `TIKTOK_PUBLISH_MODE=postiz`. For development, use `mock` mode. See `README.md` § "Postiz self-hosted local" for Docker setup if needed.
