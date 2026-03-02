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
    content_genre: str | None = Field(default=None, max_length=64)
    specific_moments_instruction: str | None = Field(default=None, max_length=1000)
    ai_choose_count: bool = Field(default=False)
    subtitles_enabled: bool = Field(default=True)
    subtitle_preset: str | None = Field(default=None, max_length=64)
    video_language: str | None = Field(default=None, max_length=5)
    subtitle_font_size: int | None = Field(default=None, ge=16, le=96)


class JobCreateResponse(BaseModel):
    job_id: str


class ClipReviewRequest(BaseModel):
    approved: bool | None = None
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
    content_genre: str | None = Field(default=None, max_length=64)
    specific_moments_instruction: str | None = Field(default=None, max_length=1000)
    ai_choose_count: bool | None = None
    video_language: str | None = Field(default=None, max_length=5)
    subtitle_font_size: int | None = Field(default=None, ge=16, le=96)


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
    content_genre: str | None = Field(default=None, max_length=64)
    specific_moments_instruction: str | None = Field(default=None, max_length=1000)
    ai_choose_count: bool | None = None
    video_language: str | None = Field(default=None, max_length=5)
    subtitle_font_size: int | None = Field(default=None, ge=16, le=96)


class PublishApprovedResponse(BaseModel):
    published_count: int
    failed_count: int


class GenerateCaptionRequest(BaseModel):
    clip_id: str
    transcript: str


class GenerateCaptionResponse(BaseModel):
    caption: str


class PublishTikTokRequest(BaseModel):
    clip_id: str
    caption: str
    title: str
    schedule_time: str | None = None


class PublishTikTokResponse(BaseModel):
    success: bool
    post_id: str = ""


class BulkClipPublishItem(BaseModel):
    clip_id: str
    caption: str
    title: str
    schedule_time: str | None = None


class BulkPublishTikTokRequest(BaseModel):
    clips: list[BulkClipPublishItem]


class BulkClipPublishResult(BaseModel):
    clip_id: str
    success: bool
    post_id: str = ""
    error: str = ""


class DirectPublishTikTokRequest(BaseModel):
    user_id: str
    video_url: str
    title: str = ""
    privacy_level: str = "SELF_ONLY"


class DirectPublishTikTokResponse(BaseModel):
    success: bool
    publish_id: str = ""
    error: str = ""


class DirectPublishStatusRequest(BaseModel):
    user_id: str
    publish_id: str


class SubtitlePreviewRequest(BaseModel):
    subtitle_font_name: str | None = Field(default=None, min_length=1, max_length=64)
    subtitle_font_size: int | None = Field(default=None, ge=16, le=96)
    subtitle_margin_horizontal: int | None = Field(default=None, ge=10, le=300)
    subtitle_margin_vertical: int | None = Field(default=None, ge=10, le=300)
    output_width: int | None = Field(default=None, ge=320, le=3840)
    output_height: int | None = Field(default=None, ge=320, le=3840)
    subtitle_text: str | None = Field(default=None, min_length=1, max_length=140)
    background_image_url: str | None = Field(default=None, max_length=1024)


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
    transcript_excerpt: str = ""
    score: float = 0.0
    virality_score: float = 0.0
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
    requested_content_genre: str = ""
    requested_specific_moments_instruction: str = ""
    requested_ai_choose_count: bool = False
    requested_subtitles_enabled: bool = True
    requested_subtitle_preset: str = ""
    requested_video_language: str = "es"
    requested_subtitle_font_size: int = 36
    status: Literal["queued", "running", "failed", "completed"] = "queued"
    progress: float = 0.0
    current_step: str = "En cola"
    error: str = ""
    logs: list[str] = Field(default_factory=list)
    clips: list[ClipArtifact] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
