from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field


class JobCreateRequest(BaseModel):
    youtube_url: str = Field(min_length=10)
    clips_count: int | None = Field(default=None, ge=1, le=12)
    min_clip_seconds: int | None = Field(default=None, ge=5, le=300)
    max_clip_seconds: int | None = Field(default=None, ge=5, le=300)
    subtitle_font_name: str | None = Field(default=None, min_length=1, max_length=64)
    subtitle_margin_horizontal: int | None = Field(default=None, ge=10, le=300)
    subtitle_margin_vertical: int | None = Field(default=None, ge=10, le=300)
    output_width: int | None = Field(default=None, ge=320, le=3840)
    output_height: int | None = Field(default=None, ge=320, le=3840)


class JobCreateResponse(BaseModel):
    job_id: str


class ClipReviewRequest(BaseModel):
    approved: bool
    rejection_reason: str | None = Field(default=None, max_length=300)


class RegenerateRequest(BaseModel):
    clips_count: int | None = Field(default=None, ge=1, le=12)
    min_clip_seconds: int | None = Field(default=None, ge=5, le=300)
    max_clip_seconds: int | None = Field(default=None, ge=5, le=300)
    subtitle_font_name: str | None = Field(default=None, min_length=1, max_length=64)
    subtitle_margin_horizontal: int | None = Field(default=None, ge=10, le=300)
    subtitle_margin_vertical: int | None = Field(default=None, ge=10, le=300)
    output_width: int | None = Field(default=None, ge=320, le=3840)
    output_height: int | None = Field(default=None, ge=320, le=3840)


class RestartRequest(BaseModel):
    clips_count: int | None = Field(default=None, ge=1, le=12)
    min_clip_seconds: int | None = Field(default=None, ge=5, le=300)
    max_clip_seconds: int | None = Field(default=None, ge=5, le=300)
    subtitle_font_name: str | None = Field(default=None, min_length=1, max_length=64)
    subtitle_margin_horizontal: int | None = Field(default=None, ge=10, le=300)
    subtitle_margin_vertical: int | None = Field(default=None, ge=10, le=300)
    output_width: int | None = Field(default=None, ge=320, le=3840)
    output_height: int | None = Field(default=None, ge=320, le=3840)
    use_cache: bool = True


class PublishApprovedResponse(BaseModel):
    published_count: int
    failed_count: int


class SubtitlePreviewRequest(BaseModel):
    subtitle_font_name: str | None = Field(default=None, min_length=1, max_length=64)
    subtitle_margin_horizontal: int | None = Field(default=None, ge=10, le=300)
    subtitle_margin_vertical: int | None = Field(default=None, ge=10, le=300)
    output_width: int | None = Field(default=None, ge=320, le=3840)
    output_height: int | None = Field(default=None, ge=320, le=3840)
    subtitle_text: str | None = Field(default=None, min_length=1, max_length=140)


class SubtitlePreviewResponse(BaseModel):
    preview_url: str


class ClipArtifact(BaseModel):
    index: int
    title: str
    start: float
    end: float
    duration: float
    url: str
    thumbnail_url: str = ""
    review_status: Literal["pending", "approved", "rejected"] = "pending"
    rejection_reason: str = ""
    publish_status: Literal["not_published", "publishing", "published", "failed"] = "not_published"
    publish_error: str = ""
    tiktok_post_id: str = ""


class JobState(BaseModel):
    job_id: str
    youtube_url: str
    generation: int = 1
    requested_clips_count: int = 4
    requested_min_clip_seconds: int = 12
    requested_max_clip_seconds: int = 95
    requested_subtitle_font_name: str = "Inter"
    requested_subtitle_margin_horizontal: int = 56
    requested_subtitle_margin_vertical: int = 46
    requested_output_width: int = 1080
    requested_output_height: int = 1920
    status: Literal["queued", "running", "failed", "completed"] = "queued"
    progress: float = 0.0
    current_step: str = "En cola"
    error: str = ""
    logs: list[str] = Field(default_factory=list)
    clips: list[ClipArtifact] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
