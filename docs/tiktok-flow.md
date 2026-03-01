# TikTok Posting Architecture

## Flow

```
Blipr app (local)
  → POST /api/publish/tiktok
      → postiz.py: upload_to_postiz()
          → POST https://postiz.blipr.co/api/public/v1/upload  (multipart mp4)
          ← {id, path}  (path = /uploads/YYYY/MM/DD/<hash>.mp4)
      → postiz.py: post_to_tiktok()
          → POST https://postiz.blipr.co/api/public/v1/posts
          ← {id, ...}

Postiz VPS (temporal worker)
  → TikTok Content Posting API (DIRECT_POST, PULL_FROM_URL)
      video_url = https://postiz.blipr.co/uploads/...
```

## Why Local Storage on Postiz

TikTok verifies domain ownership for `pull_from_url`. The domain registered in the TikTok developer portal is `postiz.blipr.co`.

If `STORAGE_PROVIDER=cloudflare` on Postiz, videos are served from `https://pub-*.r2.dev/...` — a domain TikTok has not verified — causing `url_ownership_unverified` errors.

Fix: `STORAGE_PROVIDER=local` → videos served from `postiz.blipr.co/uploads/...` (nginx `location /uploads/ { alias /uploads/; }` inside the container).

## Postiz Post Payload

```json
{
  "type": "schedule",
  "date": "2026-01-01T12:05:00Z",
  "shortLink": false,
  "tags": [],
  "posts": [{
    "integration": {"id": "<tiktok_integration_id>"},
    "value": [{"content": "<caption>", "image": [{"id": "<media_id>", "path": "<media_path>"}]}],
    "settings": {
      "__type": "tiktok",
      "title": "<title, max 90 chars>",
      "privacy_level": "SELF_ONLY",
      "content_posting_method": "DIRECT_POST",
      "duet": false,
      "stitch": true,
      "comment": true,
      "autoAddMusic": "no",
      "brand_content_toggle": false,
      "brand_organic_toggle": false,
      "video_made_with_ai": false
    }
  }]
}
```

`date` for "post now" is always 5 minutes in the future — Postiz rejects past dates.

## Known TikTok API Errors (via Postiz logs)

| TikTok error | Postiz message | Fix |
|---|---|---|
| `url_ownership_unverified` | "URL ownership not verified" | Switch Postiz `STORAGE_PROVIDER` to `local` |
| `unaudited_client_can_only_post_to_private_accounts` | "App not approved for public posting" | Submit TikTok app for audit, or use `SELF_ONLY` privacy as workaround |
| `scope_not_authorized` | "Missing required permissions" | Re-authenticate TikTok in Postiz integrations UI |
| `invalid_access_token` | "Access token invalid" | Re-authenticate TikTok in Postiz integrations UI |

## TikTok App Audit Status

The Postiz instance uses TikTok client ID `sbawhib3paxvaxudx7`. This app is **unaudited** — until it passes TikTok's review:
- Videos post with `privacy_level: "SELF_ONLY"` (private)
- User must manually change to public from TikTok app after posting

To get approved: submit at https://developers.tiktok.com → your app → Audit/Review, demonstrating `video.publish` scope usage.
