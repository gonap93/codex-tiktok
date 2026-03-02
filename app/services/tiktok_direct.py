"""Direct TikTok integration — token refresh and posting via TikTok Content Posting API."""

from datetime import datetime, timezone, timedelta

import httpx
from supabase import create_client, Client

from app.config import get_settings


class TikTokDirectError(Exception):
    pass


def _get_supabase() -> Client:
    s = get_settings()
    if not s.supabase_url or not s.supabase_service_role_key:
        raise TikTokDirectError("Supabase credentials not configured")
    return create_client(s.supabase_url, s.supabase_service_role_key)


def get_valid_tiktok_token(user_id: str) -> str:
    """Return a valid TikTok access token for the user, refreshing if needed."""
    sb = _get_supabase()
    result = sb.table("social_accounts").select("*").eq("user_id", user_id).eq("platform", "tiktok").single().execute()

    if not result.data:
        raise TikTokDirectError("TikTok account not connected")

    account = result.data
    expires_at = account.get("access_token_expires_at")

    # If token is still valid (with 5min buffer), return it
    if expires_at:
        exp = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        if exp > datetime.now(timezone.utc) + timedelta(minutes=5):
            return account["access_token"]

    # Refresh the token
    s = get_settings()
    if not s.tiktok_client_key or not s.tiktok_client_secret:
        raise TikTokDirectError("TikTok client credentials not configured")

    refresh_token = account.get("refresh_token")
    if not refresh_token:
        raise TikTokDirectError("No refresh token available — user must reconnect TikTok")

    with httpx.Client(timeout=15) as client:
        resp = client.post(
            "https://open.tiktokapis.com/v2/oauth/token/",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data={
                "client_key": s.tiktok_client_key,
                "client_secret": s.tiktok_client_secret,
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
        )

    if resp.status_code != 200:
        raise TikTokDirectError(f"Token refresh failed: HTTP {resp.status_code}")

    token_data = resp.json()
    if token_data.get("error"):
        raise TikTokDirectError(f"Token refresh error: {token_data.get('error_description', token_data['error'])}")

    new_access = token_data["access_token"]
    new_refresh = token_data.get("refresh_token", refresh_token)
    now = datetime.now(timezone.utc)
    access_expires = (now + timedelta(seconds=token_data["expires_in"])).isoformat()
    refresh_expires = (now + timedelta(seconds=token_data.get("refresh_expires_in", 86400 * 365))).isoformat()

    sb.table("social_accounts").update({
        "access_token": new_access,
        "refresh_token": new_refresh,
        "access_token_expires_at": access_expires,
        "refresh_token_expires_at": refresh_expires,
    }).eq("user_id", user_id).eq("platform", "tiktok").execute()

    return new_access


def query_creator_info(access_token: str) -> dict:
    """Query TikTok creator info to get allowed privacy levels etc."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            "https://open.tiktokapis.com/v2/post/publish/creator_info/query/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
        )
    if resp.status_code != 200:
        raise TikTokDirectError(f"Creator info query failed: HTTP {resp.status_code}")
    data = resp.json()
    if data.get("error", {}).get("code") != "ok":
        err = data.get("error", {})
        raise TikTokDirectError(f"Creator info error: {err.get('message', err.get('code', 'unknown'))}")
    return data.get("data", {})


def init_file_upload(
    access_token: str,
    video_size: int,
    title: str = "",
    privacy_level: str = "SELF_ONLY",
) -> dict:
    """Initialize a direct file upload post to TikTok. Returns upload_url and publish_id."""
    payload = {
        "post_info": {
            "privacy_level": privacy_level,
            "title": (title or "")[:150],
        },
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": video_size,  # single chunk upload
            "total_chunk_count": 1,
        },
    }

    with httpx.Client(timeout=30) as client:
        resp = client.post(
            "https://open.tiktokapis.com/v2/post/publish/video/init/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
            json=payload,
        )

    if resp.status_code != 200:
        raise TikTokDirectError(f"Post init failed: HTTP {resp.status_code} — {resp.text}")

    data = resp.json()
    err = data.get("error", {})
    if err.get("code") != "ok":
        raise TikTokDirectError(f"Post init error: {err.get('message', err.get('code', 'unknown'))}")

    return data.get("data", {})


def upload_video_to_tiktok(upload_url: str, video_data: bytes) -> None:
    """Upload video bytes to TikTok's upload URL."""
    video_size = len(video_data)
    headers = {
        "Content-Range": f"bytes 0-{video_size - 1}/{video_size}",
        "Content-Length": str(video_size),
        "Content-Type": "video/mp4",
    }

    with httpx.Client(timeout=300) as client:
        resp = client.put(upload_url, headers=headers, content=video_data)

    if resp.status_code not in (200, 201):
        raise TikTokDirectError(f"Video upload failed: HTTP {resp.status_code} — {resp.text}")


def publish_video_file(
    access_token: str,
    video_path: str,
    title: str = "",
    privacy_level: str = "SELF_ONLY",
) -> dict:
    """Full file upload flow: init → upload bytes → return publish_id."""
    import os
    video_size = os.path.getsize(video_path)
    if video_size == 0:
        raise TikTokDirectError("Video file is empty")

    # Step 1: Init upload
    init_data = init_file_upload(access_token, video_size, title, privacy_level)
    upload_url = init_data.get("upload_url")
    publish_id = init_data.get("publish_id", "")

    if not upload_url:
        raise TikTokDirectError(f"No upload_url in init response: {init_data}")

    # Step 2: Upload video bytes
    with open(video_path, "rb") as f:
        video_data = f.read()

    upload_video_to_tiktok(upload_url, video_data)

    return {"publish_id": publish_id}


def download_and_publish(
    access_token: str,
    video_url: str,
    title: str = "",
    privacy_level: str = "SELF_ONLY",
) -> dict:
    """Download video from URL, then upload to TikTok via file upload."""
    # Download video from R2/URL
    with httpx.Client(timeout=120, follow_redirects=True) as client:
        resp = client.get(video_url)
    if resp.status_code != 200:
        raise TikTokDirectError(f"Failed to download video from {video_url}: HTTP {resp.status_code}")

    video_data = resp.content
    video_size = len(video_data)
    if video_size == 0:
        raise TikTokDirectError("Downloaded video is empty")

    # Init upload
    init_data = init_file_upload(access_token, video_size, title, privacy_level)
    upload_url = init_data.get("upload_url")
    publish_id = init_data.get("publish_id", "")

    if not upload_url:
        raise TikTokDirectError(f"No upload_url in init response: {init_data}")

    # Upload
    upload_video_to_tiktok(upload_url, video_data)

    return {"publish_id": publish_id}


def fetch_publish_status(access_token: str, publish_id: str) -> dict:
    """Check the status of a TikTok publish request."""
    with httpx.Client(timeout=15) as client:
        resp = client.post(
            "https://open.tiktokapis.com/v2/post/publish/status/fetch/",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"publish_id": publish_id},
        )

    if resp.status_code != 200:
        raise TikTokDirectError(f"Status fetch failed: HTTP {resp.status_code}")

    data = resp.json()
    err = data.get("error", {})
    if err.get("code") != "ok":
        raise TikTokDirectError(f"Status fetch error: {err.get('message', err.get('code', 'unknown'))}")

    return data.get("data", {})
