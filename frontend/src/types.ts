export type JobStatus = "queued" | "running" | "failed" | "completed";
export type NoticeType = "info" | "error";
export type BusyAction = "" | "regenerate" | "restart" | "publish";
export type ThemeMode = "light" | "dark";
export type PageType = "overview" | "clipper" | "channels" | "historial";

export type VideoLanguage = "es" | "en";

export type ContentGenre =
  | "podcast"
  | "business"
  | "entertainment"
  | "education"
  | "fitness"
  | "cooking"
  | "gaming"
  | "motivation"
  | "";

export type SubtitlePreset =
  | "karaoke"
  | "deep_diver"
  | "pod_p"
  | "neon_glow"
  | "clean_white"
  | "bold_shadow"
  | "gradient_pop"
  | "minimal"
  | "retro_vhs"
  | "comic_burst"
  | "";

export type AspectRatio = "9:16" | "1:1" | "16:9";

export interface VideoMeta {
  title: string;
  author_name: string;
  thumbnail_url: string;
}

export interface ClipArtifact {
  index: number;
  title: string;
  start: number;
  end: number;
  duration: number;
  url: string;
  thumbnail_url?: string;
  transcript_excerpt?: string;
  score: number;
  review_status: "pending" | "approved" | "rejected";
  rejection_reason: string;
  publish_status: "not_published" | "publishing" | "published" | "failed";
  publish_error?: string;
  tiktok_post_id?: string;
}

export interface JobState {
  job_id: string;
  youtube_url: string;
  generation: number;
  requested_clips_count: number;
  requested_min_clip_seconds: number;
  requested_max_clip_seconds: number;
  requested_subtitle_font_name: string;
  requested_subtitle_margin_horizontal: number;
  requested_subtitle_margin_vertical: number;
  requested_output_width: number;
  requested_output_height: number;
  requested_content_genre: string;
  requested_specific_moments_instruction: string;
  requested_ai_choose_count: boolean;
  requested_subtitles_enabled: boolean;
  requested_subtitle_preset: string;
  requested_video_language: string;
  requested_subtitle_font_size: number;
  status: JobStatus;
  progress: number;
  current_step: string;
  error: string;
  logs: string[];
  clips: ClipArtifact[];
  created_at: string;
  updated_at: string;
}

export interface FormState {
  youtube_url: string;
  clips_count: number;
  ai_choose_count: boolean;
  content_genre: ContentGenre;
  specific_moments_instruction: string;
  subtitle_font_name: string;
  subtitle_margin_horizontal: number;
  subtitle_margin_vertical: number;
  output_width: number;
  output_height: number;
  subtitles_enabled: boolean;
  subtitle_preset: SubtitlePreset;
  aspect_ratio: AspectRatio;
  video_language: VideoLanguage;
  subtitle_font_size: number;
  subtitle_position_x: number;
  subtitle_position_y: number;
}
