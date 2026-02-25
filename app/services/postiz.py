import mimetypes
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from openai import OpenAI

from app.config import Settings
from app.services.tiktok_publisher import PostizPublisherError, _extract_post_id, _request_postiz


def upload_to_postiz(file_path: str, settings: Settings) -> tuple[str, str]:
    """Upload a video file to Postiz Media. Returns (media_id, media_path) for use in posts."""
    path = Path(file_path)
    if not path.is_file():
        raise PostizPublisherError(f"Archivo no encontrado: {file_path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "video/mp4"
    with path.open("rb") as f:
        payload = _request_postiz(
            settings,
            "POST",
            "/upload",
            files={"file": (path.name, f, mime_type)},
        )
    if not isinstance(payload, dict):
        raise PostizPublisherError("Respuesta invalida de Postiz al subir el archivo.")
    media_id = payload.get("id") or "video-0"
    media_path = (
        payload.get("path")
        or payload.get("url")
        or payload.get("fileUrl")
    )
    if not isinstance(media_path, str) or not media_path.strip():
        raise PostizPublisherError("Postiz no devolvio la URL del archivo subido.")
    return (str(media_id).strip(), media_path.strip())


def generate_caption(transcript: str, clip_context: str, settings: Settings) -> str:
    client = OpenAI(api_key=settings.openai_api_key)
    prompt = (
        "Eres un experto en contenido viral para TikTok. "
        "Genera un caption atractivo y viral en español para el siguiente clip de video.\n\n"
        f"Contexto del clip: {clip_context}\n\n"
        f"Transcripcion del clip:\n{transcript}\n\n"
        "El caption debe:\n"
        "- Empezar con un hook que genere curiosidad\n"
        "- Ser atractivo y generar engagement\n"
        "- Incluir 3-5 hashtags relevantes al final\n"
        "- Tener maximo 2200 caracteres\n"
        "Responde solo con el caption, sin explicaciones."
    )
    response = client.chat.completions.create(
        model=settings.openai_analysis_model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=600,
    )
    caption = (response.choices[0].message.content or "").strip()
    return caption[:2200]


def post_to_tiktok(
    media_id: str,
    media_path: str,
    caption: str,
    title: str,
    schedule_time: str | None,
    settings: Settings,
) -> dict[str, Any]:
    integration_id = settings.postiz_tiktok_integration_id.strip()
    if not integration_id:
        raise PostizPublisherError(
            "Falta configurar TIKTOK_INTEGRATION_ID o POSTIZ_TIKTOK_INTEGRATION_ID."
        )

    # Postiz only has "schedule" and "draft"; use "schedule" for publish. For "now", use 5 min
    # in the future so Postiz doesn't treat it as already past and skip publishing to TikTok.
    # Use ISO 8601 with Z suffix (YYYY-MM-DDTHH:MM:SSZ) for compatibility.
    post_type = "schedule"
    if schedule_time:
        date = schedule_time
    else:
        when = datetime.now(timezone.utc) + timedelta(minutes=5)
        date = when.strftime("%Y-%m-%dT%H:%M:%SZ")
    # Postiz API: value is array of { content, image: [{ id, path }] }; TikTok title max 90 chars
    payload: dict[str, Any] = {
        "type": post_type,
        "date": date,
        "shortLink": False,
        "tags": [],
        "posts": [
            {
                "integration": {"id": integration_id},
                "value": [
                    {
                        "content": caption,
                        "image": [{"id": media_id, "path": media_path}],
                    }
                ],
                "settings": {
                    "__type": "tiktok",
                    "title": (title or "Video")[:90],
                    "privacy_level": "SELF_ONLY",
                    "duet": False,
                    "stitch": True,
                    "comment": True,
                    "autoAddMusic": "no",
                    "brand_content_toggle": False,
                    "brand_organic_toggle": False,
                    "video_made_with_ai": False,
                    "content_posting_method": "DIRECT_POST",
                },
            }
        ],
    }

    result = _request_postiz(settings, "POST", "/posts", json=payload)
    return result if isinstance(result, dict) else {"data": result}


def publish_clip(
    file_path: str,
    clip_id: str,
    caption: str,
    title: str,
    schedule_time: str | None,
    settings: Settings,
) -> dict[str, Any]:
    # 1. Upload video to Postiz Media so it appears in Media and the post can publish to TikTok
    media_id, media_path = upload_to_postiz(file_path, settings)

    # 2. Create post in Postiz with that media (schedule with current time = publish now)
    result = post_to_tiktok(media_id, media_path, caption, title, schedule_time, settings)
    post_id = _extract_post_id(result)
    return {"post_id": post_id, "provider": "postiz", **result}
