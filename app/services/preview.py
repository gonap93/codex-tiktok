import hashlib
import json
import shutil
import subprocess
from pathlib import Path

from app.config import Settings
from app.services.clipper import build_subtitle_filter


def _render_preview_srt(path: Path, text: str) -> None:
    payload = "1\n00:00:00,000 --> 00:00:03,000\n" + text.strip() + "\n"
    path.write_text(payload, encoding="utf-8")


def render_subtitle_preview_image(
    settings: Settings,
    *,
    subtitle_font_name: str,
    subtitle_margin_horizontal: int,
    subtitle_margin_vertical: int,
    output_width: int,
    output_height: int,
    subtitle_text: str,
) -> str:
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("No se encontro ffmpeg en PATH.")

    preview_dir = settings.static_dir / "previews"
    preview_dir.mkdir(parents=True, exist_ok=True)

    payload = {
        "font": subtitle_font_name,
        "font_file": settings.subtitle_font_file,
        "flat_white": True,
        "margin_h": subtitle_margin_horizontal,
        "margin_v": subtitle_margin_vertical,
        "width": output_width,
        "height": output_height,
        "text": subtitle_text.strip(),
        "size": settings.subtitle_font_size,
        "spacing": settings.subtitle_letter_spacing,
        "uppercase": settings.subtitle_uppercase,
    }
    digest = hashlib.sha1(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:24]
    srt_path = preview_dir / f"subtitle_preview_{digest}.srt"
    png_path = preview_dir / f"subtitle_preview_{digest}.png"

    if png_path.exists():
        return f"/static/previews/{png_path.name}"

    subtitle_line = subtitle_text.strip() or "ESTA FRASE SE CONSTRUYE EN VIVO"
    if settings.subtitle_uppercase:
        subtitle_line = subtitle_line.upper()
    _render_preview_srt(srt_path, subtitle_line)

    subtitle_filter = build_subtitle_filter(
        srt_path,
        settings,
        subtitle_font_name=subtitle_font_name,
        subtitle_margin_horizontal=subtitle_margin_horizontal,
        subtitle_margin_vertical=subtitle_margin_vertical,
        output_width=output_width,
        output_height=output_height,
        flat_white=True,
    )
    filter_chain = (
        f"color=c=#243f5b:s={output_width}x{output_height}:d=3,format=yuv420p,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=#2f5878@0.3:t=fill,"
        "drawbox=x=0:y=0:w=iw:h=ih:color=#16283f@0.22:t=fill,"
        f"{subtitle_filter}"
    )

    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        filter_chain,
        "-frames:v",
        "1",
        str(png_path),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        srt_path.unlink(missing_ok=True)
        raise RuntimeError(f"No se pudo generar preview exacto: {result.stderr.strip()}")
    return f"/static/previews/{png_path.name}"
