# Cloudflare R2 Configuration

## Current Status

R2 code exists in `app/services/r2.py` but is **not called by `postiz.py`**. Postiz uploads directly to its own `/upload` endpoint and serves files locally. R2 may be used again in the future.

## R2 Service (`app/services/r2.py`)

Provides two functions:
- `upload_clip(file_path, clip_id, settings) -> str` — uploads mp4, returns public URL
- `delete_clip(clip_id, settings) -> None` — best-effort delete, never raises

Object key format: `clips/{clip_id.replace(":", "-")}.mp4`
e.g. clip_id `abc123:1` → `clips/abc123-1.mp4`

## Required Env Vars

```
R2_ACCOUNT_ID=<cloudflare account id>
R2_ACCESS_KEY_ID=<r2 api token key id>
R2_SECRET_ACCESS_KEY=<r2 api token secret>
R2_BUCKET_NAME=<bucket name>
R2_PUBLIC_URL=https://pub-<hash>.r2.dev  # or custom domain
```

## Bucket Requirements

- **Public access must be enabled** — TikTok needs to pull the video URL without auth
- Enable via Cloudflare dashboard: R2 → bucket → Settings → Public Access → Allow Access
- Or use a custom domain with public routing

## Endpoint

S3-compatible endpoint: `https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com`

The boto3 client is configured with:
```python
s3 = boto3.client(
    "s3",
    endpoint_url=f"https://{account_id}.r2.cloudflarestorage.com",
    aws_access_key_id=access_key_id,
    aws_secret_access_key=secret_access_key,
    region_name="auto",
)
```

## Why R2 Was Bypassed

TikTok verifies domain ownership for `pull_from_url`. The R2 CDN URL (`pub-*.r2.dev`) was not verified in the TikTok developer portal, causing `url_ownership_unverified` errors. Postiz local storage (`postiz.blipr.co/uploads/...`) is the verified domain.

If R2 is used in the future, its public domain (custom domain) must be registered in the TikTok developer portal.
