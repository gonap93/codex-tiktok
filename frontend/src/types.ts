export type JobStatus = "queued" | "running" | "failed" | "completed";
export type NoticeType = "info" | "error";
export type BusyAction = "" | "regenerate" | "restart" | "publish";
export type ThemeMode = "light" | "dark";

export interface ClipArtifact {
  index: number;
  title: string;
  start: number;
  end: number;
  duration: number;
  url: string;
  thumbnail_url?: string;
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
  min_clip_seconds: number;
  max_clip_seconds: number;
  subtitle_font_name: string;
  subtitle_margin_horizontal: number;
  subtitle_margin_vertical: number;
  output_width: number;
  output_height: number;
}
