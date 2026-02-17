import hashlib
import mimetypes
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

from app.config import Settings


class PostizPublisherError(RuntimeError):
    """Raised when Postiz API calls fail."""


def _normalize_postiz_public_api_url(raw_url: str) -> str:
    base = raw_url.strip().rstrip("/")
    if not base:
        return "http://localhost:5000/api/public/v1"
    if base.endswith("/public/v1"):
        return base
    if base.endswith("/api/public"):
        return f"{base}/v1"
    if base.endswith("/api"):
        return f"{base}/public/v1"
    return f"{base}/api/public/v1"


def _parse_api_error(response: requests.Response) -> str:
    text = response.text.strip()
    try:
        payload = response.json()
    except ValueError:
        return text or f"HTTP {response.status_code}"

    if isinstance(payload, dict):
        for key in ("message", "detail", "error"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
        errors = payload.get("errors")
        if isinstance(errors, list) and errors:
            first = errors[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                msg = first.get("message")
                if isinstance(msg, str) and msg.strip():
                    return msg.strip()
    return text or f"HTTP {response.status_code}"


def _request_postiz(settings: Settings, method: str, path: str, **kwargs: Any) -> Any:
    api_key = settings.postiz_api_key.strip()
    if not api_key:
        raise PostizPublisherError("Falta configurar POSTIZ_API_KEY.")

    timeout_seconds = max(5.0, float(settings.postiz_request_timeout_seconds))
    base_url = _normalize_postiz_public_api_url(settings.postiz_base_url)
    url = f"{base_url}{path}"
    headers = {"Authorization": api_key}
    custom_headers = kwargs.pop("headers", None)
    if isinstance(custom_headers, dict):
        headers.update(custom_headers)

    try:
        response = requests.request(method, url, headers=headers, timeout=timeout_seconds, **kwargs)
    except requests.RequestException as exc:
        raise PostizPublisherError(f"No se pudo conectar con Postiz en {url}: {exc}") from exc

    if response.status_code >= 400:
        detail = _parse_api_error(response)
        raise PostizPublisherError(f"Postiz devolvio {response.status_code}: {detail}")

    if not response.content:
        return {}
    try:
        return response.json()
    except ValueError as exc:
        raise PostizPublisherError("Postiz respondio contenido no JSON.") from exc


def _extract_integration_items(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        for key in ("integrations", "data", "items", "results"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
    return []


def _extract_integration_id(item: dict[str, Any]) -> str:
    for key in ("identifier", "id", "integrationId", "integration_id"):
        value = item.get(key)
        if isinstance(value, (str, int)) and str(value).strip():
            return str(value).strip()

    nested = item.get("integration")
    if isinstance(nested, dict):
        for key in ("identifier", "id"):
            value = nested.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()
    return ""


def _extract_integration_name(item: dict[str, Any]) -> str:
    for key in ("name", "label", "displayName", "username", "title"):
        value = item.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _flatten_strings(value: Any) -> list[str]:
    values: list[str] = []
    if isinstance(value, str):
        values.append(value)
    elif isinstance(value, dict):
        for nested in value.values():
            values.extend(_flatten_strings(nested))
    elif isinstance(value, list):
        for nested in value:
            values.extend(_flatten_strings(nested))
    return values


def _looks_like_tiktok(item: dict[str, Any]) -> bool:
    candidates = _flatten_strings(item)
    combined = " ".join(candidates).lower()
    return "tiktok" in combined


def list_tiktok_integrations(settings: Settings) -> list[dict[str, str]]:
    payload = _request_postiz(settings, "GET", "/integrations")
    integrations = []
    for item in _extract_integration_items(payload):
        if not _looks_like_tiktok(item):
            continue
        integration_id = _extract_integration_id(item)
        if not integration_id:
            continue
        integrations.append(
            {
                "id": integration_id,
                "name": _extract_integration_name(item),
            }
        )
    return integrations


def _resolve_tiktok_integration_id(settings: Settings) -> str:
    explicit = settings.postiz_tiktok_integration_id.strip()
    if explicit:
        return explicit

    integrations = list_tiktok_integrations(settings)
    if not integrations:
        raise PostizPublisherError(
            "No hay integraciones TikTok en Postiz. Conecta la cuenta en Postiz y/o define POSTIZ_TIKTOK_INTEGRATION_ID."
        )
    return integrations[0]["id"]


def _upload_media(settings: Settings, clip_path: Path) -> str:
    mime_type = mimetypes.guess_type(clip_path.name)[0] or "video/mp4"
    with clip_path.open("rb") as file_obj:
        payload = _request_postiz(
            settings,
            "POST",
            "/upload",
            files={"file": (clip_path.name, file_obj, mime_type)},
        )
    if not isinstance(payload, dict):
        raise PostizPublisherError("Respuesta invalida de /upload en Postiz.")

    for key in ("url", "path", "fileUrl"):
        value = payload.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    raise PostizPublisherError("Postiz no devolvio URL del archivo subido.")


def _source_payload(settings: Settings, title: str, integration_id: str, media_url: str, clip_path: Path) -> dict[str, Any]:
    clip_hash = hashlib.sha1(clip_path.name.encode("utf-8")).hexdigest()[:10]
    return {
        "integration": [{"id": integration_id, "value": [settings.postiz_tiktok_privacy_status]}],
        "value": title,
        "publicationDate": datetime.now(timezone.utc).isoformat(),
        "shortLink": False,
        "videoUrl": [{"id": f"clip-{clip_hash}", "name": clip_path.name, "path": media_url}],
    }


def _docs_payload(settings: Settings, title: str, integration_id: str, media_url: str) -> dict[str, Any]:
    return {
        "type": "post",
        "posts": [
            {
                "integration": {"id": integration_id},
                "value": title,
                "media": [{"path": media_url}],
                "settings": {
                    "tiktok": {
                        "privacyStatus": settings.postiz_tiktok_privacy_status,
                        "disableDuet": settings.postiz_tiktok_disable_duet,
                        "disableComment": settings.postiz_tiktok_disable_comment,
                        "disableStitch": settings.postiz_tiktok_disable_stitch,
                    }
                },
            }
        ],
        "publishNow": True,
        "shortLink": False,
        "date": datetime.now(timezone.utc).isoformat(),
    }


def _extract_post_id(payload: Any) -> str:
    if isinstance(payload, dict):
        for key in ("id", "post_id", "postId", "identifier"):
            value = payload.get(key)
            if isinstance(value, (str, int)) and str(value).strip():
                return str(value).strip()

        nested = payload.get("data")
        if isinstance(nested, dict):
            nested_id = _extract_post_id(nested)
            if nested_id:
                return nested_id

        posts = payload.get("posts")
        if isinstance(posts, list):
            for item in posts:
                post_id = _extract_post_id(item)
                if post_id:
                    return post_id
    elif isinstance(payload, list):
        for item in payload:
            post_id = _extract_post_id(item)
            if post_id:
                return post_id
    return ""


def _create_post(settings: Settings, title: str, integration_id: str, media_url: str, clip_path: Path) -> dict[str, Any]:
    payload_attempts = [
        _source_payload(settings, title, integration_id, media_url, clip_path),
        _docs_payload(settings, title, integration_id, media_url),
    ]
    errors: list[str] = []

    for payload in payload_attempts:
        try:
            result = _request_postiz(settings, "POST", "/posts", json=payload)
            if isinstance(result, dict):
                return result
            return {"data": result}
        except PostizPublisherError as exc:
            errors.append(str(exc))

    raise PostizPublisherError("No se pudo crear el post en Postiz. " + " | ".join(errors))


def _publish_via_postiz(clip_path: Path, title: str, settings: Settings) -> dict[str, str]:
    integration_id = _resolve_tiktok_integration_id(settings)
    media_url = _upload_media(settings, clip_path)
    response = _create_post(settings, title, integration_id, media_url, clip_path)
    post_id = _extract_post_id(response)
    if not post_id:
        fallback = hashlib.sha1(f"{clip_path.name}:{media_url}:{title}".encode("utf-8")).hexdigest()[:16]
        post_id = f"postiz_{fallback}"
    return {"post_id": post_id, "provider": "postiz"}


def publish_to_tiktok(clip_path: Path, title: str, settings: Settings) -> dict[str, str]:
    mode = settings.tiktok_publish_mode.strip().lower()
    if mode in {"", "mock"}:
        digest = hashlib.sha1(f"{clip_path.name}:{title}".encode("utf-8")).hexdigest()[:16]
        return {"post_id": f"mock_{digest}", "provider": "mock"}
    if mode == "postiz":
        return _publish_via_postiz(clip_path, title, settings)
    raise PostizPublisherError(
        f"TIKTOK_PUBLISH_MODE no soportado: '{settings.tiktok_publish_mode}'. Usa 'mock' o 'postiz'."
    )
