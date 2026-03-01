import json
import logging
import re
from typing import Any

from openai import OpenAI

from app.config import Settings

log = logging.getLogger(__name__)

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

GENRE_VIRALITY_SIGNALS_ES: dict[str, str] = {
    "podcast": (
        "Senales de viralidad para podcast/entrevista: opiniones controversiales o sorprendentes, "
        "quiebres emocionales o risas intensas, frases citables, pivotes inesperados de tema, "
        "silencios incomodos seguidos de una revelacion, momentos donde el invitado dice algo que 'no deberia haber dicho'."
    ),
    "gaming": (
        "Senales de viralidad para gaming: jugadas clutch, momentos de rage/furia, victorias o derrotas "
        "inesperadas, jump scares, bugs o glitches graciosos, reacciones del streamer al chat, "
        "records, momentos de caos o coordinacion de squad."
    ),
    "education": (
        "Senales de viralidad para educacion/tutorial: momentos 'mind-blown', datos contraintuitivos, "
        "mitos o conceptos erroneos desmentidos, demostraciones antes/despues, revelaciones de 'no sabia eso', "
        "segmentos densos en valor practico condensado."
    ),
    "fitness": (
        "Senales de viralidad para deportes/fitness: hazanas fisicas impresionantes, highlights de competencia, "
        "momentos underdog, transformaciones visibles, demostraciones de tecnica con resultados claros, "
        "discursos motivacionales, records personales."
    ),
    "entertainment": (
        "Senales de viralidad para entretenimiento/vlogs: reacciones genuinas y emocionales, percances o "
        "errores graciosos, resultados sorprendentes, actividades de alta energia, dinamicas de relacion, "
        "reveals de viaje, highlights de 'un dia en la vida'."
    ),
    "business": (
        "Senales de viralidad para negocios: insights financieros contraintuitivos, fracasos reveladores, "
        "estrategias accionables concretas, numeros o estadisticas impactantes, predicciones audaces, "
        "momentos de 'esto me hubiera gustado saber antes'."
    ),
    "cooking": (
        "Senales de viralidad para cocina: tecnicas sorprendentes o poco conocidas, errores divertidos en la cocina, "
        "transformaciones visuales impactantes de ingredientes, trucos rapidos y efectivos, "
        "reacciones genuinas al probar el resultado final."
    ),
    "motivation": (
        "Senales de viralidad para motivacion: historias de superacion personal, frases poderosas y citables, "
        "momentos de vulnerabilidad genuina, revelaciones personales impactantes, "
        "llamados a la accion emocionalmente cargados, quiebres de voz."
    ),
}

GENRE_VIRALITY_SIGNALS_EN: dict[str, str] = {
    "podcast": (
        "Viral signals for podcast/interview: controversial or surprising opinions, emotional breakdowns or laughs, "
        "quotable one-liners, unexpected topic pivots, awkward silences followed by a reveal, "
        "moments where the guest says something they 'shouldn't have'."
    ),
    "gaming": (
        "Viral signals for gaming: clutch plays, rage moments, unexpected wins/losses, jump scares, "
        "funny glitches, streamer reactions to chat, record-breaking moments, "
        "squad moments of chaos or coordination."
    ),
    "education": (
        "Viral signals for education/tutorial: 'mind blown' moments, counterintuitive facts, "
        "common misconceptions being debunked, before/after demonstrations, 'I didn't know that' revelations, "
        "condensed value-dense segments."
    ),
    "fitness": (
        "Viral signals for sports/fitness: impressive physical feats, competition highlights, "
        "underdog moments, transformations, technique demonstrations with visible results, "
        "motivational speeches, personal records."
    ),
    "entertainment": (
        "Viral signals for entertainment/vlogs: genuine emotional reactions, funny mishaps, "
        "surprising outcomes, high-energy activities, relationship dynamics, travel reveals, "
        "'day in the life' highlights."
    ),
    "business": (
        "Viral signals for business: counterintuitive financial insights, revealing failures, "
        "actionable strategies, shocking numbers or statistics, bold predictions, "
        "'I wish I had known this earlier' moments."
    ),
    "cooking": (
        "Viral signals for cooking: surprising or little-known techniques, funny kitchen mistakes, "
        "visually stunning ingredient transformations, quick effective tricks, "
        "genuine reactions when tasting the final result."
    ),
    "motivation": (
        "Viral signals for motivation: stories of overcoming adversity, powerful quotable phrases, "
        "genuine moments of vulnerability, impactful personal revelations, "
        "emotionally charged calls to action, voice-cracking moments."
    ),
}

LANGUAGE_PROMPT_ES = (
    "El video esta en espanol. Al analizar el transcript, ten en cuenta expresiones coloquiales, "
    "modismos latinoamericanos/espanoles, y el ritmo natural del habla en espanol. "
    "Los titulos de los clips deben generarse en espanol. "
    "Los momentos virales en contenido hispanohablante suelen incluir: reacciones exageradas, "
    "drops emocionales, revelaciones inesperadas, humor situacional, y frases de alto impacto cultural."
)

LANGUAGE_PROMPT_EN = (
    "The video is in English. When analyzing the transcript, account for colloquialisms, "
    "cultural references, and natural English speech rhythm. "
    "Clip titles must be generated in English. "
    "Viral moments in English-speaking content typically include: emotional reactions, "
    "plot twists, surprising reveals, comedic timing, quotable one-liners, and high-energy moments."
)

MIN_NATURAL_MAX_CLIP_SECONDS = 90.0
END_BUFFER_SECONDS = 1.3
SENTENCE_BREAK_GAP_SECONDS = 0.45
# Minimum clip target before the extension loop is allowed to stop at a natural break.
# Prevents short AI suggestions (~24 s) from stopping at the first sentence boundary.
MIN_CLIP_TARGET_SECONDS = 35.0

# ---------------------------------------------------------------------------
# Virality scoring signal tables
# ---------------------------------------------------------------------------

# Common stopwords excluded from information-density calculation (Spanish + English).
_STOPWORDS: frozenset[str] = frozenset(
    {
        # Spanish
        "de", "la", "el", "en", "y", "a", "que", "es", "se", "no", "un", "una",
        "los", "las", "del", "al", "lo", "por", "con", "su", "para", "como",
        "mas", "pero", "sus", "le", "ya", "o", "fue", "hay", "si",
        "porque", "este", "esta", "estos", "estas", "ese", "esa", "esos", "esas",
        "muy", "tan", "tambien", "me", "te", "nos", "les", "mi",
        "son", "ha", "han", "era", "ser", "estar", "sido", "tiene", "tienen",
        "puede", "pueden", "hacer", "hace", "hizo", "sobre", "desde", "hasta",
        "cuando", "donde", "quien", "todo", "todos", "toda", "todas",
        "otro", "otra", "otros", "otras", "mismo", "misma",
        # English
        "the", "an", "and", "or", "but", "in", "on", "at", "to", "for",
        "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "it", "its", "this", "that", "these", "those",
        "he", "she", "we", "they", "my", "your", "his", "her",
        "our", "their", "what", "which", "who", "how", "when", "where", "why",
        "so", "if", "as", "not", "just", "about", "also", "then", "than",
        "up", "can", "there", "all", "more", "some", "into", "out", "like",
        "get", "got", "one", "two", "three",
    }
)

# Emotional / surprise / high-engagement words (Spanish + English).
# Accent-stripped lowercase forms so matching works on normalized Whisper output.
_EMOTION_WORDS: tuple[str, ...] = (
    # Spanish
    "increible", "jamas", "nunca", "secreto", "error",
    "sorpresa", "impresionante", "brutal", "clave", "revelo",
    "descubri", "cambio", "importante", "unico",
    "mejor", "peor", "primera vez", "nunca antes", "revelacion",
    "explosivo", "impactante", "radical", "tremendo",
    "definitivamente", "totalmente",
    # English
    "never", "secret", "incredible", "amazing", "shocking", "revealed",
    "discovered", "changed", "important", "unique", "best", "worst",
    "first time", "never before", "explosive", "massive", "insane", "unreal",
    "mindblowing", "unbelievable", "extraordinary", "critical",
)

# Strong opinion / authenticity markers (Spanish + English).
_OPINION_MARKERS: tuple[str, ...] = (
    # Spanish
    "yo creo", "la verdad", "honestamente", "te digo que", "lo que nadie",
    "el problema es", "francamente", "siendo honesto", "en realidad",
    "lo que pasa", "la realidad es", "mi opinion",
    "sere honesto", "debo admitir", "tengo que decir",
    # English
    "i believe", "the truth is", "honestly", "let me tell you", "nobody talks",
    "the problem is", "frankly", "to be honest", "the reality is",
    "what actually", "in my opinion", "i have to say", "i must admit",
    "real talk", "ill be honest",
)

# Storytelling peak / narrative transition markers (Spanish + English).
_STORY_PEAKS: tuple[str, ...] = (
    # Spanish
    "entonces", "de repente", "fue cuando", "lo que paso",
    "en ese momento", "y resulta", "de pronto", "ahi fue",
    "y justo", "fue entonces", "en ese instante", "fue ahi",
    # English
    "and then", "suddenly", "what happened", "at that moment",
    "and it turns out", "all of a sudden", "right then", "just then",
    "that was when", "at that point",
)

# Call-to-action / direct address phrases (multi-word; single tokens handled separately).
_CTA_PHRASES: tuple[str, ...] = (
    # Spanish
    "imaginate", "pensalo", "imagina que", "piensa en",
    "fijate que", "considera que",
    # English
    "imagine that", "think about", "consider this", "remember that",
    "look at this", "notice how", "listen to", "ask yourself",
)


def _strip_accents_lower(text: str) -> str:
    """Return *text* lowercased with common Spanish accent chars replaced by
    their unaccented ASCII equivalents, so signal matching works regardless
    of whether Whisper preserved accents in the output."""
    table = str.maketrans(
        "\u00e1\u00e9\u00ed\u00f3\u00fa\u00fc\u00c1\u00c9\u00cd\u00d3\u00da\u00dc\u00f1\u00d1",
        "aeiouuAEIOUUnN",
    )
    return text.lower().translate(table)


def _compute_virality_score(text: str) -> float:
    """Return a 0.0–1.0 virality score for a transcript text segment.

    Each signal is individually capped so no single dimension dominates:

    - Question hooks (``?`` / ``\\u00bf`` near start):  max +0.15
    - Emotional / surprise language:                    max +0.25
    - Strong opinion markers:                           +0.10
    - Storytelling peak / narrative transitions:        +0.08
    - Call-to-action / direct address:                  +0.05
    - Information density (unique meaningful words):    max +0.15
    - Sentence count (prefer 3-6 complete sentences):   max +0.10
    """
    normalized = _strip_accents_lower(text)
    words = re.findall(r"\w+", normalized)
    total_words = len(words)

    score = 0.0

    # Question hooks: bonus is higher when the question opens the clip.
    question_count = text.count("?") + text.count("\u00bf")
    if question_count:
        first_120 = text[:120]
        if "?" in first_120 or "\u00bf" in first_120:
            score += 0.15
        else:
            score += 0.10

    # Emotional / surprise language.
    emotion_hits = sum(1 for phrase in _EMOTION_WORDS if phrase in normalized)
    score += min(emotion_hits * 0.10, 0.25)

    # Strong opinion markers.
    if any(marker in normalized for marker in _OPINION_MARKERS):
        score += 0.10

    # Storytelling peaks.
    if any(peak in normalized for peak in _STORY_PEAKS):
        score += 0.08

    # Call-to-action / direct address.
    cta_hit = any(phrase in normalized for phrase in _CTA_PHRASES)
    if not cta_hit:
        direct_tokens = {"ustedes", "tu", "you"}
        cta_hit = bool(direct_tokens & set(words))
    if cta_hit:
        score += 0.05

    # Information density: unique meaningful words / total words.
    if total_words > 0:
        meaningful = [w for w in words if w not in _STOPWORDS and len(w) > 2]
        unique_meaningful = len(set(meaningful))
        density_ratio = unique_meaningful / total_words
        score += min(density_ratio * 0.27, 0.15)

    # Sentence count: prefer 3-6 complete sentences in the segment.
    sentence_ends = len(re.findall(r"[.!?]", text))
    if 3 <= sentence_ends <= 6:
        score += 0.10
    elif sentence_ends in (2, 7):
        score += 0.05
    elif sentence_ends == 1:
        score += 0.02

    return round(min(score, 1.0), 4)


def _apply_score_based_duration_cap(
    start: float,
    end: float,
    virality_score: float,
    max_clip_seconds: float,
) -> tuple[float, float]:
    """Cap clip duration based on virality score tiers.

    Applied AFTER boundary alignment as an additional trim pass.
    Start time is never modified; only *end* may be reduced.

    Tiers:
    - High-scoring (> 0.65):    full ``max_clip_seconds``
    - Medium-scoring (0.40-0.65): 75% of ``max_clip_seconds``
    - Low-scoring (< 0.40):     55% of ``max_clip_seconds``
    """
    if virality_score > 0.65:
        effective_cap = max_clip_seconds
    elif virality_score >= 0.40:
        effective_cap = max_clip_seconds * 0.75
    else:
        effective_cap = max_clip_seconds * 0.55

    current_duration = end - start
    if current_duration > effective_cap:
        end = start + effective_cap

    return start, round(end, 3)


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


def _starts_clean_phrase(segments: list[dict], idx: int) -> bool:
    """Check whether the segment at *idx* is a good clip start point (beginning of a phrase)."""
    if idx == 0:
        return True
    text = str(segments[idx].get("text", "")).strip()
    prev = segments[idx - 1]
    gap = float(segments[idx]["start"]) - float(prev["end"])
    return gap >= 0.35 or _starts_new_idea(text) or _ends_idea(str(prev.get("text", "")))


_SENTENCE_END_RE = re.compile(r"[.!?]$|\.\.\.$")
_WORD_BOUNDARY_GAP = 0.5  # seconds — pause gap treated as a sentence boundary


def _word_ends_sentence(word_text: str) -> bool:
    """Return True if *word_text* ends with sentence-terminal punctuation."""
    return bool(_SENTENCE_END_RE.search(word_text.rstrip()))


def _find_sentence_start(
    words: list[dict],
    target_time: float,
    max_lookback: float = 3.0,
) -> float:
    """Return the start time of the nearest sentence boundary before *target_time*.

    Walk backward from *target_time* looking for a word whose predecessor ends a
    sentence (punctuation) or is separated by a pause >= 0.5 s.  If a boundary is
    found within *max_lookback* seconds, return that word's start time.

    If no boundary is found looking backward, walk forward up to 2.0 s from
    *target_time* and return the first sentence-start found there.

    Falls back to *target_time* unchanged when no boundary can be located.
    """
    if not words:
        return target_time

    # Find the index of the first word at or after target_time.
    anchor_idx = 0
    for idx, word in enumerate(words):
        if float(word["start"]) <= target_time:
            anchor_idx = idx
        else:
            break

    # Walk backward — look for a word that starts a new sentence (its predecessor
    # ends a sentence, or there is a pause gap before it).
    earliest_allowed = target_time - max_lookback
    for idx in range(anchor_idx, 0, -1):
        word_start = float(words[idx]["start"])
        if word_start < earliest_allowed:
            break
        prev_word = words[idx - 1]
        gap = word_start - float(prev_word["end"])
        if _word_ends_sentence(str(prev_word["word"])) or gap >= _WORD_BOUNDARY_GAP:
            return word_start

    # If idx reached 0 the very first word is always a clean start.
    if anchor_idx == 0 or (anchor_idx > 0 and float(words[0]["start"]) >= earliest_allowed):
        return float(words[0]["start"])

    # Walk forward — accept the next sentence-start up to 2.0 s ahead.
    forward_limit = target_time + 2.0
    for idx in range(1, len(words)):
        word_start = float(words[idx]["start"])
        if word_start > forward_limit:
            break
        if word_start < target_time:
            continue
        prev_word = words[idx - 1]
        gap = word_start - float(prev_word["end"])
        if _word_ends_sentence(str(prev_word["word"])) or gap >= _WORD_BOUNDARY_GAP:
            return word_start

    return target_time


def _find_sentence_end(
    words: list[dict],
    target_time: float,
    max_lookahead: float = 3.0,
) -> float:
    """Return the end time of the nearest sentence boundary after *target_time*.

    Walk forward from *target_time* looking for a word that ends a sentence
    (punctuation) or is followed by a pause >= 0.5 s.  If found within
    *max_lookahead* seconds, return the end time of that word.

    If no boundary is found looking forward, walk backward up to 2.0 s from
    *target_time* and return the end time of the last sentence-ending word found.

    Falls back to *target_time* unchanged when no boundary can be located.
    """
    if not words:
        return target_time

    latest_allowed = target_time + max_lookahead

    # Find the first word whose end is at or past target_time.
    start_idx = 0
    for idx, word in enumerate(words):
        if float(word["end"]) < target_time:
            start_idx = idx
        else:
            break

    # Walk forward — look for a sentence-ending word within max_lookahead.
    for idx in range(start_idx, len(words)):
        word_end = float(words[idx]["end"])
        if word_end > latest_allowed:
            break
        word_start = float(words[idx]["start"])
        if word_start < target_time:
            continue
        next_gap_is_pause = (
            idx < len(words) - 1
            and float(words[idx + 1]["start"]) - word_end >= _WORD_BOUNDARY_GAP
        )
        if _word_ends_sentence(str(words[idx]["word"])) or next_gap_is_pause:
            return word_end

    # Walk backward — accept a sentence end up to 2.0 s before target_time.
    backward_limit = target_time - 2.0
    for idx in range(len(words) - 1, -1, -1):
        word_end = float(words[idx]["end"])
        if word_end > target_time:
            continue
        if word_end < backward_limit:
            break
        next_gap_is_pause = (
            idx < len(words) - 1
            and float(words[idx + 1]["start"]) - word_end >= _WORD_BOUNDARY_GAP
        )
        if _word_ends_sentence(str(words[idx]["word"])) or next_gap_is_pause:
            return word_end

    return target_time


def _align_to_natural_boundaries(
    segments: list[dict],
    start: float,
    end: float,
    *,
    total_duration: float,
    min_seconds: float,
    max_seconds: float,
    words: list[dict] | None = None,
    clip_index: int = 0,
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

    # Ensure we actually land on a segment that starts a clean phrase.
    # If the current start_idx is mid-sentence, walk forward up to 3 segments.
    if not _starts_clean_phrase(segments, start_idx):
        best_idx = start_idx
        best_gap = 0.0
        for fwd in range(1, 4):
            candidate_idx = start_idx + fwd
            if candidate_idx >= len(segments):
                break
            if float(segments[candidate_idx]["start"]) - float(segments[start_idx]["start"]) > max_seconds * 0.3:
                break
            if _starts_clean_phrase(segments, candidate_idx):
                start_idx = candidate_idx
                break
            # Track the candidate with the largest preceding gap as fallback.
            prev_seg = segments[candidate_idx - 1]
            gap = float(segments[candidate_idx]["start"]) - float(prev_seg["end"])
            if gap > best_gap:
                best_gap = gap
                best_idx = candidate_idx
        else:
            # No clean phrase found — use the one with the biggest gap.
            if best_idx != start_idx:
                start_idx = best_idx

    aligned_start = float(segments[start_idx]["start"])
    # Enforce a minimum target so clips extend to a meaningful length even when
    # the AI suggests a short window (e.g. 24 s).  The extension loops below
    # respect this target before stopping at natural breaks.
    effective_target = max(MIN_CLIP_TARGET_SECONDS, end - aligned_start)
    requested_end = max(aligned_start + effective_target, end)
    end_idx = _segment_index_before_or_at(segments, requested_end)
    end_idx = max(start_idx, end_idx)
    effective_max_seconds = max(float(max_seconds), MIN_NATURAL_MAX_CLIP_SECONDS)
    hard_limit = min(total_duration, aligned_start + effective_max_seconds)
    original_span = max(MIN_CLIP_TARGET_SECONDS, end - start)

    log.info(
        "[clip %d] INPUT start=%.1f end=%.1f | aligned_start=%.1f requested_end=%.1f "
        "original_span=%.1f hard_limit=%.1f total_dur=%.1f",
        clip_index, start, end, aligned_start, requested_end,
        original_span, hard_limit, total_duration,
    )

    # Extend until the clip reaches a natural closure after the requested endpoint.
    while end_idx < len(segments) - 1:
        cur = segments[end_idx]
        nxt = segments[end_idx + 1]
        cur_end = float(cur["end"])
        next_end = float(nxt["end"])
        if next_end > hard_limit:
            break

        current_duration = cur_end - aligned_start
        gap = float(nxt["start"]) - cur_end
        reached_requested_end = cur_end >= requested_end
        natural_close = _ends_idea(str(cur["text"])) and (
            gap >= 0.18 or _starts_new_idea(str(nxt["text"]))
        )
        if reached_requested_end and current_duration >= original_span and natural_close:
            break
        if reached_requested_end and current_duration >= original_span and gap >= SENTENCE_BREAK_GAP_SECONDS:
            break
        end_idx += 1

    # If still mid-sentence, keep extending until a sentence end or a long pause.
    # We require at least original_span before stopping, and for short pauses we
    # also require sentence-terminal punctuation so we don't cut mid-phrase.
    while end_idx < len(segments) - 1:
        cur = segments[end_idx]
        nxt = segments[end_idx + 1]
        cur_end = float(cur["end"])
        next_end = float(nxt["end"])
        if next_end > hard_limit:
            break
        cur_text = str(cur["text"])
        current_duration = cur_end - aligned_start
        if _ends_idea(cur_text) and current_duration >= original_span:
            break
        gap = float(nxt["start"]) - cur_end
        # Stop on a hard pause (>= 0.9 s) once we've hit minimum target — speaker clearly done.
        if gap >= 0.9 and current_duration >= original_span:
            break
        end_idx += 1

    aligned_end = float(segments[end_idx]["end"])

    # Always leave a small tail after the punchline/resolution.
    aligned_end = min(hard_limit, aligned_end + END_BUFFER_SECONDS)

    while end_idx < len(segments) - 1 and aligned_end - aligned_start < min_seconds:
        candidate_end = float(segments[end_idx + 1]["end"])
        if candidate_end > hard_limit:
            break
        end_idx += 1
        aligned_end = candidate_end

    # --- Word-level boundary refinement (on top of segment-level logic) ---
    if words:
        # Refine start: find nearest sentence start within ±3 s of aligned_start.
        refined_start = _find_sentence_start(words, aligned_start)
        # Only accept the refinement when it does not push the clip beyond max_seconds.
        if refined_start <= aligned_start and aligned_end - refined_start <= effective_max_seconds:
            aligned_start = refined_start

        # Refine end: find nearest sentence end within +3 s / -2 s of aligned_end.
        refined_end = _find_sentence_end(words, aligned_end - END_BUFFER_SECONDS)
        # Accept refinement only when clip remains within bounds and is long enough.
        if (
            refined_end >= aligned_end - END_BUFFER_SECONDS
            and refined_end <= hard_limit
            and refined_end - aligned_start >= original_span
        ):
            # Re-apply the tail buffer on top of the word-level sentence end.
            aligned_end = min(hard_limit, refined_end + END_BUFFER_SECONDS)

    log.info(
        "[clip %d] OUTPUT aligned_start=%.1f aligned_end=%.1f duration=%.1f",
        clip_index, aligned_start, aligned_end, aligned_end - aligned_start,
    )

    # Diagnostic: log the first words of the clip so callers can verify start point.
    if words and log.isEnabledFor(logging.DEBUG):
        first_words = [
            str(w["word"]) for w in words if float(w["start"]) >= aligned_start
        ][:10]
        log.debug("Clip %d starts at %.3fs: %s", clip_index, aligned_start, " ".join(first_words))

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
    transcript_words: list[dict] = transcript.get("words", [])
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
        duration_hint = min(max(min_seconds + 20, 38), max_seconds)
        end = start + duration_hint
        nstart, nend = _align_to_natural_boundaries(
            segments,
            start,
            end,
            total_duration=total_duration,
            min_seconds=min_seconds,
            max_seconds=max_seconds,
            words=transcript_words,
            clip_index=len(moments) + 1,
        )
        if any(abs(nstart - existing["start"]) < 18 for existing in moments):
            continue
        vscore = _compute_virality_score(segment["text"])
        nstart, nend = _apply_score_based_duration_cap(nstart, nend, vscore, max_seconds)
        moments.append(
            {
                "title": segment["text"][:72].strip() or "Momento destacado",
                "reason": "Segmento con alta densidad de gancho y potencial de retencion.",
                "score": round(float(score), 3),
                "virality_score": vscore,
                "start": nstart,
                "end": nend,
            }
        )

    if len(moments) < target_count:
        target_duration = min(max(min_seconds + 24, 45), max_seconds)
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
                words=transcript_words,
                clip_index=len(moments) + 1,
            )
            fallback_text = _window_text(segments, nstart, nend)
            fallback_vscore = _compute_virality_score(fallback_text)
            nstart, nend = _apply_score_based_duration_cap(nstart, nend, fallback_vscore, max_seconds)
            moments.append(
                {
                    "title": f"Highlight {len(moments) + 1}",
                    "reason": "Fallback temporal uniforme.",
                    "score": 1.0,
                    "virality_score": fallback_vscore,
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


def _build_genre_prompt_line(content_genre: str | None, video_language: str) -> str:
    """Return the virality-signals prompt line for the given genre, or empty string."""
    if not content_genre:
        return ""
    signals_dict = GENRE_VIRALITY_SIGNALS_EN if video_language == "en" else GENRE_VIRALITY_SIGNALS_ES
    signals = signals_dict.get(content_genre)
    if signals:
        return f"- {signals}"
    # Fallback for unknown genres.
    if video_language == "en":
        return f"- Content genre: {content_genre}. Adapt selection to what works virally in this genre."
    return f"- Genero del contenido: {content_genre}. Adapta la seleccion a lo que funciona viralmente en este genero."


def choose_viral_moments(
    transcript: dict,
    settings: Settings,
    target_count: int | None = None,
    min_clip_seconds: int | None = None,
    max_clip_seconds: int | None = None,
    rejection_feedback: list[str] | None = None,
    content_genre: str | None = None,
    specific_moments_instruction: str | None = None,
    video_language: str | None = None,
) -> list[dict]:
    # target_count == 0 signals AI-choose mode (unlimited).
    ai_unlimited = False
    if target_count is not None and target_count <= 0:
        target_count = None
    if target_count is None:
        ai_unlimited = True
        # Fallback count used only for heuristic path (no OpenAI key).
        segments_peek = transcript.get("segments", [])
        total_dur = float(segments_peek[-1]["end"]) if segments_peek else 300.0
        heuristic_fallback_count = max(4, min(12, int(total_dur / 60)))
    else:
        heuristic_fallback_count = max(1, int(target_count))

    lang = (video_language or "es").strip() or "es"
    min_seconds = float(min_clip_seconds or settings.min_clip_seconds)
    max_seconds = float(max_clip_seconds or settings.max_clip_seconds)
    max_seconds = max(max_seconds, min_seconds, MIN_NATURAL_MAX_CLIP_SECONDS)
    segments = transcript["segments"]
    transcript_words: list[dict] = transcript.get("words", [])
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
            heuristic_fallback_count,
            min_seconds,
            max_seconds,
            feedback_notes,
        )

    # -- Build system prompt --
    system_prompt = (
        "Eres editor experto de clips virales para TikTok e Instagram Reels. "
        "Debes identificar momentos con hook fuerte, controversia, insight accionable o emocion alta."
    ) if lang != "en" else (
        "You are an expert viral clip editor for TikTok and Instagram Reels. "
        "You must identify moments with strong hooks, controversy, actionable insight, or high emotion."
    )
    # Append language-specific instructions.
    system_prompt += " " + (LANGUAGE_PROMPT_EN if lang == "en" else LANGUAGE_PROMPT_ES)

    # -- Build count rule --
    if ai_unlimited:
        count_rule = (
            "- Identifica TODOS los momentos virales del transcript sin importar la cantidad. "
            "No limites el numero de resultados — devuelve cada momento que califique como viral "
            "segun el tipo de contenido y las senales de viralidad. Calidad sobre cantidad."
        ) if lang != "en" else (
            "- Identify ALL viral moments in the transcript regardless of quantity. "
            "Do not limit the output count — return every moment that qualifies as viral "
            "based on the content type and virality signals. Quality over artificial limits."
        )
    else:
        requested_count = max(1, int(target_count))  # type: ignore[arg-type]
        count_rule = (
            f"- Devuelve exactamente {requested_count} momentos."
        ) if lang != "en" else (
            f"- Return exactly {requested_count} moments."
        )

    # -- Build genre and instruction lines --
    genre_line = _build_genre_prompt_line(content_genre, lang)
    instruction_line = ""
    if specific_moments_instruction:
        if lang == "en":
            instruction_line = f"- User-specific instruction: {specific_moments_instruction}"
        else:
            instruction_line = f"- Instruccion especifica del usuario: {specific_moments_instruction}"
    feedback_line = ""
    if feedback_notes:
        if lang == "en":
            feedback_line = "- Avoid topics similar to this rejected-clips feedback:\n" + chr(10).join(f"  - {note}" for note in feedback_notes[:12])
        else:
            feedback_line = "- Evita temas similares a este feedback de clips rechazados:\n" + chr(10).join(f"  - {note}" for note in feedback_notes[:12])

    # -- Build start-boundary rule --
    start_rule = (
        "- CRITICO: Cada clip DEBE comenzar al inicio de una frase u oracion completa. "
        "Nunca inicies un clip a mitad de una idea. El primer segundo del clip debe contener "
        "el comienzo claro de una frase. Ubica el 'start' en el timestamp donde comienza una nueva oracion o idea."
    ) if lang != "en" else (
        "- CRITICAL: Each clip MUST start at the beginning of a complete sentence or phrase. "
        "Never start a clip mid-sentence. The first second of the clip must contain "
        "the clear beginning of a phrase. Place 'start' at the timestamp where a new sentence or idea begins."
    )

    if lang == "en":
        user_prompt = f"""
Analyze this timestamped transcript and return ONLY valid JSON with this format:
{{
  "moments": [
    {{
      "title": "short string",
      "reason": "why it can be viral",
      "score": 0-100,
      "start": seconds (float),
      "end": seconds (float)
    }}
  ]
}}

Rules:
{count_rule}
- Do not cut a clip mid-sentence, mid-laugh, mid-reaction, or before the punchline/resolution is delivered.
- The clip end point must be after the moment reaches its natural conclusion; include the audience reaction or the speaker's final word on the topic.
- Duration must be 35-90 seconds. Minimum 35 seconds — never return an end time less than 35 s after the start.
- If a viral moment runs 50 seconds, the clip must be 50 seconds. Never truncate to hit a target.
{start_rule}
- Do not repeat similar ideas.
- Prioritize moments with strong/controversial opinions and/or concrete actionable advice.
- Avoid guest intros, thank-yous, and small talk without useful insight.
- Prefer segments with a clear statement + explanation + practical indication.
{genre_line}
{instruction_line}
{feedback_line}

Transcript:
{transcript_for_prompt}
"""
    else:
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
{count_rule}
- No cortes un clip a mitad de frase, de risa, de reaccion o antes del remate/resolucion.
- El punto final del clip debe quedar despues de la conclusion natural; incluye reaccion de audiencia o la ultima palabra del speaker sobre el tema.
- Duracion: 35-90 segundos. Minimo 35 segundos — nunca devuelvas un end menos de 35 s despues del start.
- Si un momento viral dura 50 segundos, el clip debe durar 50 segundos. Nunca trunques para cumplir un objetivo.
{start_rule}
- No repetir ideas similares.
- Prioriza momentos con opinion fuerte/polemica y/o consejo accionable concreto.
- Evita intros de invitado, agradecimientos y charla de presentacion sin insight util.
- Prefiere segmentos donde haya afirmacion clara + explicacion + indicacion practica.
{genre_line}
{instruction_line}
{feedback_line}

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
        for moment_idx, raw_moment in enumerate(raw_moments, start=1):
            start = float(raw_moment.get("start", 0.0))
            end = float(raw_moment.get("end", start + min_seconds))
            nstart, nend = _align_to_natural_boundaries(
                segments,
                start,
                end,
                total_duration=total_duration,
                min_seconds=min_seconds,
                max_seconds=max_seconds,
                words=transcript_words,
                clip_index=moment_idx,
            )
            window_text = _window_text(segments, nstart, nend)
            vscore = _compute_virality_score(window_text)
            nstart, nend = _apply_score_based_duration_cap(nstart, nend, vscore, max_seconds)
            moments.append(
                {
                    "title": str(raw_moment.get("title", "Momento viral")).strip(),
                    "reason": str(raw_moment.get("reason", "")).strip(),
                    "score": float(raw_moment.get("score", 50.0)),
                    "virality_score": vscore,
                    "start": nstart,
                    "end": nend,
                }
            )

        if not ai_unlimited:
            requested_count_int = max(1, int(target_count))  # type: ignore[arg-type]
            if len(moments) < requested_count_int:
                fallback = _heuristic_moments(
                    transcript,
                    settings,
                    requested_count_int,
                    min_seconds,
                    max_seconds,
                    feedback_notes,
                )
                known_starts = {round(moment["start"], 1) for moment in moments}
                for candidate in fallback:
                    if round(candidate["start"], 1) in known_starts:
                        continue
                    moments.append(candidate)
                    if len(moments) >= requested_count_int:
                        break
            ranked = _rerank_moments_for_viral_fit(moments[:requested_count_int], segments, total_duration)
        else:
            # AI-unlimited mode: accept all moments the model returned, no cap.
            if not moments:
                # Only use heuristic fallback when LLM returned nothing.
                moments = _heuristic_moments(
                    transcript, settings, heuristic_fallback_count,
                    min_seconds, max_seconds, feedback_notes,
                )
            ranked = _rerank_moments_for_viral_fit(moments, segments, total_duration)
        return _sort_moments_by_feedback(ranked, feedback_tokens)
    except Exception:
        return _heuristic_moments(
            transcript,
            settings,
            heuristic_fallback_count,
            min_seconds,
            max_seconds,
            feedback_notes,
        )
