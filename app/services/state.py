import asyncio
from datetime import datetime, timezone
from uuid import uuid4

from app.models import ClipArtifact, JobState

_jobs: dict[str, JobState] = {}
_subscribers: dict[str, set[asyncio.Queue]] = {}
_lock = asyncio.Lock()


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _broadcast(job: JobState) -> None:
    payload = job.model_dump(mode="json")
    queues = _subscribers.get(job.job_id, set())
    for queue in list(queues):
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            queues.discard(queue)


def _find_clip(job: JobState, clip_index: int) -> ClipArtifact:
    for clip in job.clips:
        if clip.index == clip_index:
            return clip
    raise KeyError(f"Clip {clip_index} no encontrado.")


async def create_job(
    youtube_url: str,
    requested_clips_count: int,
    requested_min_clip_seconds: int,
    requested_max_clip_seconds: int,
    requested_subtitle_font_name: str,
    requested_subtitle_margin_horizontal: int,
    requested_subtitle_margin_vertical: int,
    requested_output_width: int,
    requested_output_height: int,
    *,
    requested_content_genre: str = "",
    requested_specific_moments_instruction: str = "",
    requested_ai_choose_count: bool = False,
    requested_subtitles_enabled: bool = True,
    requested_subtitle_preset: str = "",
    requested_video_language: str = "es",
    requested_subtitle_font_size: int = 36,
) -> JobState:
    async with _lock:
        job_id = uuid4().hex[:12]
        job = JobState(
            job_id=job_id,
            youtube_url=youtube_url,
            requested_clips_count=requested_clips_count,
            requested_min_clip_seconds=requested_min_clip_seconds,
            requested_max_clip_seconds=requested_max_clip_seconds,
            requested_subtitle_font_name=requested_subtitle_font_name,
            requested_subtitle_margin_horizontal=requested_subtitle_margin_horizontal,
            requested_subtitle_margin_vertical=requested_subtitle_margin_vertical,
            requested_output_width=requested_output_width,
            requested_output_height=requested_output_height,
            requested_content_genre=requested_content_genre,
            requested_specific_moments_instruction=requested_specific_moments_instruction,
            requested_ai_choose_count=requested_ai_choose_count,
            requested_subtitles_enabled=requested_subtitles_enabled,
            requested_subtitle_preset=requested_subtitle_preset,
            requested_video_language=requested_video_language,
            requested_subtitle_font_size=requested_subtitle_font_size,
        )
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def get_job(job_id: str) -> JobState | None:
    async with _lock:
        return _jobs.get(job_id)


async def list_jobs() -> list[JobState]:
    async with _lock:
        return list(_jobs.values())


async def set_progress(
    job_id: str,
    *,
    status: str | None = None,
    progress: float | None = None,
    current_step: str | None = None,
    error: str | None = None,
) -> JobState:
    async with _lock:
        job = _jobs[job_id]
        if status is not None:
            job.status = status  # type: ignore[assignment]
        if progress is not None:
            job.progress = max(0.0, min(100.0, progress))
        if current_step is not None:
            job.current_step = current_step
        if error is not None:
            job.error = error
        job.updated_at = _utc_now_iso()
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def add_log(job_id: str, message: str, *, level: str = "INFO") -> JobState:
    async with _lock:
        job = _jobs[job_id]
        ts = datetime.now(timezone.utc).strftime("%H:%M:%S")
        job.logs.append(f"[{ts}] [{level}] {message}")
        job.updated_at = _utc_now_iso()
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def add_clip(job_id: str, clip: ClipArtifact) -> JobState:
    async with _lock:
        job = _jobs[job_id]
        job.clips.append(clip)
        job.updated_at = _utc_now_iso()
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def set_clip_review_status(
    job_id: str,
    clip_index: int,
    approved: bool | None,
    rejection_reason: str | None = None,
) -> JobState:
    async with _lock:
        job = _jobs[job_id]
        clip = _find_clip(job, clip_index)
        if approved is None:
            clip.review_status = "pending"
            clip.rejection_reason = ""
        elif approved:
            clip.review_status = "approved"
            clip.rejection_reason = ""
        else:
            clip.review_status = "rejected"
            clip.rejection_reason = (rejection_reason or "").strip()
            clip.publish_status = "not_published"
            clip.publish_error = ""
            clip.tiktok_post_id = ""
        job.updated_at = _utc_now_iso()
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def set_clip_publish_status(
    job_id: str,
    clip_index: int,
    *,
    status: str,
    post_id: str = "",
    error: str = "",
) -> JobState:
    async with _lock:
        job = _jobs[job_id]
        clip = _find_clip(job, clip_index)
        clip.publish_status = status  # type: ignore[assignment]
        clip.tiktok_post_id = post_id
        clip.publish_error = error
        job.updated_at = _utc_now_iso()
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def update_job_requests(
    job_id: str,
    *,
    requested_clips_count: int | None = None,
    requested_min_clip_seconds: int | None = None,
    requested_max_clip_seconds: int | None = None,
    requested_subtitle_font_name: str | None = None,
    requested_subtitle_margin_horizontal: int | None = None,
    requested_subtitle_margin_vertical: int | None = None,
    requested_output_width: int | None = None,
    requested_output_height: int | None = None,
    requested_content_genre: str | None = None,
    requested_specific_moments_instruction: str | None = None,
    requested_ai_choose_count: bool | None = None,
    requested_subtitles_enabled: bool | None = None,
    requested_subtitle_preset: str | None = None,
    requested_video_language: str | None = None,
    requested_subtitle_font_size: int | None = None,
) -> JobState:
    async with _lock:
        job = _jobs[job_id]
        if requested_clips_count is not None:
            job.requested_clips_count = requested_clips_count
        if requested_min_clip_seconds is not None:
            job.requested_min_clip_seconds = requested_min_clip_seconds
        if requested_max_clip_seconds is not None:
            job.requested_max_clip_seconds = requested_max_clip_seconds
        if requested_subtitle_font_name is not None:
            job.requested_subtitle_font_name = requested_subtitle_font_name
        if requested_subtitle_margin_horizontal is not None:
            job.requested_subtitle_margin_horizontal = requested_subtitle_margin_horizontal
        if requested_subtitle_margin_vertical is not None:
            job.requested_subtitle_margin_vertical = requested_subtitle_margin_vertical
        if requested_output_width is not None:
            job.requested_output_width = requested_output_width
        if requested_output_height is not None:
            job.requested_output_height = requested_output_height
        if requested_content_genre is not None:
            job.requested_content_genre = requested_content_genre
        if requested_specific_moments_instruction is not None:
            job.requested_specific_moments_instruction = requested_specific_moments_instruction
        if requested_ai_choose_count is not None:
            job.requested_ai_choose_count = requested_ai_choose_count
        if requested_subtitles_enabled is not None:
            job.requested_subtitles_enabled = requested_subtitles_enabled
        if requested_subtitle_preset is not None:
            job.requested_subtitle_preset = requested_subtitle_preset
        if requested_video_language is not None:
            job.requested_video_language = requested_video_language
        if requested_subtitle_font_size is not None:
            job.requested_subtitle_font_size = requested_subtitle_font_size
        job.updated_at = _utc_now_iso()
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def start_new_generation(job_id: str) -> int:
    async with _lock:
        job = _jobs[job_id]
        job.generation += 1
        job.clips = []
        job.error = ""
        job.updated_at = _utc_now_iso()
        _jobs[job_id] = job
        _broadcast(job)
        return job.generation


async def subscribe(job_id: str) -> asyncio.Queue:
    async with _lock:
        queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        _subscribers.setdefault(job_id, set()).add(queue)
        job = _jobs.get(job_id)
        if job is not None:
            try:
                queue.put_nowait(job.model_dump(mode="json"))
            except asyncio.QueueFull:
                pass
        return queue


async def unsubscribe(job_id: str, queue: asyncio.Queue) -> None:
    async with _lock:
        if job_id in _subscribers:
            _subscribers[job_id].discard(queue)
