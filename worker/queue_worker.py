"""
Blipr VPS Queue Worker
======================
Polls Supabase for pending jobs and postings, runs the existing pipeline,
uploads clips to R2, and syncs status back to Supabase.

Env vars needed (in addition to existing .env):
  SUPABASE_URL=https://<project>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

Run alongside FastAPI:
  python -m worker.queue_worker

Or wire into FastAPI lifespan (see bottom of this file).
"""

from __future__ import annotations

import asyncio
import logging
import os
import sys
from pathlib import Path

# Ensure project root is on sys.path when run as __main__
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv

load_dotenv(override=True)

from supabase import create_client, Client  # pip install supabase

from app.config import get_settings
from app.services.pipeline import run_job
from app.services.postiz import generate_caption, publish_clip
from app.services.r2 import upload_clip
from app.services.state import create_job, get_job
from app.services.tiktok_direct import get_valid_tiktok_token, publish_video_file, TikTokDirectError

log = logging.getLogger("blipr.worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

POLL_INTERVAL = 5  # seconds between polls


def _get_supabase() -> Client:
    url = os.environ["SUPABASE_URL"]
    key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
    return create_client(url, key)


# ─── Job status sync ──────────────────────────────────────────────────────────

async def _sync_job_status(supabase: Client, supabase_job_id: str, local_job_id: str) -> None:
    """Read in-memory pipeline state and push to Supabase jobs table."""
    job = await get_job(local_job_id)
    if job is None:
        return

    # Map local pipeline status → Supabase status enum
    status_map = {
        "queued": "pending",
        "running": "clipping",
        "completed": "done",
        "failed": "failed",
    }
    status = status_map.get(job.status, "clipping")

    # Refine based on current_step text
    if job.status == "running":
        step = (job.current_step or "").lower()
        if "descarg" in step or "download" in step:
            status = "downloading"
        elif "transcrib" in step:
            status = "transcribing"
        else:
            status = "clipping"

    update: dict = {"status": status, "logs": job.logs or []}
    if job.error:
        update["error_message"] = job.error

    supabase.table("jobs").update(update).eq("id", supabase_job_id).execute()


# ─── R2 upload + clip row ─────────────────────────────────────────────────────

async def _upload_clips_to_r2(supabase: Client, supabase_job_id: str, local_job_id: str) -> None:
    """After pipeline completes, upload each rendered clip to R2 and insert rows."""
    settings = get_settings()
    job = await get_job(local_job_id)
    if job is None:
        return

    for clip in job.clips:
        clip_path_str = str(settings.jobs_dir / local_job_id / Path(clip.url).name)
        clip_id = f"{local_job_id}:{clip.index}"

        try:
            r2_url = await asyncio.to_thread(upload_clip, clip_path_str, clip_id, settings)
            r2_key = f"clips/{clip_id.replace(':', '-')}.mp4"
            supabase.table("clips").insert({
                "job_id": supabase_job_id,
                "clip_index": clip.index,
                "start_seconds": clip.start,
                "end_seconds": clip.end,
                "transcript_excerpt": clip.transcript_excerpt or "",
                "r2_video_url": r2_url,
                "r2_key": r2_key,
                "title": clip.title or "",
                "score": float(clip.score),
            }).execute()
            log.info("Uploaded clip %d to R2: %s", clip.index, r2_url)
        except Exception as exc:
            log.error("Failed to upload clip %d to R2: %s", clip.index, exc)


# ─── Job poll loop ────────────────────────────────────────────────────────────

async def _process_job(supabase: Client, row: dict) -> None:
    supabase_job_id: str = row["id"]
    youtube_url: str = row["youtube_url"]

    log.info("Claiming job %s (%s)", supabase_job_id, youtube_url)
    supabase.table("jobs").update({"status": "downloading"}).eq("id", supabase_job_id).execute()

    settings = get_settings()

    # Create an in-memory job using settings stored in Supabase
    local_job = await create_job(
        youtube_url,
        requested_clips_count=int(row.get("clips_count") or settings.clips_count),
        requested_min_clip_seconds=settings.min_clip_seconds,
        requested_max_clip_seconds=settings.max_clip_seconds,
        requested_subtitle_font_name=str(row.get("subtitle_font_name") or settings.subtitle_font_name),
        requested_subtitle_margin_horizontal=int(row.get("subtitle_margin_horizontal") or settings.subtitle_margin_horizontal),
        requested_subtitle_margin_vertical=int(row.get("subtitle_margin_vertical") or settings.subtitle_margin_vertical),
        requested_output_width=int(row.get("output_width") or settings.output_width),
        requested_output_height=int(row.get("output_height") or settings.output_height),
        requested_content_genre=str(row.get("content_genre") or ""),
        requested_specific_moments_instruction=str(row.get("specific_moments_instruction") or ""),
        requested_ai_choose_count=bool(row.get("ai_choose_count") or False),
        requested_subtitles_enabled=bool(row.get("subtitles_enabled") if row.get("subtitles_enabled") is not None else True),
        requested_video_language=str(row.get("video_language") or "es"),
        requested_subtitle_font_size=int(row.get("subtitle_font_size") or 36),
    )
    local_job_id = local_job.job_id

    try:
        # Run pipeline stages; sync status every ~5 s via a background task
        async def status_syncer():
            while True:
                await asyncio.sleep(3)
                await _sync_job_status(supabase, supabase_job_id, local_job_id)

        sync_task = asyncio.create_task(status_syncer())
        try:
            await run_job(local_job_id, youtube_url)
        finally:
            sync_task.cancel()
            try:
                await sync_task
            except asyncio.CancelledError:
                pass

        # Final status check
        final_job = await get_job(local_job_id)
        if final_job and final_job.status == "completed":
            supabase.table("jobs").update({"status": "clipping"}).eq("id", supabase_job_id).execute()
            await _upload_clips_to_r2(supabase, supabase_job_id, local_job_id)
            supabase.table("jobs").update({"status": "done"}).eq("id", supabase_job_id).execute()
            log.info("Job %s done.", supabase_job_id)
        else:
            error_msg = (final_job.error if final_job else "Unknown error") or "Pipeline failed"
            supabase.table("jobs").update({"status": "failed", "error_message": error_msg}).eq("id", supabase_job_id).execute()
            log.error("Job %s failed: %s", supabase_job_id, error_msg)

    except Exception as exc:
        log.exception("Unhandled error processing job %s", supabase_job_id)
        supabase.table("jobs").update({"status": "failed", "error_message": str(exc)}).eq("id", supabase_job_id).execute()


async def poll_jobs(supabase: Client) -> None:
    """Poll for pending jobs and process them one at a time."""
    while True:
        try:
            result = (
                supabase.table("jobs")
                .select(
                    "id, youtube_url, clips_count, ai_choose_count, video_language, "
                    "content_genre, specific_moments_instruction, subtitles_enabled, "
                    "subtitle_font_name, subtitle_font_size, subtitle_margin_horizontal, "
                    "subtitle_margin_vertical, output_width, output_height"
                )
                .eq("status", "pending")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                await _process_job(supabase, rows[0])
            else:
                await asyncio.sleep(POLL_INTERVAL)
        except Exception:
            log.exception("Error in job poll loop")
            await asyncio.sleep(POLL_INTERVAL)


# ─── Posting poll loop ────────────────────────────────────────────────────────

async def _process_posting(supabase: Client, row: dict) -> None:
    posting_id: str = row["id"]
    clip_id: str = row["clip_id"]

    log.info("Processing posting %s for clip %s", posting_id, clip_id)
    supabase.table("postings").update({"status": "posting"}).eq("id", posting_id).execute()

    try:
        clip_result = supabase.table("clips").select("*").eq("id", clip_id).single().execute()
        clip_row = clip_result.data
        if not clip_row or not clip_row.get("r2_video_url"):
            raise RuntimeError("Clip not found or not yet uploaded to R2")

        settings = get_settings()
        local_job_id = None

        # Try to find the local clip file via job directory
        job_result = supabase.table("jobs").select("id").eq("id", clip_row["job_id"]).single().execute()
        if not job_result.data:
            raise RuntimeError("Parent job not found")

        # The clip file lives in jobs/<local_job_id>/clip_g01_01.mp4
        # We derive the local job directory from r2_key: clips/<local_job_id>-<index>.mp4
        r2_key: str = clip_row.get("r2_key", "")
        # r2_key format: clips/<job_id>-<clip_index>.mp4
        stem = Path(r2_key).stem  # e.g. "abc123def456-1"
        parts = stem.rsplit("-", 1)
        if len(parts) == 2:
            local_job_id = parts[0]

        if not local_job_id:
            raise RuntimeError("Cannot derive local job id from r2_key")

        job_dir = settings.jobs_dir / local_job_id
        clip_index = int(clip_row["clip_index"])
        # Find matching clip file
        clip_files = list(job_dir.glob(f"clip_g*_{clip_index:02d}.mp4"))
        if not clip_files:
            raise RuntimeError(f"No clip file found in {job_dir} for index {clip_index}")
        clip_path = str(clip_files[0])

        # Use user-provided caption/title if available, otherwise generate
        stored_caption: str = row.get("caption") or ""
        stored_title: str = row.get("post_title") or ""
        if stored_caption:
            caption = stored_caption
        else:
            transcript_excerpt = clip_row.get("transcript_excerpt") or ""
            caption = await asyncio.to_thread(generate_caption, transcript_excerpt, f"Clip {clip_index}", settings)

        title = stored_title or clip_row.get("title") or f"Clip {clip_index}"

        # Determine posting method: direct TikTok (if user has connected account) or Postiz fallback
        # Look up user_id from clip → job chain
        job_row = supabase.table("jobs").select("user_id").eq("id", clip_row["job_id"]).single().execute()
        user_id = job_row.data.get("user_id") if job_row.data else None

        used_direct = False
        if user_id:
            # Check if user has a direct TikTok connection
            acct = supabase.table("social_accounts").select("id").eq("user_id", user_id).eq("platform", "tiktok").single().execute()
            if acct.data:
                try:
                    token = await asyncio.to_thread(get_valid_tiktok_token, user_id)
                    direct_result = await asyncio.to_thread(
                        publish_video_file,
                        token,
                        clip_path,
                        title,
                        "SELF_ONLY",
                    )
                    post_id = str(direct_result.get("publish_id", ""))
                    supabase.table("postings").update({
                        "status": "posted",
                        "postiz_job_id": post_id,
                    }).eq("id", posting_id).execute()
                    log.info("Posting %s → posted via direct TikTok (publish_id=%s)", posting_id, post_id)
                    used_direct = True
                except (TikTokDirectError, Exception) as direct_exc:
                    log.warning("Direct TikTok failed for posting %s, falling back to Postiz: %s", posting_id, direct_exc)

        if not used_direct:
            # Fallback: Postiz
            result = await asyncio.to_thread(
                publish_clip,
                clip_path,
                f"{local_job_id}:{clip_index}",
                caption,
                title,
                None,
                settings,
            )
            post_id = str(result.get("post_id", ""))
            supabase.table("postings").update({
                "status": "posted",
                "postiz_job_id": post_id,
            }).eq("id", posting_id).execute()
            log.info("Posting %s → posted via Postiz (post_id=%s)", posting_id, post_id)

    except Exception as exc:
        log.error("Posting %s failed: %s", posting_id, exc)
        supabase.table("postings").update({
            "status": "failed",
            "error_message": str(exc),
        }).eq("id", posting_id).execute()


async def poll_postings(supabase: Client) -> None:
    """Poll for pending postings and process them."""
    while True:
        try:
            result = (
                supabase.table("postings")
                .select("id, clip_id, caption, post_title, schedule_time")
                .eq("status", "pending")
                .order("created_at", desc=False)
                .limit(1)
                .execute()
            )
            rows = result.data or []
            if rows:
                await _process_posting(supabase, rows[0])
            else:
                await asyncio.sleep(POLL_INTERVAL)
        except Exception:
            log.exception("Error in posting poll loop")
            await asyncio.sleep(POLL_INTERVAL)


# ─── Entry point ──────────────────────────────────────────────────────────────

async def run_worker() -> None:
    """Start both poll loops concurrently."""
    supabase = _get_supabase()
    log.info("Queue worker started. Polling every %ds.", POLL_INTERVAL)
    await asyncio.gather(
        poll_jobs(supabase),
        poll_postings(supabase),
    )


if __name__ == "__main__":
    asyncio.run(run_worker())
