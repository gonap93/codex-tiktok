import shutil
import subprocess
import re
import unicodedata
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import Settings


def _as_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return dict(value)


def _normalize_alias(value: str) -> str:
    lowered = value.strip().lower()
    if not lowered:
        return ""
    normalized = unicodedata.normalize("NFKD", lowered)
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    alnum_only = "".join(char for char in without_accents if char.isalnum())
    return alnum_only


def _parse_entity_replacements(raw: str) -> dict[str, str]:
    if not raw.strip():
        return {}
    entries: dict[str, str] = {}
    chunks = [part.strip() for part in re.split(r"[;\n]+", raw) if part.strip()]
    for chunk in chunks:
        if "=>" not in chunk:
            continue
        alias_raw, canonical_raw = chunk.split("=>", 1)
        alias = alias_raw.strip()
        canonical = canonical_raw.strip()
        if not alias or not canonical:
            continue
        key = _normalize_alias(alias)
        if key:
            entries[key] = canonical
    return entries


def _replace_token_with_entities(token: str, replacements: dict[str, str]) -> str:
    key = _normalize_alias(token)
    if not key:
        return token
    canonical = replacements.get(key)
    if not canonical:
        return token
    if token.isupper():
        return canonical.upper()
    return canonical


def _apply_entity_replacements(text: str, replacements: dict[str, str]) -> str:
    if not text or not replacements:
        return text
    return re.sub(
        r"[A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ][A-Za-z0-9ÁÉÍÓÚÜÑáéíóúüñ'’.\-]*",
        lambda match: _replace_token_with_entities(match.group(0), replacements),
        text,
    )


def _build_transcription_prompt(settings: Settings, replacements: dict[str, str]) -> str:
    hint_terms = [term.strip() for term in re.split(r"[,;\n]+", str(settings.transcription_hint_terms)) if term.strip()]
    canonical_terms = list(dict.fromkeys(replacements.values()))
    merged_terms = list(dict.fromkeys([*hint_terms, *canonical_terms]))
    if not merged_terms:
        return ""
    return (
        "Transcripcion en espanol rioplatense. "
        "Respeta ortografia de nombres propios y empresas: " + ", ".join(merged_terms) + "."
    )


def _probe_duration_seconds(video_path: Path) -> float:
    if shutil.which("ffprobe") is None:
        raise RuntimeError("No se encontro ffprobe en PATH.")
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=noprint_wrappers=1:nokey=1",
        str(video_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"No se pudo leer duracion del video: {result.stderr.strip()}")
    try:
        return max(0.1, float(result.stdout.strip()))
    except ValueError as exc:
        raise RuntimeError("ffprobe devolvio una duracion invalida.") from exc


def _extract_audio_chunk(
    video_path: Path,
    output_chunk_path: Path,
    *,
    start: float,
    duration: float,
    bitrate: str,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("No se encontro ffmpeg en PATH.")

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(video_path),
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        "-b:a",
        bitrate,
        str(output_chunk_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg fallo al extraer audio: {result.stderr.strip()}")


def _transcribe_chunk(
    client: OpenAI,
    chunk_path: Path,
    settings: Settings,
    *,
    transcription_prompt: str,
) -> dict:
    request_payload: dict[str, Any] = {
        "model": settings.openai_transcription_model,
        "response_format": "verbose_json",
        "timestamp_granularities": ["segment", "word"],
    }
    if transcription_prompt.strip():
        request_payload["prompt"] = transcription_prompt.strip()
    with chunk_path.open("rb") as media_file:
        transcript = client.audio.transcriptions.create(file=media_file, **request_payload)
    return _as_dict(transcript)


def transcribe_video(video_path: Path, settings: Settings) -> dict:
    if not settings.openai_api_key:
        raise RuntimeError("Falta OPENAI_API_KEY en .env para usar Whisper API.")

    client = OpenAI(api_key=settings.openai_api_key)
    duration = _probe_duration_seconds(video_path)
    chunk_seconds = max(60, settings.transcription_chunk_seconds)
    overlap_seconds = max(0.0, min(chunk_seconds * 0.35, float(settings.transcription_chunk_overlap_seconds)))
    chunk_step = max(30.0, chunk_seconds - overlap_seconds)
    max_upload_bytes = max(1, settings.transcription_max_upload_mb) * 1024 * 1024
    entity_replacements = _parse_entity_replacements(str(settings.transcription_entity_replacements))
    transcription_prompt = _build_transcription_prompt(settings, entity_replacements)

    raw_segments: list[dict] = []
    raw_words: list[dict] = []
    chunk_starts: list[float] = []
    cursor = 0.0
    while cursor < duration:
        chunk_starts.append(cursor)
        cursor += chunk_step
    total_chunks = max(1, len(chunk_starts))

    for idx, chunk_start in enumerate(chunk_starts):
        chunk_duration = min(chunk_seconds, duration - chunk_start)
        if chunk_duration <= 0:
            continue

        chunk_path = video_path.parent / f"_audio_chunk_{idx:03d}.mp3"
        _extract_audio_chunk(
            video_path,
            chunk_path,
            start=chunk_start,
            duration=chunk_duration,
            bitrate=settings.transcription_audio_bitrate,
        )

        if chunk_path.stat().st_size > max_upload_bytes:
            chunk_path.unlink(missing_ok=True)
            raise RuntimeError(
                "Chunk de audio supera limite de Whisper. Reduce TRANSCRIPTION_CHUNK_SECONDS "
                "o TRANSCRIPTION_AUDIO_BITRATE en .env."
            )

        payload = _transcribe_chunk(
            client,
            chunk_path,
            settings,
            transcription_prompt=transcription_prompt,
        )
        chunk_path.unlink(missing_ok=True)
        chunk_segments = payload.get("segments", [])
        for raw_segment in chunk_segments:
            segment = _as_dict(raw_segment)
            segment["start"] = float(segment.get("start", 0.0)) + chunk_start
            segment["end"] = float(segment.get("end", 0.0)) + chunk_start
            raw_segments.append(segment)
        chunk_words = payload.get("words", [])
        for raw_word in chunk_words:
            word = _as_dict(raw_word)
            word["start"] = float(word.get("start", 0.0)) + chunk_start
            word["end"] = float(word.get("end", 0.0)) + chunk_start
            raw_words.append(word)

    segments: list[dict] = []
    for raw_segment in sorted(raw_segments, key=lambda item: (float(item.get("start", 0.0)), float(item.get("end", 0.0)))):
        segment = _as_dict(raw_segment)
        start = float(segment.get("start", 0.0))
        end = float(segment.get("end", start + 0.1))
        text = str(segment.get("text", "")).strip()
        text = _apply_entity_replacements(text, entity_replacements)
        if text:
            normalized_text = " ".join(text.lower().split())
            if segments:
                previous = segments[-1]
                if (
                    normalized_text == " ".join(str(previous["text"]).lower().split())
                    and abs(start - float(previous["start"])) <= 0.25
                    and abs(end - float(previous["end"])) <= 0.35
                ):
                    continue
            segments.append({"start": start, "end": max(end, start + 0.05), "text": text})

    if not segments:
        raise RuntimeError("Whisper no devolvio segmentos con chunks de audio.")

    words: list[dict] = []
    for raw_word in sorted(raw_words, key=lambda item: (float(item.get("start", 0.0)), float(item.get("end", 0.0)))):
        word = _as_dict(raw_word)
        text = str(word.get("word", word.get("text", ""))).strip()
        text = _apply_entity_replacements(text, entity_replacements)
        if not text:
            continue
        start = float(word.get("start", 0.0))
        end = float(word.get("end", start + 0.05))
        if words:
            previous = words[-1]
            if (
                text.lower() == str(previous["word"]).lower()
                and abs(start - float(previous["start"])) <= 0.08
                and abs(end - float(previous["end"])) <= 0.12
            ):
                continue
        words.append({"word": text, "start": start, "end": max(end, start + 0.03)})

    full_text = " ".join(segment["text"] for segment in segments)
    return {"text": full_text, "segments": segments, "words": words}
