import asyncio
import json
import re
from pathlib import Path

from app.config import get_settings
from app.models import ClipArtifact
from app.services.analyzer import choose_viral_moments
from app.services.clipper import render_clip_thumbnail, render_vertical_clip
from app.services.downloader import download_youtube_video
from app.services.state import add_clip, add_log, get_job, set_progress, start_new_generation
from app.services.subtitles import build_srt_for_clip
from app.services.transcriber import transcribe_video

MOMENTS_POOL_FILE = "moments_pool.json"
USED_MOMENTS_FILE = "used_moments.json"
REJECTION_FEEDBACK_FILE = "rejection_feedback.json"


def _safe_title(raw_title: str, index: int) -> str:
    title = " ".join(raw_title.split()).strip()
    if not title:
        return f"Clip {index}"
    return title[:80]


def _resolve_cached_source_video(job_dir: Path) -> Path | None:
    candidates = [path for path in job_dir.glob("source.*") if path.is_file()]
    if not candidates:
        return None
    return max(candidates, key=lambda path: path.stat().st_size)


def _load_json(path: Path, default):
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _moment_start(moment: dict) -> float:
    return float(moment.get("start", 0.0))


def _feedback_keywords(text: str) -> set[str]:
    raw = re.findall(r"[a-zA-Z0-9áéíóúñüÁÉÍÓÚÑÜ]+", text.lower())
    stop = {
        "para",
        "porque",
        "sobre",
        "este",
        "esta",
        "estos",
        "estas",
        "muy",
        "poco",
        "algo",
        "clip",
        "video",
        "idea",
        "tema",
        "cuando",
        "donde",
        "desde",
        "hasta",
        "solo",
        "pero",
        "como",
        "that",
        "this",
        "with",
        "from",
    }
    return {token for token in raw if len(token) >= 4 and token not in stop}


def _moment_relevance_penalty(moment: dict, feedback_tokens: set[str]) -> int:
    if not feedback_tokens:
        return 0
    moment_text = f"{moment.get('title', '')} {moment.get('reason', '')}"
    moment_tokens = _feedback_keywords(moment_text)
    return len(moment_tokens & feedback_tokens)


def _rank_pool_by_feedback(pool: list[dict], feedback_notes: list[str]) -> list[dict]:
    feedback_tokens: set[str] = set()
    for note in feedback_notes:
        feedback_tokens.update(_feedback_keywords(note))
    if not feedback_tokens:
        return pool
    return sorted(
        pool,
        key=lambda moment: (
            _moment_relevance_penalty(moment, feedback_tokens),
            -float(moment.get("score", 0.0)),
            _moment_start(moment),
        ),
    )


def _collect_rejection_feedback_from_job(job) -> list[str]:
    notes: list[str] = []
    for clip in job.clips:
        if clip.review_status != "rejected":
            continue
        reason = (clip.rejection_reason or "").strip()
        title = (clip.title or "").strip()
        if reason:
            notes.append(reason)
        if title:
            notes.append(title)
    return notes


def _unique_moments(moments: list[dict], min_gap_seconds: float = 8.0) -> list[dict]:
    deduped: list[dict] = []
    for moment in moments:
        start = _moment_start(moment)
        if any(abs(start - _moment_start(existing)) < min_gap_seconds for existing in deduped):
            continue
        deduped.append(moment)
    return deduped


def _select_unused_moments(
    pool: list[dict],
    used_starts: list[float],
    target_count: int,
    min_gap_seconds: float = 8.0,
) -> list[dict]:
    selected: list[dict] = []
    for moment in pool:
        start = _moment_start(moment)
        if any(abs(start - used) < min_gap_seconds for used in used_starts):
            continue
        if any(abs(start - _moment_start(existing)) < min_gap_seconds for existing in selected):
            continue
        selected.append(moment)
        if len(selected) >= target_count:
            break
    return selected


async def _render_moments_as_clips(
    *,
    job_id: str,
    job_dir: Path,
    source_video_path: Path,
    transcript: dict,
    moments: list[dict],
    generation: int,
    settings,
    progress_start: float,
    progress_span: float,
    subtitle_font_name: str,
    subtitle_margin_horizontal: int,
    subtitle_margin_vertical: int,
    output_width: int,
    output_height: int,
) -> None:
    clip_count = len(moments)
    if clip_count == 0:
        raise RuntimeError("No se encontraron momentos para renderizar clips.")

    for idx, moment in enumerate(moments, start=1):
        start = float(moment["start"])
        end = float(moment["end"])
        title = _safe_title(str(moment.get("title", f"Clip {idx}")), idx)
        current_progress = progress_start + (idx - 1) * (progress_span / clip_count)
        await set_progress(
            job_id,
            progress=current_progress,
            current_step=f"Generando clip {idx}/{clip_count}",
        )

        subtitles_path = job_dir / f"clip_g{generation:02d}_{idx:02d}.srt"
        clip_path = job_dir / f"clip_g{generation:02d}_{idx:02d}.mp4"
        thumb_path = job_dir / f"clip_g{generation:02d}_{idx:02d}.jpg"

        await asyncio.to_thread(
            build_srt_for_clip,
            transcript["segments"],
            start,
            end,
            subtitles_path,
            settings,
            transcript.get("words", []),
        )
        await asyncio.to_thread(
            render_vertical_clip,
            source_video_path,
            clip_path,
            subtitles_path,
            start,
            end,
            settings,
            subtitle_font_name,
            subtitle_margin_horizontal,
            subtitle_margin_vertical,
            output_width,
            output_height,
        )
        thumbnail_url = ""
        try:
            await asyncio.to_thread(render_clip_thumbnail, clip_path, thumb_path)
            thumbnail_url = f"/jobs/{job_id}/{thumb_path.name}"
        except Exception:
            thumbnail_url = ""

        clip_url = f"/jobs/{job_id}/{clip_path.name}"
        clip = ClipArtifact(
            index=idx,
            title=title,
            start=start,
            end=end,
            duration=round(end - start, 2),
            url=clip_url,
            thumbnail_url=thumbnail_url,
        )
        await add_clip(job_id, clip)
        await add_log(job_id, f"Clip {idx} listo: {clip_path.name}")


async def _build_or_extend_moment_pool(
    *,
    transcript: dict,
    settings,
    target_clips: int,
    min_clip_seconds: int,
    max_clip_seconds: int,
    existing_pool: list[dict],
    rejection_feedback: list[str] | None = None,
) -> list[dict]:
    pool = _unique_moments(existing_pool)
    min_pool_size = max(target_clips * 3, target_clips + 6)
    if len(pool) >= min_pool_size:
        return _rank_pool_by_feedback(pool, rejection_feedback or [])

    fresh = await asyncio.to_thread(
        choose_viral_moments,
        transcript,
        settings,
        min_pool_size,
        min_clip_seconds,
        max_clip_seconds,
        rejection_feedback or [],
    )
    return _rank_pool_by_feedback(_unique_moments(pool + fresh), rejection_feedback or [])


async def regenerate_job_from_cache(job_id: str) -> None:
    settings = get_settings()
    job_dir = settings.jobs_dir / job_id
    transcript_path = job_dir / "transcript.json"
    moments_path = job_dir / "moments.json"
    pool_path = job_dir / MOMENTS_POOL_FILE
    used_path = job_dir / USED_MOMENTS_FILE
    feedback_path = job_dir / REJECTION_FEEDBACK_FILE

    try:
        job = await get_job(job_id)
        if job is None:
            raise RuntimeError("Job no encontrado para regeneracion.")
        source_video_path = _resolve_cached_source_video(job_dir)
        if source_video_path is None:
            raise RuntimeError("No se encontro source.* para regenerar.")
        if not transcript_path.exists():
            raise RuntimeError("No se encontro transcript.json para regenerar.")

        await set_progress(job_id, status="running", progress=10, current_step="Regenerando desde cache")
        await add_log(job_id, "Regeneracion iniciada usando cache (sin re-transcribir).")

        transcript = _load_json(transcript_path, {})
        if "segments" not in transcript:
            raise RuntimeError("Transcript cache invalido.")

        target_clips = max(1, int(job.requested_clips_count))
        min_clip_seconds = max(5, int(job.requested_min_clip_seconds))
        max_clip_seconds = max(min_clip_seconds, int(job.requested_max_clip_seconds))
        subtitle_font_name = job.requested_subtitle_font_name
        subtitle_margin_horizontal = int(job.requested_subtitle_margin_horizontal)
        subtitle_margin_vertical = int(job.requested_subtitle_margin_vertical)
        output_width = int(job.requested_output_width)
        output_height = int(job.requested_output_height)
        feedback_notes = _load_json(feedback_path, [])
        current_feedback = _collect_rejection_feedback_from_job(job)
        if current_feedback:
            merged_feedback = list(dict.fromkeys([*feedback_notes, *current_feedback]))
            _save_json(feedback_path, merged_feedback)
            feedback_notes = merged_feedback

        pool = _load_json(pool_path, [])
        used_starts = [float(item) for item in _load_json(used_path, [])]
        pool = await _build_or_extend_moment_pool(
            transcript=transcript,
            settings=settings,
            target_clips=target_clips,
            min_clip_seconds=min_clip_seconds,
            max_clip_seconds=max_clip_seconds,
            existing_pool=pool,
            rejection_feedback=feedback_notes,
        )
        _save_json(pool_path, pool)

        selected = _select_unused_moments(pool, used_starts, target_clips)
        if len(selected) < target_clips:
            await add_log(job_id, "Pool de momentos agotado; se intentara completar con nuevos candidatos.")
            extra = await asyncio.to_thread(
                choose_viral_moments,
                transcript,
                settings,
                max(target_clips * 2, 8),
                min_clip_seconds,
                max_clip_seconds,
                feedback_notes,
            )
            pool = _rank_pool_by_feedback(_unique_moments(pool + extra), feedback_notes)
            _save_json(pool_path, pool)
            selected = _select_unused_moments(pool, used_starts, target_clips)

        if not selected:
            raise RuntimeError("No se encontraron nuevos momentos para regenerar.")
        selected = selected[:target_clips]
        _save_json(moments_path, selected)

        generation = await start_new_generation(job_id)
        await _render_moments_as_clips(
            job_id=job_id,
            job_dir=job_dir,
            source_video_path=source_video_path,
            transcript=transcript,
            moments=selected,
            generation=generation,
            settings=settings,
            progress_start=52,
            progress_span=44,
            subtitle_font_name=subtitle_font_name,
            subtitle_margin_horizontal=subtitle_margin_horizontal,
            subtitle_margin_vertical=subtitle_margin_vertical,
            output_width=output_width,
            output_height=output_height,
        )

        used_starts.extend(_moment_start(moment) for moment in selected)
        _save_json(used_path, used_starts)

        await set_progress(job_id, status="completed", progress=100, current_step="Completado")
        await add_log(job_id, "Regeneracion completada usando assets cacheados.")
    except asyncio.CancelledError:
        await set_progress(
            job_id,
            status="failed",
            progress=100,
            current_step="Cancelado",
            error="Proceso cancelado por reinicio manual.",
        )
        await add_log(job_id, "Regeneracion cancelada por reinicio manual.")
        raise
    except Exception as exc:
        await set_progress(job_id, status="failed", progress=100, current_step="Error", error=str(exc))
        await add_log(job_id, f"Fallo regenerando clips: {exc}")


async def run_job(job_id: str, youtube_url: str) -> None:
    settings = get_settings()
    job_dir = settings.jobs_dir / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    transcript_path = job_dir / "transcript.json"
    moments_path = job_dir / "moments.json"
    pool_path = job_dir / MOMENTS_POOL_FILE
    used_path = job_dir / USED_MOMENTS_FILE
    feedback_path = job_dir / REJECTION_FEEDBACK_FILE

    try:
        await set_progress(job_id, status="running", progress=2, current_step="Preparando job")
        await add_log(job_id, "Job iniciado.")

        await set_progress(job_id, progress=8, current_step="Descargando video de YouTube")
        source_video_path = await asyncio.to_thread(download_youtube_video, youtube_url, job_dir, settings)
        await add_log(job_id, f"Descarga completada: {source_video_path.name}")

        await set_progress(job_id, progress=25, current_step="Transcribiendo con Whisper")
        transcript = await asyncio.to_thread(transcribe_video, source_video_path, settings)
        _save_json(transcript_path, transcript)
        await add_log(job_id, "Transcripcion completada.")

        await set_progress(job_id, progress=42, current_step="Seleccionando momentos virales")
        job = await get_job(job_id)
        if job is None:
            raise RuntimeError("Job no encontrado durante analisis.")

        target_clips = max(1, int(job.requested_clips_count))
        min_clip_seconds = max(5, int(job.requested_min_clip_seconds))
        max_clip_seconds = max(min_clip_seconds, int(job.requested_max_clip_seconds))
        subtitle_font_name = job.requested_subtitle_font_name
        subtitle_margin_horizontal = int(job.requested_subtitle_margin_horizontal)
        subtitle_margin_vertical = int(job.requested_subtitle_margin_vertical)
        output_width = int(job.requested_output_width)
        output_height = int(job.requested_output_height)
        feedback_notes = _load_json(feedback_path, [])

        pool = await _build_or_extend_moment_pool(
            transcript=transcript,
            settings=settings,
            target_clips=target_clips,
            min_clip_seconds=min_clip_seconds,
            max_clip_seconds=max_clip_seconds,
            existing_pool=[],
            rejection_feedback=feedback_notes,
        )
        _save_json(pool_path, pool)

        selected = _select_unused_moments(pool, [], target_clips)
        if not selected:
            raise RuntimeError("No se pudieron identificar momentos para generar clips.")
        selected = selected[:target_clips]
        _save_json(moments_path, selected)
        await add_log(job_id, f"Momentos seleccionados: {len(selected)}.")

        generation = job.generation
        await _render_moments_as_clips(
            job_id=job_id,
            job_dir=job_dir,
            source_video_path=source_video_path,
            transcript=transcript,
            moments=selected,
            generation=generation,
            settings=settings,
            progress_start=52,
            progress_span=44,
            subtitle_font_name=subtitle_font_name,
            subtitle_margin_horizontal=subtitle_margin_horizontal,
            subtitle_margin_vertical=subtitle_margin_vertical,
            output_width=output_width,
            output_height=output_height,
        )
        _save_json(used_path, [_moment_start(moment) for moment in selected])

        await set_progress(job_id, status="completed", progress=100, current_step="Completado")
        await add_log(job_id, "Pipeline finalizado con exito.")
    except asyncio.CancelledError:
        await set_progress(
            job_id,
            status="failed",
            progress=100,
            current_step="Cancelado",
            error="Proceso cancelado por reinicio manual.",
        )
        await add_log(job_id, "Job cancelado por reinicio manual.")
        raise
    except Exception as exc:
        await set_progress(job_id, status="failed", progress=100, current_step="Error", error=str(exc))
        await add_log(job_id, f"Fallo del pipeline: {exc}")
