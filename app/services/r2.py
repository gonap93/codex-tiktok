import boto3
from botocore.exceptions import ClientError

from app.config import Settings


class R2UploadError(RuntimeError):
    """Raised when R2 upload or delete operations fail."""


def _get_client(settings: Settings):
    return boto3.client(
        "s3",
        endpoint_url=f"https://{settings.r2_account_id}.r2.cloudflarestorage.com",
        aws_access_key_id=settings.r2_access_key_id,
        aws_secret_access_key=settings.r2_secret_access_key,
        region_name="auto",
    )


def _object_key(clip_id: str) -> str:
    # Replace colons so the key is unambiguously URL-safe (e.g. "job123-1.mp4").
    return f"clips/{clip_id.replace(':', '-')}.mp4"


def upload_clip(file_path: str, clip_id: str, settings: Settings) -> str:
    """Upload an mp4 to R2 and return its public HTTPS URL.

    The R2 bucket must have public access enabled in the Cloudflare dashboard
    so Postiz (and TikTok's pull_from_url ingestor) can fetch the file.
    """
    for field, name in [
        (settings.r2_account_id, "R2_ACCOUNT_ID"),
        (settings.r2_access_key_id, "R2_ACCESS_KEY_ID"),
        (settings.r2_secret_access_key, "R2_SECRET_ACCESS_KEY"),
        (settings.r2_bucket_name, "R2_BUCKET_NAME"),
        (settings.r2_public_url, "R2_PUBLIC_URL"),
    ]:
        if not field:
            raise R2UploadError(f"Falta configurar {name}.")

    key = _object_key(clip_id)
    client = _get_client(settings)
    try:
        with open(file_path, "rb") as fh:
            client.upload_fileobj(
                fh,
                settings.r2_bucket_name,
                key,
                ExtraArgs={"ContentType": "video/mp4"},
            )
    except (ClientError, OSError) as exc:
        raise R2UploadError(f"Error subiendo clip a R2: {exc}") from exc

    public_url = settings.r2_public_url.rstrip("/")
    return f"{public_url}/{key}"


def delete_clip(clip_id: str, settings: Settings) -> None:
    """Delete the clip from R2. Best-effort: never raises."""
    if not settings.r2_account_id or not settings.r2_bucket_name:
        return

    key = _object_key(clip_id)
    client = _get_client(settings)
    try:
        client.delete_object(Bucket=settings.r2_bucket_name, Key=key)
    except ClientError:
        pass
