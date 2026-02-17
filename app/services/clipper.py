import shutil
import subprocess
from pathlib import Path

from app.config import Settings


def escape_filter_path(path: Path) -> str:
    escaped = str(path.resolve())
    escaped = escaped.replace("\\", "\\\\")
    escaped = escaped.replace(":", r"\:")
    escaped = escaped.replace("'", r"\'")
    return escaped


def build_subtitle_filter(
    subtitles_path: Path,
    settings: Settings,
    *,
    subtitle_font_name: str | None = None,
    subtitle_margin_horizontal: int | None = None,
    subtitle_margin_vertical: int | None = None,
    output_width: int | None = None,
    output_height: int | None = None,
    flat_white: bool = False,
) -> str:
    subtitle_file = escape_filter_path(subtitles_path)
    font_file_raw = str(getattr(settings, "subtitle_font_file", "")).strip()
    fonts_dir_fragment = ""
    if font_file_raw:
        font_file_path = Path(font_file_raw).expanduser()
        if not font_file_path.is_absolute():
            font_file_path = (Path.cwd() / font_file_path).resolve()
        if font_file_path.exists():
            fonts_dir_fragment = f"fontsdir='{escape_filter_path(font_file_path.parent)}':"
    font_name_raw = subtitle_font_name or settings.subtitle_font_name
    font_name = font_name_raw.replace("'", r"\'")
    font_size = max(8, settings.subtitle_font_size)
    letter_spacing = max(0.0, float(settings.subtitle_letter_spacing))
    margin_v = max(20, subtitle_margin_vertical or settings.subtitle_margin_vertical)
    margin_h = max(20, subtitle_margin_horizontal or settings.subtitle_margin_horizontal)
    target_w = max(320, int(output_width or settings.output_width))
    target_h = max(320, int(output_height or settings.output_height))
    if flat_white:
        outline_colour = "&H00FFFFFF&"
        outline = 0
        shadow = 0
    else:
        outline_colour = "&H00101010&"
        outline = 2
        shadow = 1
    return (
        f"subtitles='{subtitle_file}':"
        f"{fonts_dir_fragment}"
        f"original_size={target_w}x{target_h}:"
        "force_style='"
        f"FontName={font_name},"
        f"FontSize={font_size},"
        f"Spacing={letter_spacing:.2f},"
        "PrimaryColour=&H00FFFFFF&,"
        f"OutlineColour={outline_colour},"
        "BackColour=&H00000000&,"
        f"BorderStyle=1,Outline={outline},Shadow={shadow},Bold=1,"
        f"Alignment=2,MarginV={margin_v},MarginL={margin_h},MarginR={margin_h}"
        "'"
    )


def render_vertical_clip(
    source_video_path: Path,
    output_clip_path: Path,
    subtitles_path: Path,
    start: float,
    end: float,
    settings: Settings,
    subtitle_font_name: str | None = None,
    subtitle_margin_horizontal: int | None = None,
    subtitle_margin_vertical: int | None = None,
    output_width: int | None = None,
    output_height: int | None = None,
) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("No se encontro ffmpeg en PATH.")

    output_clip_path.parent.mkdir(parents=True, exist_ok=True)
    target_w = max(320, int(output_width or settings.output_width))
    target_h = max(320, int(output_height or settings.output_height))
    subtitle_filter = build_subtitle_filter(
        subtitles_path,
        settings,
        subtitle_font_name=subtitle_font_name,
        subtitle_margin_horizontal=subtitle_margin_horizontal,
        subtitle_margin_vertical=subtitle_margin_vertical,
        output_width=target_w,
        output_height=target_h,
        flat_white=True,
    )

    filter_complex = (
        f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"boxblur=20:10,crop={target_w}:{target_h}[bg];"
        f"[0:v]scale={target_w}:{target_h}:force_original_aspect_ratio=decrease[fg];"
        f"[bg][fg]overlay=(W-w)/2:(H-h)/2,{subtitle_filter}[v]"
    )

    duration = max(0.1, end - start)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        str(source_video_path),
        "-filter_complex",
        filter_complex,
        "-map",
        "[v]",
        "-map",
        "0:a?",
        "-c:v",
        "libx264",
        "-preset",
        "medium",
        "-crf",
        "20",
        "-c:a",
        "aac",
        "-b:a",
        "128k",
        "-movflags",
        "+faststart",
        "-shortest",
        str(output_clip_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Error de ffmpeg: {result.stderr.strip()}")


def render_clip_thumbnail(clip_path: Path, thumbnail_path: Path) -> None:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("No se encontro ffmpeg en PATH.")
    thumbnail_path.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg",
        "-y",
        "-ss",
        "0.6",
        "-i",
        str(clip_path),
        "-frames:v",
        "1",
        "-vf",
        "scale=360:640:force_original_aspect_ratio=cover",
        str(thumbnail_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Error generando thumbnail: {result.stderr.strip()}")
