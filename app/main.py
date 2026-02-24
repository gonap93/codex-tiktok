import asyncio
import json
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from app.config import get_settings
from app.models import (
    ClipReviewRequest,
    JobCreateRequest,
    JobCreateResponse,
    PublishApprovedResponse,
    RegenerateRequest,
    RestartRequest,
    SubtitlePreviewRequest,
    SubtitlePreviewResponse,
)
from app.services.pipeline import regenerate_job_from_cache, run_job
from app.services.preview import render_subtitle_preview_image
from app.services.state import (
    add_log,
    create_job,
    get_job,
    list_jobs,
    set_progress,
    set_clip_publish_status,
    set_clip_review_status,
    subscribe,
    unsubscribe,
    update_job_requests,
)
from app.services.tiktok_publisher import PostizPublisherError, list_tiktok_integrations, publish_to_tiktok

settings = get_settings()
_job_tasks: dict[str, asyncio.Task] = {}

app = FastAPI(
    title="ClipMaker API",
    description="YouTube -> Clips virales automatizado",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/jobs", StaticFiles(directory=str(settings.jobs_dir)), name="jobs")
app.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
app.mount(
    "/assets",
    StaticFiles(directory=str(settings.frontend_dist_dir / "assets"), check_dir=False),
    name="frontend-assets",
)


def _frontend_index_path() -> Path:
    dist_index = settings.frontend_dist_dir / "index.html"
    if dist_index.exists():
        return dist_index
    return settings.static_dir / "index.html"


def _is_reserved_path(path: str) -> bool:
    return path.startswith("api/") or path.startswith("jobs/") or path.startswith("static/") or path.startswith("assets/")


def _safe_file_candidate(root: Path, relative_path: str) -> Path | None:
    if not relative_path:
        return None
    candidate = (root / relative_path).resolve()
    root_resolved = root.resolve()
    if not candidate.is_relative_to(root_resolved):
        return None
    if candidate.is_file():
        return candidate
    return None


def _normalize_output_size(width: int, height: int) -> tuple[int, int]:
    # libx264 requires even dimensions.
    normalized_width = max(320, min(3840, int(width)))
    normalized_height = max(320, min(3840, int(height)))
    if normalized_width % 2 != 0:
        normalized_width -= 1
    if normalized_height % 2 != 0:
        normalized_height -= 1
    if normalized_width < 320 or normalized_height < 320:
        raise HTTPException(status_code=400, detail="Output width/height invalidos.")
    return normalized_width, normalized_height


def _register_job_task(job_id: str, task: asyncio.Task) -> None:
    prev = _job_tasks.get(job_id)
    if prev is not None and not prev.done() and prev is not task:
        prev.cancel()
    _job_tasks[job_id] = task

    def _cleanup(done_task: asyncio.Task) -> None:
        if _job_tasks.get(job_id) is done_task:
            _job_tasks.pop(job_id, None)

    task.add_done_callback(_cleanup)


async def _cancel_job_task(job_id: str) -> None:
    task = _job_tasks.get(job_id)
    if task is None or task.done():
        return
    task.cancel()
    try:
        await asyncio.wait_for(task, timeout=2.0)
    except (asyncio.TimeoutError, asyncio.CancelledError):
        pass
    except Exception:
        pass


@app.get("/")
async def index() -> FileResponse:
    return FileResponse(_frontend_index_path())


@app.post("/api/jobs", response_model=JobCreateResponse)
async def start_job(payload: JobCreateRequest) -> JobCreateResponse:
    youtube_url = payload.youtube_url.strip()
    if "youtube.com" not in youtube_url and "youtu.be" not in youtube_url:
        raise HTTPException(status_code=400, detail="Debe ser un link valido de YouTube.")
    requested_clips = payload.clips_count or settings.clips_count
    requested_clips = max(1, min(requested_clips, settings.max_clips_per_job))
    requested_min = payload.min_clip_seconds or settings.min_clip_seconds
    requested_max = payload.max_clip_seconds or settings.max_clip_seconds
    requested_font = (payload.subtitle_font_name or settings.subtitle_font_name).strip() or settings.subtitle_font_name
    requested_margin_h = payload.subtitle_margin_horizontal or settings.subtitle_margin_horizontal
    requested_margin_v = payload.subtitle_margin_vertical or settings.subtitle_margin_vertical
    requested_output_w = payload.output_width or settings.output_width
    requested_output_h = payload.output_height or settings.output_height
    requested_output_w, requested_output_h = _normalize_output_size(requested_output_w, requested_output_h)
    if requested_min > requested_max:
        requested_max = requested_min

    requested_genre = (payload.content_genre or "").strip()
    requested_moments_instruction = (payload.specific_moments_instruction or "").strip()
    requested_ai_choose = payload.ai_choose_count
    requested_subtitles_enabled = payload.subtitles_enabled
    requested_subtitle_preset = (payload.subtitle_preset or "").strip()
    requested_video_language = (payload.video_language or "es").strip() or "es"
    requested_subtitle_font_size = payload.subtitle_font_size or 36

    if requested_ai_choose:
        requested_clips = 0  # signal to pipeline to auto-choose

    job = await create_job(
        youtube_url,
        requested_clips,
        requested_min,
        requested_max,
        requested_font,
        requested_margin_h,
        requested_margin_v,
        requested_output_w,
        requested_output_h,
        requested_content_genre=requested_genre,
        requested_specific_moments_instruction=requested_moments_instruction,
        requested_ai_choose_count=requested_ai_choose,
        requested_subtitles_enabled=requested_subtitles_enabled,
        requested_subtitle_preset=requested_subtitle_preset,
        requested_video_language=requested_video_language,
        requested_subtitle_font_size=requested_subtitle_font_size,
    )
    task = asyncio.create_task(run_job(job.job_id, youtube_url))
    _register_job_task(job.job_id, task)
    return JobCreateResponse(job_id=job.job_id)


@app.get("/api/jobs")
async def list_all_jobs() -> list[dict]:
    jobs = await list_jobs()
    return [j.model_dump(mode="json") for j in jobs]


@app.get("/api/jobs/{job_id}")
async def job_status(job_id: str) -> dict:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    return job.model_dump(mode="json")


@app.get("/api/jobs/{job_id}/stream")
async def stream_job(job_id: str) -> StreamingResponse:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    queue = await subscribe(job_id)

    async def event_generator():
        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=15)
                    yield f"data: {json.dumps(event, ensure_ascii=False)}\n\n"
                    # Close the stream once the job reaches a terminal state
                    status = event.get("status") if isinstance(event, dict) else None
                    if status in ("completed", "failed"):
                        break
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            await unsubscribe(job_id, queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.patch("/api/jobs/{job_id}/clips/{clip_index}")
async def review_clip(job_id: str, clip_index: int, payload: ClipReviewRequest) -> dict:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    if not any(clip.index == clip_index for clip in job.clips):
        raise HTTPException(status_code=404, detail="Clip no encontrado.")

    reason = (payload.rejection_reason or "").strip()
    await set_clip_review_status(job_id, clip_index, payload.approved, reason if payload.approved is False else None)
    updated = await get_job(job_id)
    assert updated is not None
    return updated.model_dump(mode="json")


@app.post("/api/jobs/{job_id}/regenerate")
async def regenerate_job(job_id: str, payload: RegenerateRequest) -> dict:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    if job.status == "running":
        raise HTTPException(status_code=400, detail="El job esta ejecutandose. Espera a que termine.")

    requested_clips = payload.clips_count or job.requested_clips_count
    requested_clips = max(1, min(requested_clips, settings.max_clips_per_job))
    requested_min = payload.min_clip_seconds or job.requested_min_clip_seconds
    requested_max = payload.max_clip_seconds or job.requested_max_clip_seconds
    requested_font = (payload.subtitle_font_name or job.requested_subtitle_font_name).strip() or job.requested_subtitle_font_name
    requested_margin_h = payload.subtitle_margin_horizontal or job.requested_subtitle_margin_horizontal
    requested_margin_v = payload.subtitle_margin_vertical or job.requested_subtitle_margin_vertical
    requested_output_w = payload.output_width or job.requested_output_width
    requested_output_h = payload.output_height or job.requested_output_height
    requested_output_w, requested_output_h = _normalize_output_size(requested_output_w, requested_output_h)
    if requested_min > requested_max:
        raise HTTPException(status_code=400, detail="La duracion minima no puede ser mayor que la maxima.")

    regen_genre = (payload.content_genre or "").strip() or None
    regen_moments_instruction = (payload.specific_moments_instruction or "").strip() or None
    regen_ai_choose = payload.ai_choose_count
    regen_video_language = (payload.video_language or "").strip() or None
    regen_subtitle_font_size = payload.subtitle_font_size

    await update_job_requests(
        job_id,
        requested_clips_count=requested_clips,
        requested_min_clip_seconds=requested_min,
        requested_max_clip_seconds=requested_max,
        requested_subtitle_font_name=requested_font,
        requested_subtitle_margin_horizontal=requested_margin_h,
        requested_subtitle_margin_vertical=requested_margin_v,
        requested_output_width=requested_output_w,
        requested_output_height=requested_output_h,
        requested_content_genre=regen_genre,
        requested_specific_moments_instruction=regen_moments_instruction,
        requested_ai_choose_count=regen_ai_choose,
        requested_video_language=regen_video_language,
        requested_subtitle_font_size=regen_subtitle_font_size,
    )
    await add_log(
        job_id,
        "Regeneracion solicitada reutilizando transcripcion/analisis cacheados.",
    )
    task = asyncio.create_task(regenerate_job_from_cache(job_id))
    _register_job_task(job_id, task)
    updated = await get_job(job_id)
    assert updated is not None
    return updated.model_dump(mode="json")


@app.post("/api/jobs/{job_id}/restart")
async def restart_job(job_id: str, payload: RestartRequest) -> dict:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")

    requested_clips = payload.clips_count or job.requested_clips_count
    requested_clips = max(1, min(requested_clips, settings.max_clips_per_job))
    requested_min = payload.min_clip_seconds or job.requested_min_clip_seconds
    requested_max = payload.max_clip_seconds or job.requested_max_clip_seconds
    requested_font = (payload.subtitle_font_name or job.requested_subtitle_font_name).strip() or job.requested_subtitle_font_name
    requested_margin_h = payload.subtitle_margin_horizontal or job.requested_subtitle_margin_horizontal
    requested_margin_v = payload.subtitle_margin_vertical or job.requested_subtitle_margin_vertical
    requested_output_w = payload.output_width or job.requested_output_width
    requested_output_h = payload.output_height or job.requested_output_height
    requested_output_w, requested_output_h = _normalize_output_size(requested_output_w, requested_output_h)
    if requested_min > requested_max:
        raise HTTPException(status_code=400, detail="La duracion minima no puede ser mayor que la maxima.")

    restart_genre = (payload.content_genre or "").strip() or None
    restart_moments_instruction = (payload.specific_moments_instruction or "").strip() or None
    restart_ai_choose = payload.ai_choose_count
    restart_video_language = (payload.video_language or "").strip() or None
    restart_subtitle_font_size = payload.subtitle_font_size

    await update_job_requests(
        job_id,
        requested_clips_count=requested_clips,
        requested_min_clip_seconds=requested_min,
        requested_max_clip_seconds=requested_max,
        requested_subtitle_font_name=requested_font,
        requested_subtitle_margin_horizontal=requested_margin_h,
        requested_subtitle_margin_vertical=requested_margin_v,
        requested_output_width=requested_output_w,
        requested_output_height=requested_output_h,
        requested_content_genre=restart_genre,
        requested_specific_moments_instruction=restart_moments_instruction,
        requested_ai_choose_count=restart_ai_choose,
        requested_video_language=restart_video_language,
        requested_subtitle_font_size=restart_subtitle_font_size,
    )

    await _cancel_job_task(job_id)
    await set_progress(
        job_id,
        status="queued",
        progress=0,
        current_step="Reiniciando proceso",
        error="",
    )
    await add_log(job_id, "Reinicio manual solicitado por el usuario.")

    job_dir = settings.jobs_dir / job_id
    has_transcript = (job_dir / "transcript.json").exists()
    has_source = any(job_dir.glob("source.*"))
    use_cache = payload.use_cache and has_transcript and has_source

    if payload.use_cache and not use_cache:
        await add_log(job_id, "Cache incompleto; se reinicia proceso completo.")

    task = asyncio.create_task(regenerate_job_from_cache(job_id) if use_cache else run_job(job_id, job.youtube_url))
    _register_job_task(job_id, task)
    updated = await get_job(job_id)
    assert updated is not None
    return updated.model_dump(mode="json")


@app.post("/api/jobs/{job_id}/publish-approved", response_model=PublishApprovedResponse)
async def publish_approved(job_id: str) -> PublishApprovedResponse:
    job = await get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job no encontrado.")
    if job.status != "completed":
        raise HTTPException(status_code=400, detail="El job aun no termino de generar clips.")

    approved = [clip for clip in job.clips if clip.review_status == "approved"]
    if not approved:
        raise HTTPException(status_code=400, detail="No hay clips aprobados para publicar.")

    published_count = 0
    failed_count = 0
    await add_log(job_id, f"Iniciando publicacion de {len(approved)} clip(s) aprobados.")

    for clip in approved:
        await set_clip_publish_status(job_id, clip.index, status="publishing")
        clip_path = (settings.jobs_dir / job_id / Path(clip.url).name).resolve()
        try:
            if not clip_path.exists():
                raise FileNotFoundError(f"No existe {clip_path.name}")
            result = await asyncio.to_thread(publish_to_tiktok, clip_path, clip.title, settings)
            post_id = str(result.get("post_id", ""))
            provider = str(result.get("provider", "")).strip() or "tiktok"
            await set_clip_publish_status(job_id, clip.index, status="published", post_id=post_id)
            await add_log(job_id, f"Clip {clip.index} publicado via {provider} ({post_id}).")
            published_count += 1
        except Exception as exc:
            await set_clip_publish_status(job_id, clip.index, status="failed", error=str(exc))
            await add_log(job_id, f"Fallo publicando clip {clip.index}: {exc}", level="ERROR")
            failed_count += 1

    summary_level = "SUCCESS" if failed_count == 0 else "INFO"
    await add_log(job_id, f"Publicacion finalizada. OK={published_count}, FAIL={failed_count}.", level=summary_level)
    return PublishApprovedResponse(published_count=published_count, failed_count=failed_count)


@app.get("/api/publishing/tiktok/integrations")
async def tiktok_integrations() -> dict:
    try:
        integrations = await asyncio.to_thread(list_tiktok_integrations, settings)
    except PostizPublisherError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"count": len(integrations), "integrations": integrations}


@app.post("/api/preview/subtitle-frame", response_model=SubtitlePreviewResponse)
async def subtitle_preview(payload: SubtitlePreviewRequest) -> SubtitlePreviewResponse:
    requested_font = (payload.subtitle_font_name or settings.subtitle_font_name).strip() or settings.subtitle_font_name
    requested_font_size = payload.subtitle_font_size or settings.subtitle_font_size
    requested_margin_h = payload.subtitle_margin_horizontal or settings.subtitle_margin_horizontal
    requested_margin_v = payload.subtitle_margin_vertical or settings.subtitle_margin_vertical
    requested_output_w = payload.output_width or settings.output_width
    requested_output_h = payload.output_height or settings.output_height
    requested_output_w, requested_output_h = _normalize_output_size(requested_output_w, requested_output_h)
    requested_background_image_url = (payload.background_image_url or "").strip()
    if requested_background_image_url and not requested_background_image_url.startswith("https://img.youtube.com/"):
        requested_background_image_url = ""

    preview_url = await asyncio.to_thread(
        render_subtitle_preview_image,
        settings,
        subtitle_font_name=requested_font,
        subtitle_font_size=requested_font_size,
        subtitle_margin_horizontal=max(20, requested_margin_h),
        subtitle_margin_vertical=max(20, requested_margin_v),
        output_width=requested_output_w,
        output_height=requested_output_h,
        subtitle_text=(payload.subtitle_text or "ESTA FRASE SE CONSTRUYE EN VIVO").strip(),
        background_image_url=requested_background_image_url or None,
    )
    return SubtitlePreviewResponse(preview_url=preview_url)


@app.get("/api/youtube/oembed")
async def youtube_oembed(url: str) -> dict:
    import httpx

    if "youtube.com" not in url and "youtu.be" not in url:
        raise HTTPException(status_code=400, detail="URL de YouTube invalida.")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                "https://www.youtube.com/oembed",
                params={"url": url, "format": "json"},
                timeout=5.0,
            )
            resp.raise_for_status()
            return resp.json()
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"No se pudo obtener metadata: {exc}") from exc


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str) -> FileResponse:
    if _is_reserved_path(full_path):
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")

    dist_root = settings.frontend_dist_dir
    dist_candidate = _safe_file_candidate(dist_root, full_path)
    if dist_candidate is not None:
        return FileResponse(dist_candidate)
    if Path(full_path).suffix:
        raise HTTPException(status_code=404, detail="Recurso no encontrado.")
    dist_index = dist_root / "index.html"
    if dist_index.exists():
        return FileResponse(dist_index)

    static_candidate = _safe_file_candidate(settings.static_dir, full_path)
    if static_candidate is not None:
        return FileResponse(static_candidate)
    raise HTTPException(status_code=404, detail="Recurso no encontrado.")
