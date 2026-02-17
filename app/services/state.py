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
        )
        _jobs[job_id] = job
        _broadcast(job)
        return job


async def get_job(job_id: str) -> JobState | None:
    async with _lock:
        return _jobs.get(job_id)


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


async def add_log(job_id: str, message: str) -> JobState:
    async with _lock:
        job = _jobs[job_id]
        job.logs.append(message)
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
    approved: bool,
    rejection_reason: str | None = None,
) -> JobState:
    async with _lock:
        job = _jobs[job_id]
        clip = _find_clip(job, clip_index)
        clip.review_status = "approved" if approved else "rejected"
        if approved:
            clip.rejection_reason = ""
        else:
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
