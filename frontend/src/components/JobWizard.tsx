import { Fragment, useCallback, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { ArrowLeft, ArrowRight, Sparkles, Check } from "lucide-react";
import previewSampleImage from "../assets/preview-sample.svg";
import type { AspectRatio, ContentGenre, FormState, NoticeType, VideoLanguage, VideoMeta } from "../types";

const API_BASE = "";

// --- Preview metrics ---

const PREVIEW_FONT_SCALE = 8.6;

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function fontVisualFactor(fontName: string): number {
  const normalized = fontName.trim().toLowerCase();
  if (normalized === "montserrat") return 1.06;
  if (normalized === "oswald") return 0.92;
  if (normalized === "roboto condensed") return 0.95;
  if (normalized === "anton") return 1.0;
  if (normalized === "bebas neue") return 0.88;
  return 1;
}

function previewMetrics(width: number, height: number, fontSize: number, fontName: string) {
  const safeW = Math.max(1, Math.floor(width));
  const safeH = Math.max(1, Math.floor(height));
  const ratio = Math.max(0.1, safeW / safeH);
  const baseArea = ratio >= 1 ? 96_000 : 84_000;

  let stageWidth = Math.round(Math.sqrt(baseArea * ratio));
  let stageHeight = Math.round(stageWidth / ratio);
  const maxStageWidth = ratio >= 1 ? 430 : 320;
  const maxStageHeight = ratio >= 1 ? 280 : 430;

  if (stageWidth > maxStageWidth) {
    const factor = maxStageWidth / stageWidth;
    stageWidth = Math.round(stageWidth * factor);
    stageHeight = Math.round(stageHeight * factor);
  }
  if (stageHeight > maxStageHeight) {
    const factor = maxStageHeight / stageHeight;
    stageWidth = Math.round(stageWidth * factor);
    stageHeight = Math.round(stageHeight * factor);
  }

  stageWidth = clamp(stageWidth, 170, 430);
  stageHeight = clamp(stageHeight, 170, 430);

  const captionSize = clamp(
    Math.round((stageHeight / 22) * (fontSize / 36) * fontVisualFactor(fontName)),
    9,
    52,
  );
  const cardPadX = clamp(Math.round(stageWidth * 0.09), 12, 24);
  const cardPadY = clamp(Math.round(stageHeight * 0.06), 10, 18);
  const cardWidth = clamp(stageWidth + cardPadX * 2, 220, 472);

  return { stageWidth, stageHeight, captionSize, cardPadX, cardPadY, cardWidth };
}

// --- Constants ---

const GENRE_OPTIONS: { id: ContentGenre; emoji: string; label: string }[] = [
  { id: "podcast", emoji: "\u{1F399}\uFE0F", label: "Podcast" },
  { id: "business", emoji: "\u{1F4BC}", label: "Business" },
  { id: "entertainment", emoji: "\u{1F3AD}", label: "Entertainment" },
  { id: "education", emoji: "\u{1F4DA}", label: "Education" },
  { id: "fitness", emoji: "\u{1F3CB}\uFE0F", label: "Fitness" },
  { id: "cooking", emoji: "\u{1F373}", label: "Cocina" },
  { id: "gaming", emoji: "\u{1F3AE}", label: "Gaming" },
  { id: "motivation", emoji: "\u{1F4A1}", label: "Motivacion" },
];

const ASPECT_RATIOS: { id: AspectRatio; width: number; height: number; label: string; icon: string; platforms: string[] }[] = [
  { id: "9:16", width: 1080, height: 1920, label: "9:16", icon: "\u25AF", platforms: ["TikTok", "Reels", "Shorts"] },
  { id: "1:1", width: 1080, height: 1080, label: "1:1", icon: "\u2B1C", platforms: ["Instagram", "Facebook"] },
  { id: "16:9", width: 1920, height: 1080, label: "16:9", icon: "\u25AD", platforms: ["YouTube", "Twitter/X", "LinkedIn"] },
];

function toNumberOr(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function extractVideoId(url: string): string | null {
  const match = url.match(/(?:v=|\/)([\w-]{11})(?:[?&]|$)/);
  return match ? match[1] : null;
}

// --- Component ---

interface JobWizardProps {
  form: FormState;
  fontOptions: string[];
  submitting: boolean;
  notice: string;
  noticeType: NoticeType;
  onUpdateForm: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  onCreateJob: () => void;
  onFieldFormatError: (message: string) => void;
}

export function JobWizard({
  form,
  fontOptions,
  submitting,
  notice,
  noticeType,
  onUpdateForm,
  onCreateJob,
}: JobWizardProps) {
  const [step, setStep] = useState<1 | 2 | 3>(1);
  const [videoMeta, setVideoMeta] = useState<VideoMeta | null>(null);
  const [metaLoading, setMetaLoading] = useState(false);
  const [metaError, setMetaError] = useState("");
  const [thumbnailUrl, setThumbnailUrl] = useState("");
  const [draggingSubtitle, setDraggingSubtitle] = useState(false);
  const thumbnailRef = useRef("");

  // Drag state for subtitle positioning
  const stageRef = useRef<HTMLDivElement | null>(null);
  const isDragging = useRef(false);

  // Fetch video metadata when URL changes
  useEffect(() => {
    const videoId = extractVideoId(form.youtube_url);
    if (!videoId) {
      setVideoMeta(null);
      setThumbnailUrl("");
      setMetaError("");
      return;
    }

    const thumb = `https://img.youtube.com/vi/${videoId}/maxresdefault.jpg`;
    setThumbnailUrl(thumb);
    thumbnailRef.current = thumb;

    let cancelled = false;
    async function fetchMeta() {
      setMetaLoading(true);
      setMetaError("");
      try {
        const resp = await fetch(`${API_BASE}/api/youtube/oembed?url=${encodeURIComponent(form.youtube_url)}`);
        if (!resp.ok) throw new Error("No se pudo obtener metadata");
        const data = await resp.json();
        if (!cancelled) {
          setVideoMeta({
            title: data.title || "Sin titulo",
            author_name: data.author_name || "Desconocido",
            thumbnail_url: thumb,
          });
        }
      } catch {
        if (!cancelled) {
          setVideoMeta({
            title: "Video de YouTube",
            author_name: "",
            thumbnail_url: thumb,
          });
          setMetaError("");
        }
      } finally {
        if (!cancelled) setMetaLoading(false);
      }
    }
    const timer = setTimeout(fetchMeta, 300);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [form.youtube_url]);

  const canContinueStep1 = Boolean(form.youtube_url.trim() && extractVideoId(form.youtube_url));

  const preview = useMemo(
    () =>
      previewMetrics(
        form.output_width,
        form.output_height,
        form.subtitle_font_size,
        form.subtitle_font_name,
      ),
    [form.output_width, form.output_height, form.subtitle_font_size, form.subtitle_font_name],
  );

  const previewStyle: CSSProperties = {
    alignSelf: "center",
    width: `${preview.cardWidth}px`,
    maxWidth: "100%",
    ["--preview-stage-width" as string]: `${preview.stageWidth}px`,
    ["--preview-stage-height" as string]: `${preview.stageHeight}px`,
    ["--preview-caption-size" as string]: `${preview.captionSize}px`,
    ["--preview-card-pad-x" as string]: `${preview.cardPadX}px`,
    ["--preview-card-pad-y" as string]: `${preview.cardPadY}px`,
  };

  const handleRatioSelect = (ratio: (typeof ASPECT_RATIOS)[number]) => {
    onUpdateForm("aspect_ratio", ratio.id);
    onUpdateForm("output_width", ratio.width);
    onUpdateForm("output_height", ratio.height);
  };

  // --- Drag-to-position handlers ---
  const handleDragStart = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      const stage = stageRef.current;
      if (!stage) return;
      isDragging.current = true;
      setDraggingSubtitle(true);

      const handleMove = (moveEvent: MouseEvent) => {
        if (!isDragging.current || !stage) return;
        const rect = stage.getBoundingClientRect();
        const x = clamp(((moveEvent.clientX - rect.left) / rect.width) * 100, 5, 95);
        const y = clamp(((moveEvent.clientY - rect.top) / rect.height) * 100, 5, 95);
        onUpdateForm("subtitle_position_x", Math.round(x));
        onUpdateForm("subtitle_position_y", Math.round(y));
      };

      const handleUp = () => {
        isDragging.current = false;
        setDraggingSubtitle(false);
        document.removeEventListener("mousemove", handleMove);
        document.removeEventListener("mouseup", handleUp);
      };

      document.addEventListener("mousemove", handleMove);
      document.addEventListener("mouseup", handleUp);
    },
    [onUpdateForm],
  );

  // Use the persisted thumbnail ref as fallback when thumbnailUrl state might be stale
  const effectiveThumbnail = thumbnailUrl || thumbnailRef.current;
  const showCenterGuide = draggingSubtitle && form.subtitle_position_x === 50;

  const stepLabels = ["URL", "Clips", "Formato"];

  return (
    <section className="panel wizard">
      {/* Step indicator */}
      <div className="wizard-steps">
        <div className="wizard-steps-track">
          {stepLabels.map((label, idx) => {
            const stepNum = (idx + 1) as 1 | 2 | 3;
            const isCompleted = step > stepNum;
            const isActive = step === stepNum;
            return (
              <Fragment key={label}>
                {idx > 0 && (
                  <div className={`wizard-step-line${isCompleted ? " wizard-step-line--done" : ""}`} />
                )}
                <button
                  className={`wizard-step-dot${isActive ? " wizard-step-dot--active" : ""}${isCompleted ? " wizard-step-dot--completed" : ""}`}
                  onClick={() => {
                    if (isCompleted) setStep(stepNum);
                  }}
                  type="button"
                  disabled={!isCompleted && !isActive}
                >
                  {isCompleted ? <Check size={14} /> : stepNum}
                </button>
              </Fragment>
            );
          })}
        </div>
        <div className="wizard-steps-labels">
          {stepLabels.map((label, idx) => {
            const isActive = step === (idx + 1);
            return (
              <Fragment key={label}>
                {idx > 0 && <div className="wizard-step-label-spacer" />}
                <span className={`wizard-step-label${isActive ? " wizard-step-label--active" : ""}`}>
                  {label}
                </span>
              </Fragment>
            );
          })}
        </div>
      </div>

      <div className="wizard-body">
        {/* ===== Step 1: YouTube URL ===== */}
        {step === 1 && (
          <div className="wizard-step-content">
            <h2>Pega un link de YouTube</h2>
            <p className="wizard-step-desc">El video se descargara y transcribira automaticamente.</p>

            <input
              className="wizard-url-input"
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={form.youtube_url}
              onChange={(e) => onUpdateForm("youtube_url", e.target.value)}
              autoFocus
            />

            {metaLoading && <p className="wizard-meta-loading">Cargando metadata...</p>}

            {videoMeta && effectiveThumbnail && (
              <div className="wizard-video-card">
                <img
                  className="wizard-video-thumb"
                  src={effectiveThumbnail}
                  alt="Thumbnail"
                  onError={(e) => {
                    const target = e.target as HTMLImageElement;
                    const videoId = extractVideoId(form.youtube_url);
                    if (videoId && target.src.includes("maxresdefault")) {
                      target.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
                    }
                  }}
                />
                <div className="wizard-video-info">
                  <p className="wizard-video-title">{videoMeta.title}</p>
                  {videoMeta.author_name && (
                    <p className="wizard-video-author">{videoMeta.author_name}</p>
                  )}
                </div>
              </div>
            )}

            {metaError && <p className="wizard-meta-error">{metaError}</p>}
          </div>
        )}

        {/* ===== Step 2: Clip Configuration ===== */}
        {step === 2 && (
          <div className="wizard-step-content">
            <h2>Configuracion de clips</h2>
            <p className="wizard-step-desc">Elige cuantos clips generar y el tipo de contenido.</p>

            {/* AI Choose Toggle */}
            <button
              className={`wizard-ai-toggle${form.ai_choose_count ? " wizard-ai-toggle--active" : ""}`}
              onClick={() => onUpdateForm("ai_choose_count", !form.ai_choose_count)}
              type="button"
            >
              <Sparkles size={20} />
              <div>
                <strong>Dejar que la IA elija</strong>
                <span>La IA determinara la cantidad optima de clips</span>
              </div>
            </button>

            {form.ai_choose_count && (
              <p className="wizard-ai-hint">La IA identificara todos los momentos virales del video</p>
            )}

            {/* Clips Count */}
            {!form.ai_choose_count && (
              <label className="field">
                <span>Cantidad de clips</span>
                <select
                  value={form.clips_count}
                  onChange={(e) => onUpdateForm("clips_count", toNumberOr(e.target.value, 4))}
                >
                  {Array.from({ length: 12 }).map((_, idx) => {
                    const value = idx + 1;
                    return (
                      <option key={value} value={value}>
                        {value}
                      </option>
                    );
                  })}
                </select>
              </label>
            )}

            {/* Language Selector */}
            <div className="wizard-lang-section">
              <p className="wizard-field-label">Idioma del video</p>
              <div className="wizard-lang-toggle">
                <button
                  className={`wizard-lang-btn${form.video_language === "es" ? " wizard-lang-btn--active" : ""}`}
                  onClick={() => onUpdateForm("video_language", "es" as VideoLanguage)}
                  type="button"
                >
                  Espanol
                </button>
                <button
                  className={`wizard-lang-btn${form.video_language === "en" ? " wizard-lang-btn--active" : ""}`}
                  onClick={() => onUpdateForm("video_language", "en" as VideoLanguage)}
                  type="button"
                >
                  English
                </button>
              </div>
            </div>

            {/* Genre Grid */}
            <div className="wizard-genre-section">
              <p className="wizard-field-label">Genero del contenido (opcional)</p>
              <div className="wizard-genre-grid">
                {GENRE_OPTIONS.map((genre) => (
                  <button
                    key={genre.id}
                    className={`wizard-genre-pill${form.content_genre === genre.id ? " wizard-genre-pill--active" : ""}`}
                    onClick={() =>
                      onUpdateForm("content_genre", form.content_genre === genre.id ? "" : genre.id)
                    }
                    type="button"
                  >
                    <span className="wizard-genre-emoji">{genre.emoji}</span>
                    <span>{genre.label}</span>
                  </button>
                ))}
              </div>
            </div>

            {/* Specific Moments */}
            <label className="field">
              <span>Momentos especificos (opcional)</span>
              <textarea
                className="wizard-moments-textarea"
                placeholder="Ej: Enfocate en la parte sobre funnels de marketing..."
                value={form.specific_moments_instruction}
                onChange={(e) => onUpdateForm("specific_moments_instruction", e.target.value)}
                rows={3}
                maxLength={1000}
              />
            </label>
          </div>
        )}

        {/* ===== Step 3: Format & Subtitles ===== */}
        {step === 3 && (
          <div className="wizard-step-content">
            <h2>Formato y subtitulos</h2>
            <p className="wizard-step-desc">Elige la relacion de aspecto y el estilo de subtitulos.</p>

            <div className="wizard-format-layout">
              <div className="wizard-format-controls">
                {/* Aspect Ratio with Platform Labels */}
                <div className="wizard-ratio-section">
                  <p className="wizard-field-label">Relacion de aspecto</p>
                  <div className="wizard-ratio-group">
                    {ASPECT_RATIOS.map((ratio) => (
                      <button
                        key={ratio.id}
                        className={`wizard-ratio-btn${form.aspect_ratio === ratio.id ? " wizard-ratio-btn--active" : ""}`}
                        onClick={() => handleRatioSelect(ratio)}
                        type="button"
                      >
                        <span className="wizard-ratio-icon">{ratio.icon}</span>
                        <span>{ratio.label}</span>
                        <div className="wizard-ratio-platforms">
                          {ratio.platforms.map((p) => (
                            <span key={p} className="wizard-platform-tag">{p}</span>
                          ))}
                        </div>
                      </button>
                    ))}
                  </div>
                </div>

                {/* Subtitle Toggle */}
                <div className="wizard-subtitle-toggle-section">
                  <label className="wizard-switch-label">
                    <span>Subtitulos</span>
                    <button
                      className={`wizard-switch${form.subtitles_enabled ? " wizard-switch--on" : ""}`}
                      onClick={() => onUpdateForm("subtitles_enabled", !form.subtitles_enabled)}
                      type="button"
                      role="switch"
                      aria-checked={form.subtitles_enabled}
                    >
                      <span className="wizard-switch-thumb" />
                    </button>
                  </label>
                </div>

                {/* Subtitle Controls (no presets, no advanced toggle) */}
                {form.subtitles_enabled && (
                  <div className="wizard-subtitle-controls">
                    {/* Font Selector */}
                    <label className="field">
                      <span>Fuente</span>
                      <select
                        value={form.subtitle_font_name}
                        onChange={(e) => onUpdateForm("subtitle_font_name", e.target.value)}
                      >
                        {fontOptions.map((font) => (
                          <option key={font} value={font}>
                            {font}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                )}
              </div>

              {/* Live Preview */}
              <div className="subtitle-preview subtitle-preview-adaptive" style={previewStyle}>
                <p>
                  Preview subtitulos
                  <span className="subtitle-size-chip">
                    {form.output_width}x{form.output_height} ({form.aspect_ratio})
                  </span>
                </p>
                <div className="subtitle-stage-wrap" style={{ maxHeight: "400px" }}>
                  <div
                    ref={stageRef}
                    className="subtitle-stage"
                  >
                    <img
                      className="subtitle-stage-bg subtitle-stage-bg--blurred"
                      src={effectiveThumbnail || previewSampleImage}
                      alt=""
                      onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        const videoId = extractVideoId(form.youtube_url);
                        if (videoId && target.src.includes("maxresdefault")) {
                          target.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
                        }
                      }}
                    />
                    <div className="subtitle-stage-overlay" />
                    <img
                      className="subtitle-stage-foreground"
                      src={effectiveThumbnail || previewSampleImage}
                      alt=""
                      onError={(e) => {
                        const target = e.target as HTMLImageElement;
                        const videoId = extractVideoId(form.youtube_url);
                        if (videoId && target.src.includes("maxresdefault")) {
                          target.src = `https://img.youtube.com/vi/${videoId}/hqdefault.jpg`;
                        }
                      }}
                    />
                    {showCenterGuide && <div className="subtitle-center-guide" aria-hidden="true" />}

                    {form.subtitles_enabled && (
                      <div
                        className="subtitle-caption subtitle-caption--draggable"
                        style={{
                          fontFamily: `"${form.subtitle_font_name}", sans-serif`,
                          fontSize: `${preview.captionSize}px`,
                          left: `${form.subtitle_position_x}%`,
                          top: `${form.subtitle_position_y}%`,
                          transform: "translate(-50%, -50%)",
                        }}
                        onMouseDown={handleDragStart}
                      >
                        ESTA FRASE SE CONSTRUYE EN VIVO
                      </div>
                    )}
                  </div>
                </div>
                {form.subtitles_enabled && (
                  <p className="wizard-drag-hint">Arrastra el texto para reposicionar</p>
                )}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Notice */}
      {notice && <div className={`notice notice-${noticeType}`}>{notice}</div>}

      {/* Navigation */}
      <div className="wizard-nav">
        {step > 1 ? (
          <button
            className="btn btn-ghost"
            onClick={() => setStep((step - 1) as 1 | 2)}
            type="button"
          >
            <ArrowLeft size={16} />
            Atras
          </button>
        ) : (
          <div />
        )}

        {step < 3 ? (
          <button
            className="btn btn-primary"
            onClick={() => setStep((step + 1) as 2 | 3)}
            disabled={step === 1 && !canContinueStep1}
            type="button"
          >
            Continuar
            <ArrowRight size={16} />
          </button>
        ) : (
          <button
            className="btn btn-primary"
            disabled={submitting}
            onClick={onCreateJob}
            type="button"
          >
            {submitting ? "Creando job..." : "Generar clips"}
          </button>
        )}
      </div>
    </section>
  );
}
