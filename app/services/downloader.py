import shutil
from pathlib import Path

from yt_dlp import YoutubeDL

from app.config import Settings


def _resolve_downloaded_file(output_dir: Path) -> Path:
    candidates = list(output_dir.glob("source.*"))
    candidates = [path for path in candidates if path.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if not candidates:
        raise RuntimeError("No se encontro archivo descargado. Revisa el enlace o cookies de YouTube.")
    return max(candidates, key=lambda p: p.stat().st_size)


def _prepare_cookie_file(settings: Settings, output_dir: Path) -> str | None:
    if not settings.yt_cookies_file:
        return None

    source = Path(settings.yt_cookies_file).expanduser()
    if not source.exists():
        raise RuntimeError(f"No existe YTDLP_COOKIES_FILE en la ruta: {source}")

    # yt-dlp actualiza el cookiejar; por eso usamos una copia dentro de un directorio escribible.
    target = output_dir / "_cookies.txt"
    shutil.copy2(source, target)
    try:
        target.chmod(0o600)
    except OSError:
        pass
    return str(target)


def download_youtube_video(youtube_url: str, output_dir: Path, settings: Settings) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    base_opts: dict = {
        "outtmpl": str(output_dir / "source.%(ext)s"),
        "merge_output_format": "mp4",
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "remote_components": ["ejs:github"],
        "retries": 10,
        "fragment_retries": 10,
        "concurrent_fragment_downloads": 4,
        "http_headers": {
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        },
        "extractor_args": {
            "youtube": {
                "player_client": ["android", "web", "tv_embedded"],
            }
        },
    }

    if settings.yt_proxy:
        base_opts["proxy"] = settings.yt_proxy
    if settings.yt_cookies_file:
        base_opts["cookiefile"] = _prepare_cookie_file(settings, output_dir)
    elif settings.yt_cookies_browser:
        base_opts["cookiesfrombrowser"] = (settings.yt_cookies_browser,)

    format_attempts = [
        "bestvideo[ext=mp4][height<=1080]+bestaudio[ext=m4a]/bestvideo[height<=1080]+bestaudio/best[height<=1080]",
        "bv*+ba/b",
        "best",
    ]

    last_error: Exception | None = None
    for current_format in format_attempts:
        try:
            ydl_opts = dict(base_opts)
            ydl_opts["format"] = current_format
            with YoutubeDL(ydl_opts) as ydl:
                ydl.extract_info(youtube_url, download=True)
            return _resolve_downloaded_file(output_dir)
        except Exception as exc:
            last_error = exc

    raise RuntimeError(
        "Fallo descargando YouTube tras multiples intentos de formato. "
        "Prueba actualizando cookies o usando YTDLP_COOKIES_BROWSER."
    ) from last_error
