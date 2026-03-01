import re
from pathlib import Path

from app.config import Settings


def _format_srt_time(seconds: float) -> str:
    milliseconds = int(round(max(0.0, seconds) * 1000))
    hours = milliseconds // 3_600_000
    minutes = (milliseconds % 3_600_000) // 60_000
    secs = (milliseconds % 60_000) // 1_000
    millis = milliseconds % 1_000
    return f"{hours:02}:{minutes:02}:{secs:02},{millis:03}"


def _seconds_to_ms(seconds: float) -> int:
    return int(round(max(0.0, seconds) * 1000))


def _timed_words_from_segments(segments: list[dict], clip_start: float, clip_end: float) -> list[dict]:
    timed_words: list[dict] = []
    for segment in segments:
        seg_start = float(segment["start"])
        seg_end = float(segment["end"])
        text = str(segment["text"])
        words = re.findall(r"\S+", text)
        if not words:
            continue
        duration = max(seg_end - seg_start, 0.01)
        for idx, word in enumerate(words):
            word_start = seg_start + (duration * idx / len(words))
            word_end = seg_start + (duration * (idx + 1) / len(words))
            if word_end < clip_start or word_start > clip_end:
                continue
            timed_words.append(
                {
                    "word": word,
                    "start": max(word_start, clip_start) - clip_start,
                    "end": min(word_end, clip_end) - clip_start,
                }
            )
    return timed_words


def _timed_words_from_words(words: list[dict], clip_start: float, clip_end: float) -> list[dict]:
    timed_words: list[dict] = []
    for item in words:
        text = str(item.get("word", "")).strip()
        if not text:
            continue
        word_start = float(item.get("start", 0.0))
        word_end = float(item.get("end", word_start + 0.05))
        if word_end < clip_start or word_start > clip_end:
            continue
        timed_words.append(
            {
                "word": text,
                "start": max(word_start, clip_start) - clip_start,
                "end": min(word_end, clip_end) - clip_start,
            }
        )
    return timed_words


def _synthetic_timed_words_from_clip_text(segments: list[dict], clip_start: float, clip_end: float) -> list[dict]:
    clip_duration = max(0.1, clip_end - clip_start)
    joined = " ".join(
        str(segment.get("text", "")).strip()
        for segment in segments
        if float(segment.get("end", 0.0)) >= clip_start and float(segment.get("start", 0.0)) <= clip_end
    ).strip()
    if not joined:
        return []
    words = re.findall(r"\S+", joined)[:180]
    if not words:
        return []
    slot = max(0.09, clip_duration / max(1, len(words)))
    timed_words: list[dict] = []
    for idx, word in enumerate(words):
        start = min(clip_duration - 0.03, idx * slot)
        end = min(clip_duration, start + max(0.07, slot * 0.92))
        timed_words.append({"word": word, "start": start, "end": max(end, start + 0.07)})
    return timed_words


def _sanitize_timed_words(timed_words: list[dict], clip_duration: float) -> list[dict]:
    cleaned: list[dict] = []
    for item in timed_words:
        text = str(item.get("word", "")).strip()
        if not text:
            continue
        start = float(item.get("start", 0.0))
        end = float(item.get("end", start + 0.05))
        start = max(0.0, min(start, clip_duration - 0.02))
        end = max(start + 0.05, min(end, clip_duration))
        cleaned.append({"word": text, "start": start, "end": end})
    cleaned.sort(key=lambda item: (float(item["start"]), float(item["end"])))
    return cleaned


def _timed_word_coverage_seconds(timed_words: list[dict]) -> float:
    if not timed_words:
        return 0.0
    coverage = 0.0
    for item in timed_words:
        coverage += max(0.0, float(item["end"]) - float(item["start"]))
    return coverage


def _wrap_words(words: list[str], max_chars_per_line: int) -> list[str]:
    if not words:
        return []
    if max_chars_per_line <= 8:
        return [" ".join(words).strip()]

    lines: list[str] = []
    current: list[str] = []
    current_len = 0
    for word in words:
        projected = len(word) if not current else current_len + 1 + len(word)
        if current and projected > max_chars_per_line:
            lines.append(" ".join(current))
            current = [word]
            current_len = len(word)
        else:
            current.append(word)
            current_len = projected
    if current:
        lines.append(" ".join(current))
    return lines


def _wrap_centered_text(text: str, max_chars_per_line: int, max_lines: int) -> str:
    words = text.split()
    if not words:
        return text

    if max_lines <= 0:
        return "\n".join(_wrap_words(words, max_chars_per_line))

    start_idx = 0
    lines = _wrap_words(words, max_chars_per_line)
    while len(lines) > max_lines and start_idx < len(words) - 1:
        start_idx += 1
        lines = _wrap_words(words[start_idx:], max_chars_per_line)
    return "\n".join(lines)


_PUNCTUATION_BREAK = frozenset(".?!,")
_PAUSE_BREAK_SECONDS = 0.4


def _word_ends_phrase(word: str) -> bool:
    """Return True if the word ends with a phrase-boundary punctuation character."""
    stripped = word.rstrip()
    return bool(stripped) and stripped[-1] in _PUNCTUATION_BREAK


def _select_phrase_chunk_size(
    timed_words: list[dict],
    cursor: int,
    chunk_min: int,
    chunk_max: int,
    *,
    max_chars_per_line: int,
    max_lines: int,
    subtitle_uppercase: bool,
    pause_split_seconds: float,
) -> int:
    available = len(timed_words) - cursor
    if available <= 0:
        return 0

    # Hard cap: never exceed chunk_max (3) words per subtitle line.
    max_size = min(chunk_max, available)
    if max_size == 1:
        return 1

    min_size = max(1, min(chunk_min, max_size))
    hard_pause_for_single = max(pause_split_seconds * 2.0, pause_split_seconds + 0.28)
    # Use the larger of the config pause threshold and the hard-coded 0.4s boundary.
    effective_pause_split = max(pause_split_seconds, _PAUSE_BREAK_SECONDS)
    best_fit = 0
    punctuation_choice = 0
    pause_choice = 0

    # Select phrase size by visual fit + natural pauses + punctuation between words.
    for size in range(1, max_size + 1):
        phrase = " ".join(item["word"] for item in timed_words[cursor : cursor + size]).strip()
        if subtitle_uppercase:
            phrase = phrase.upper()
        words_in_phrase = phrase.split()

        # Hard character cap per line: if a single word already exceeds the limit,
        # accept it as a 1-word line. If adding another word would exceed the cap
        # and we already have min_size words, stop here.
        phrase_chars = len(phrase)
        if size > 1 and phrase_chars > max_chars_per_line and best_fit >= 1:
            break

        wrapped = _wrap_words(words_in_phrase, max_chars_per_line)
        if max_lines > 0 and len(wrapped) > max_lines:
            break
        best_fit = size

        # Check for a punctuation boundary at the end of this word.
        current_word = str(timed_words[cursor + size - 1].get("word", ""))
        if size >= min_size and _word_ends_phrase(current_word):
            punctuation_choice = size
            break

        next_index = cursor + size
        if next_index >= len(timed_words):
            pause_choice = size
            continue
        gap_after = float(timed_words[next_index]["start"]) - float(timed_words[next_index - 1]["end"])
        if size == 1 and gap_after >= hard_pause_for_single:
            return 1
        if size >= min_size and gap_after >= effective_pause_split:
            pause_choice = size
            break

    if best_fit == 0:
        return 0
    # Punctuation break takes highest priority.
    if punctuation_choice:
        return punctuation_choice
    if pause_choice:
        return pause_choice
    if best_fit <= min_size:
        return best_fit

    # If there is no clear pause, choose the strongest local gap in [min_size, best_fit]
    # to keep phrase lengths variable and more natural.
    best_gap = -1.0
    best_gap_size = min_size
    for size in range(min_size, best_fit + 1):
        next_index = cursor + size
        if next_index >= len(timed_words):
            return size
        gap_after = float(timed_words[next_index]["start"]) - float(timed_words[next_index - 1]["end"])
        if gap_after > best_gap:
            best_gap = gap_after
            best_gap_size = size
    return best_gap_size


def build_srt_for_clip(
    segments: list[dict],
    clip_start: float,
    clip_end: float,
    output_srt_path: Path,
    settings: Settings,
    words: list[dict] | None = None,
) -> None:
    clip_duration = max(0.1, clip_end - clip_start)
    word_based = _sanitize_timed_words(_timed_words_from_words(words or [], clip_start, clip_end), clip_duration)
    segment_based = _sanitize_timed_words(_timed_words_from_segments(segments, clip_start, clip_end), clip_duration)
    timed_words = word_based
    min_coverage = min(1.6, clip_duration * 0.22)
    if len(word_based) < 6 or _timed_word_coverage_seconds(word_based) < min_coverage:
        timed_words = segment_based or word_based
    if not timed_words:
        timed_words = _sanitize_timed_words(
            _synthetic_timed_words_from_clip_text(segments, clip_start, clip_end),
            clip_duration,
        )
    if not timed_words:
        output_srt_path.write_text("", encoding="utf-8")
        return

    chunk_min = max(1, settings.subtitle_chunk_min_words)
    chunk_max = max(chunk_min, settings.subtitle_chunk_max_words)
    max_lines = max(1, int(getattr(settings, "subtitle_max_lines", 2)))
    timing_shift = float(settings.subtitle_timing_shift_seconds)
    pause_split_seconds = max(0.12, float(getattr(settings, "subtitle_phrase_pause_split_seconds", 0.34)))
    clip_duration_ms = max(1, _seconds_to_ms(clip_duration))
    min_cue_ms = 120

    lines: list[str] = []
    subtitle_index = 1
    cursor = 0
    last_cue_end_ms = 0
    while cursor < len(timed_words):
        chunk_size = _select_phrase_chunk_size(
            timed_words,
            cursor,
            chunk_min,
            chunk_max,
            max_chars_per_line=settings.subtitle_max_chars_per_line,
            max_lines=max_lines,
            subtitle_uppercase=settings.subtitle_uppercase,
            pause_split_seconds=pause_split_seconds,
        )
        chunk_size = min(chunk_size, chunk_max)
        if chunk_size <= 0:
            break
        chunk = timed_words[cursor : cursor + chunk_size]
        if not chunk:
            break

        start = max(0.0, min(float(chunk[0]["start"]) + timing_shift, clip_duration - 0.02))
        end = max(start + 0.08, min(float(chunk[-1]["end"]) + timing_shift, clip_duration))
        next_start_ms: int | None = None
        next_index = cursor + chunk_size
        if next_index < len(timed_words):
            next_start = float(timed_words[next_index]["start"]) + timing_shift
            next_start_ms = _seconds_to_ms(max(0.0, min(next_start, clip_duration)))
            end = max(end, min(next_start, end + 0.22))

        start_ms = _seconds_to_ms(start)
        end_ms = _seconds_to_ms(end)
        start_ms = max(start_ms, last_cue_end_ms)
        if start_ms >= clip_duration_ms:
            break
        if next_start_ms is not None:
            end_ms = min(end_ms, next_start_ms)
        end_ms = max(end_ms, start_ms + min_cue_ms)
        if next_start_ms is not None:
            end_ms = min(end_ms, next_start_ms)
        end_ms = min(end_ms, clip_duration_ms)
        if end_ms <= start_ms:
            cursor += chunk_size
            continue

        visible_words = " ".join(item["word"] for item in chunk).strip()
        if settings.subtitle_uppercase:
            visible_words = visible_words.upper()
        text = _wrap_centered_text(visible_words, settings.subtitle_max_chars_per_line, max_lines)
        lines.append(str(subtitle_index))
        lines.append(f"{_format_srt_time(start_ms / 1000)} --> {_format_srt_time(end_ms / 1000)}")
        lines.append(text)
        lines.append("")
        subtitle_index += 1
        last_cue_end_ms = end_ms

        cursor += chunk_size

    output_srt_path.write_text("\n".join(lines), encoding="utf-8")
