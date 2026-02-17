import json
import re
from typing import Any

from openai import OpenAI

from app.config import Settings

INTRO_PATTERNS = (
    "bienvenido",
    "gracias por venir",
    "gracias por invitarme",
    "para arrancar",
    "nos gustaria preguntarte",
    "nos gustaría preguntarte",
    "contanos un poco",
    "tu historia",
    "tu trayectoria",
    "quien sos",
    "quién sos",
    "presentarte",
)

ADVICE_PATTERNS = (
    "tenes que",
    "tenés que",
    "tienes que",
    "hay que",
    "deberias",
    "deberías",
    "mi consejo",
    "te recomiendo",
    "recomiendo",
    "clave es",
    "si queres",
    "si querés",
    "si quieres",
    "para lograr",
    "para crecer",
    "para vender",
)

CONTROVERSY_PATTERNS = (
    "nadie",
    "error",
    "errores",
    "mito",
    "polem",
    "polém",
    "controvers",
    "fracaso",
    "fracas",
    "riesgo",
    "dinero",
    "imposible",
    "mentira",
    "estafa",
    "crisis",
)


def _extract_json_block(text: str) -> dict[str, Any]:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No se encontro JSON en la respuesta del modelo.")
    return json.loads(text[start : end + 1])


def _normalize_window(
    start: float,
    end: float,
    total_duration: float,
    min_seconds: float,
    max_seconds: float,
) -> tuple[float, float]:
    start = max(0.0, min(start, total_duration))
    duration = max(0.1, min(max_seconds, end - start))
    if duration < min_seconds:
        duration = min_seconds
    if start + duration > total_duration:
        start = max(0.0, total_duration - duration)
    end = min(total_duration, start + duration)
    return round(start, 3), round(end, 3)


def _segment_index_before_or_at(segments: list[dict], target_second: float) -> int:
    idx = 0
    for pos, segment in enumerate(segments):
        if float(segment["start"]) <= target_second:
            idx = pos
        else:
            break
    return idx


def _ends_idea(text: str) -> bool:
    return bool(re.search(r"[.!?]$|\\.\\.\\.$", text.strip()))


def _starts_new_idea(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    first = stripped[0]
    return first.isupper() or stripped.lower().startswith(("pero ", "ademas ", "ahora ", "por otro lado "))


def _align_to_natural_boundaries(
    segments: list[dict],
    start: float,
    end: float,
    *,
    total_duration: float,
    min_seconds: float,
    max_seconds: float,
) -> tuple[float, float]:
    if not segments:
        return _normalize_window(start, end, total_duration, min_seconds, max_seconds)

    start_idx = _segment_index_before_or_at(segments, start)
    if float(segments[start_idx]["end"]) < start and start_idx < len(segments) - 1:
        start_idx += 1

    # Move start backwards to the nearest natural break to avoid cutting an ongoing sentence.
    for _ in range(5):
        if start_idx <= 0:
            break
        prev = segments[start_idx - 1]
        cur = segments[start_idx]
        gap = float(cur["start"]) - float(prev["end"])
        candidate_start = float(prev["start"])
        if gap >= 0.35 or _ends_idea(str(prev["text"])):
            break
        if end - candidate_start > max_seconds:
            break
        start_idx -= 1

    aligned_start = float(segments[start_idx]["start"])
    end_idx = _segment_index_before_or_at(segments, end)
    end_idx = max(start_idx, end_idx)
    hard_limit = min(total_duration, aligned_start + max_seconds)

    # Extend until a natural sentence closure whenever possible.
    while end_idx < len(segments) - 1:
        cur = segments[end_idx]
        nxt = segments[end_idx + 1]
        cur_end = float(cur["end"])
        next_end = float(nxt["end"])
        current_duration = cur_end - aligned_start
        if next_end > hard_limit:
            break
        natural_close = _ends_idea(str(cur["text"])) and (
            (float(nxt["start"]) - cur_end) >= 0.18 or _starts_new_idea(str(nxt["text"]))
        )
        if current_duration >= min_seconds and natural_close:
            break
        end_idx += 1

    aligned_end = float(segments[end_idx]["end"])
    while end_idx < len(segments) - 1 and aligned_end - aligned_start < min_seconds:
        candidate_end = float(segments[end_idx + 1]["end"])
        if candidate_end > hard_limit:
            break
        end_idx += 1
        aligned_end = candidate_end

    return _normalize_window(
        aligned_start,
        aligned_end,
        total_duration,
        min_seconds,
        max_seconds,
    )


def _heuristic_moments(
    transcript: dict,
    settings: Settings,
    target_count: int,
    min_seconds: float,
    max_seconds: float,
    rejection_feedback: list[str] | None = None,
) -> list[dict]:
    segments = transcript["segments"]
    total_duration = float(segments[-1]["end"])
    keywords = {
        "secreto",
        "error",
        "nadie",
        "viral",
        "dinero",
        "controversia",
        "truco",
        "hack",
        "importante",
        "increible",
        "sorprendente",
        "atencion",
        "ojo",
        "clave",
    }

    scored: list[tuple[float, int, dict]] = []
    for index, segment in enumerate(segments):
        text = segment["text"].lower()
        words = re.findall(r"\w+", text)
        keyword_hits = sum(1 for word in words if word in keywords)
        punctuation_bonus = text.count("?") + text.count("!")
        density = min(len(words) / 40.0, 1.5)
        score = keyword_hits * 2 + punctuation_bonus * 0.4 + density + 0.5
        scored.append((score, index, segment))

    scored.sort(key=lambda item: item[0], reverse=True)
    moments: list[dict] = []
    for score, idx, segment in scored:
        if len(moments) >= target_count:
            break
        start = float(segment["start"])
        if idx > 0:
            prev = segments[idx - 1]
            if start - float(prev["end"]) < 0.7:
                start = float(prev["start"])
        duration_hint = min(max(min_seconds + 8, 22), max_seconds)
        end = start + duration_hint
        nstart, nend = _align_to_natural_boundaries(
            segments,
            start,
            end,
            total_duration=total_duration,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
        )
        if any(abs(nstart - existing["start"]) < 18 for existing in moments):
            continue
        moments.append(
            {
                "title": segment["text"][:72].strip() or "Momento destacado",
                "reason": "Segmento con alta densidad de gancho y potencial de retencion.",
                "score": round(float(score), 3),
                "start": nstart,
                "end": nend,
            }
        )

    if len(moments) < target_count:
        target_duration = min(max(min_seconds + 8, 22), max_seconds)
        stride = max(target_duration * 0.65, 20)
        cursor = 0.0
        while len(moments) < target_count and cursor + min_seconds < total_duration:
            nstart, nend = _align_to_natural_boundaries(
                segments,
                cursor,
                cursor + target_duration,
                total_duration=total_duration,
                min_seconds=min_seconds,
                max_seconds=max_seconds,
            )
            moments.append(
                {
                    "title": f"Highlight {len(moments) + 1}",
                    "reason": "Fallback temporal uniforme.",
                    "score": 1.0,
                    "start": nstart,
                    "end": nend,
                }
            )
            cursor += stride

    feedback_tokens = _feedback_tokens(rejection_feedback or [])
    ranked = _rerank_moments_for_viral_fit(moments[:target_count], segments, total_duration)
    return _sort_moments_by_feedback(ranked, feedback_tokens)


def _feedback_tokens(feedback_notes: list[str]) -> set[str]:
    tokens: set[str] = set()
    for note in feedback_notes:
        for token in re.findall(r"[a-zA-Z0-9áéíóúñüÁÉÍÓÚÑÜ]+", note.lower()):
            if len(token) >= 4:
                tokens.add(token)
    return tokens


def _moment_feedback_overlap(moment: dict, feedback_tokens: set[str]) -> int:
    if not feedback_tokens:
        return 0
    text = f"{moment.get('title', '')} {moment.get('reason', '')}".lower()
    tokens = set(re.findall(r"[a-zA-Z0-9áéíóúñüÁÉÍÓÚÑÜ]+", text))
    return len(tokens & feedback_tokens)


def _sort_moments_by_feedback(moments: list[dict], feedback_tokens: set[str]) -> list[dict]:
    if not feedback_tokens:
        return moments
    return sorted(
        moments,
        key=lambda moment: (
            _moment_feedback_overlap(moment, feedback_tokens),
            -float(moment.get("score", 0.0)),
            float(moment.get("start", 0.0)),
        ),
    )


def _build_prompt_segments(segments: list[dict], max_segments: int = 420) -> list[dict]:
    if len(segments) <= max_segments:
        return segments

    # Sample windows across the entire interview, not just the first minutes.
    window_count = 6
    window_size = max(20, max_segments // window_count)
    start_limit = max(0, len(segments) - window_size)
    picked: set[int] = set()
    for window_idx in range(window_count):
        start = int(round(window_idx * start_limit / max(1, window_count - 1)))
        end = min(len(segments), start + window_size)
        for idx in range(start, end):
            picked.add(idx)

    ordered = sorted(picked)
    if len(ordered) <= max_segments:
        return [segments[idx] for idx in ordered]

    # Uniform reduction if selected windows still exceed the token budget.
    reduced: list[dict] = []
    step = len(ordered) / max_segments
    for i in range(max_segments):
        reduced.append(segments[ordered[int(i * step)]])
    return reduced


def _window_text(segments: list[dict], start: float, end: float, max_chars: int = 900) -> str:
    parts: list[str] = []
    current_len = 0
    for segment in segments:
        seg_start = float(segment.get("start", 0.0))
        seg_end = float(segment.get("end", 0.0))
        if seg_end < start or seg_start > end:
            continue
        text = str(segment.get("text", "")).strip()
        if not text:
            continue
        parts.append(text)
        current_len += len(text) + 1
        if current_len >= max_chars:
            break
    return " ".join(parts).strip().lower()


def _count_pattern_hits(text: str, patterns: tuple[str, ...]) -> int:
    return sum(1 for pattern in patterns if pattern in text)


def _viral_fit_score(moment: dict, segments: list[dict], total_duration: float) -> float:
    model_score = float(moment.get("score", 50.0))
    start = float(moment.get("start", 0.0))
    end = float(moment.get("end", start + 1.0))
    text = _window_text(segments, start, end)

    intro_hits = _count_pattern_hits(text, INTRO_PATTERNS)
    advice_hits = _count_pattern_hits(text, ADVICE_PATTERNS)
    controversy_hits = _count_pattern_hits(text, CONTROVERSY_PATTERNS)
    question_hits = text.count("?")
    number_hits = len(re.findall(r"\b\d+(?:[.,]\d+)?\b", text))

    score = model_score
    score += advice_hits * 8.0
    score += controversy_hits * 6.0
    score += min(question_hits, 2) * 3.0
    score += min(number_hits, 2) * 2.0
    if intro_hits:
        score -= intro_hits * 14.0
    if start < min(70.0, total_duration * 0.12) and intro_hits:
        score -= 10.0
    if advice_hits == 0 and controversy_hits == 0 and question_hits == 0:
        score -= 8.0
    return score


def _rerank_moments_for_viral_fit(moments: list[dict], segments: list[dict], total_duration: float) -> list[dict]:
    if not moments:
        return moments

    scored: list[tuple[float, dict]] = []
    for moment in moments:
        viral_score = _viral_fit_score(moment, segments, total_duration)
        enriched = dict(moment)
        enriched["score"] = round(max(0.0, min(100.0, viral_score)), 3)
        scored.append((viral_score, enriched))
    scored.sort(key=lambda item: (-item[0], float(item[1].get("start", 0.0))))
    return [item[1] for item in scored]


def choose_viral_moments(
    transcript: dict,
    settings: Settings,
    target_count: int | None = None,
    min_clip_seconds: int | None = None,
    max_clip_seconds: int | None = None,
    rejection_feedback: list[str] | None = None,
) -> list[dict]:
    requested_count = max(1, int(target_count or settings.clips_count))
    min_seconds = float(min_clip_seconds or settings.min_clip_seconds)
    max_seconds = float(max_clip_seconds or settings.max_clip_seconds)
    if max_seconds < min_seconds:
        max_seconds = min_seconds
    segments = transcript["segments"]
    total_duration = float(segments[-1]["end"])
    clipped_segments = _build_prompt_segments(segments, max_segments=min(420, len(segments)))
    transcript_for_prompt = "\n".join(
        f"[{segment['start']:.2f}-{segment['end']:.2f}] {segment['text']}"
        for segment in clipped_segments
    )

    feedback_notes = rejection_feedback or []
    feedback_tokens = _feedback_tokens(feedback_notes)
    if not settings.openai_api_key:
        return _heuristic_moments(
            transcript,
            settings,
            requested_count,
            min_seconds,
            max_seconds,
            feedback_notes,
        )

    system_prompt = (
        "Eres editor experto de clips virales para TikTok e Instagram Reels. "
        "Debes identificar momentos con hook fuerte, controversia, insight accionable o emocion alta."
    )
    user_prompt = f"""
Analiza esta transcripcion con timestamps y devuelve SOLO JSON valido con el formato:
{{
  "moments": [
    {{
      "title": "string corto",
      "reason": "por que puede ser viral",
      "score": 0-100,
      "start": segundos (float),
      "end": segundos (float)
    }}
  ]
}}

Reglas:
- Devuelve exactamente {requested_count} momentos.
- Duracion recomendada entre {int(min_seconds)} y {int(max_seconds)} segundos.
- Prioriza que cada clip termine cuando cierra la idea, sin cortar explicaciones a la mitad.
- Elegi inicios en pausas naturales si es posible.
- No repetir ideas similares.
- Prioriza momentos con opinion fuerte/polemica y/o consejo accionable concreto.
- Evita intros de invitado, agradecimientos y charla de presentacion sin insight util.
- Prefiere segmentos donde haya afirmacion clara + explicacion + indicacion practica.
{"- Evita temas similares a este feedback de clips rechazados:\\n" + chr(10).join(f"  - {note}" for note in feedback_notes[:12]) if feedback_notes else ""}

Transcripcion:
{transcript_for_prompt}
"""

    try:
        client = OpenAI(api_key=settings.openai_api_key)
        completion = client.chat.completions.create(
            model=settings.openai_analysis_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )
        content = completion.choices[0].message.content or ""
        payload = _extract_json_block(content)
        raw_moments = payload.get("moments", [])
        moments: list[dict] = []
        for raw_moment in raw_moments:
            start = float(raw_moment.get("start", 0.0))
            end = float(raw_moment.get("end", start + min_seconds))
            nstart, nend = _align_to_natural_boundaries(
                segments,
                start,
                end,
                total_duration=total_duration,
                min_seconds=min_seconds,
                max_seconds=max_seconds,
            )
            moments.append(
                {
                    "title": str(raw_moment.get("title", "Momento viral")).strip(),
                    "reason": str(raw_moment.get("reason", "")).strip(),
                    "score": float(raw_moment.get("score", 50.0)),
                    "start": nstart,
                    "end": nend,
                }
            )

        if len(moments) < requested_count:
            fallback = _heuristic_moments(
                transcript,
                settings,
                requested_count,
                min_seconds,
                max_seconds,
                feedback_notes,
            )
            known_starts = {round(moment["start"], 1) for moment in moments}
            for candidate in fallback:
                if round(candidate["start"], 1) in known_starts:
                    continue
                moments.append(candidate)
                if len(moments) >= requested_count:
                    break
        ranked = _rerank_moments_for_viral_fit(moments[:requested_count], segments, total_duration)
        return _sort_moments_by_feedback(ranked, feedback_tokens)
    except Exception:
        return _heuristic_moments(
            transcript,
            settings,
            requested_count,
            min_seconds,
            max_seconds,
            feedback_notes,
        )
