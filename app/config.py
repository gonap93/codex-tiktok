from pathlib import Path

from dotenv import load_dotenv
from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: str = Field(default="")
    openai_transcription_model: str = Field(default="whisper-1")
    openai_analysis_model: str = Field(default="gpt-4o-mini")

    clips_count: int = Field(default=4)
    max_clips_per_job: int = Field(default=12)
    min_clip_seconds: int = Field(default=12)
    max_clip_seconds: int = Field(default=95)
    subtitle_chunk_min_words: int = Field(default=2)
    subtitle_chunk_max_words: int = Field(default=6)
    subtitle_max_chars_per_line: int = Field(default=18)
    subtitle_max_lines: int = Field(default=2)
    subtitle_phrase_pause_split_seconds: float = Field(default=0.34)
    subtitle_font_name: str = Field(default="Inter")
    subtitle_font_file: str = Field(default="")
    subtitle_font_size: int = Field(default=10)
    subtitle_font_render_scale: float = Field(default=0.45)
    subtitle_letter_spacing: float = Field(default=2.2)
    subtitle_uppercase: bool = Field(default=True)
    subtitle_margin_vertical: int = Field(default=518)
    subtitle_margin_horizontal: int = Field(default=56)
    subtitle_timing_shift_seconds: float = Field(default=0.08)
    output_width: int = Field(default=1080)
    output_height: int = Field(default=1920)
    transcription_chunk_seconds: int = Field(default=480)
    transcription_chunk_overlap_seconds: float = Field(default=1.5)
    transcription_audio_bitrate: str = Field(default="48k")
    transcription_max_upload_mb: int = Field(default=24)
    transcription_entity_replacements: str = Field(default="")
    transcription_hint_terms: str = Field(default="")
    tiktok_publish_mode: str = Field(default="mock")
    postiz_base_url: str = Field(
        default="http://localhost:5000/api",
        validation_alias=AliasChoices("POSTIZ_API_URL", "POSTIZ_BASE_URL"),
    )
    postiz_api_key: str = Field(default="")
    postiz_tiktok_integration_id: str = Field(
        default="",
        validation_alias=AliasChoices("TIKTOK_INTEGRATION_ID", "POSTIZ_TIKTOK_INTEGRATION_ID"),
    )
    postiz_tiktok_privacy_status: str = Field(default="PUBLIC_TO_EVERYONE")
    postiz_tiktok_disable_duet: bool = Field(default=False)
    postiz_tiktok_disable_comment: bool = Field(default=False)
    postiz_tiktok_disable_stitch: bool = Field(default=False)
    postiz_request_timeout_seconds: float = Field(default=60.0)

    r2_account_id: str = Field(default="")
    r2_access_key_id: str = Field(default="")
    r2_secret_access_key: str = Field(default="")
    r2_bucket_name: str = Field(default="")
    r2_public_url: str = Field(default="")

    yt_cookies_file: str = Field(
        default="",
        validation_alias=AliasChoices("YTDLP_COOKIES_FILE", "YT_COOKIES_FILE"),
    )
    yt_cookies_browser: str = Field(
        default="",
        validation_alias=AliasChoices("YTDLP_COOKIES_BROWSER", "YT_COOKIES_BROWSER"),
    )
    yt_proxy: str = Field(
        default="",
        validation_alias=AliasChoices("YTDLP_PROXY", "YT_PROXY"),
    )

    jobs_dir: Path = Field(default=Path("jobs"))
    static_dir: Path = Field(default=Path("static"))
    frontend_dist_dir: Path = Field(default=Path("frontend/dist"))


def get_settings() -> Settings:
    # Reload .env on each access so runtime config changes are honored
    # without needing to restart the process.
    load_dotenv(override=True)
    settings = Settings()
    settings.jobs_dir.mkdir(parents=True, exist_ok=True)
    settings.static_dir.mkdir(parents=True, exist_ok=True)
    return settings
