import previewSampleImage from "../assets/preview-sample.svg";
import { useMemo, type CSSProperties } from "react";
import type { FormState, NoticeType } from "../types";

interface JobConfigPanelProps {
  form: FormState;
  fontOptions: string[];
  submitting: boolean;
  notice: string;
  noticeType: NoticeType;
  previewImageUrl: string;
  previewLoading: boolean;
  previewError: string;
  onUpdateForm: <K extends keyof FormState>(key: K, value: FormState[K]) => void;
  onCreateJob: () => void;
  onFieldFormatError: (message: string) => void;
}

const OUTPUT_PRESETS = [
  { id: "story_hd", label: "Vertical HD (720x1280)", width: 720, height: 1280 },
  { id: "story_fullhd", label: "Vertical Full HD (1080x1920)", width: 1080, height: 1920 },
  { id: "portrait_4_5", label: "Portrait 4:5 (1080x1350)", width: 1080, height: 1350 },
  { id: "square", label: "Square (1080x1080)", width: 1080, height: 1080 },
  { id: "landscape", label: "Landscape (1920x1080)", width: 1920, height: 1080 },
] as const;
const BACKEND_SUBTITLE_FONT_SIZE = 10;
const BACKEND_SUBTITLE_SPACING = 2.2;
const PREVIEW_FONT_SCALE = 8.6;

function toNumberOr(value: string, fallback: number): number {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parsePositiveInteger(value: string): number | null {
  if (!/^\d+$/.test(value.trim())) return null;
  return Number(value);
}

function currentPresetId(width: number, height: number): string {
  const matched = OUTPUT_PRESETS.find((preset) => preset.width === width && preset.height === height);
  return matched ? matched.id : OUTPUT_PRESETS[1].id;
}

function ratioLabel(width: number, height: number): string {
  const gcd = (a: number, b: number): number => (b === 0 ? a : gcd(b, a % b));
  const safeW = Math.max(1, Math.floor(width));
  const safeH = Math.max(1, Math.floor(height));
  const div = gcd(safeW, safeH);
  return `${safeW / div}:${safeH / div}`;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function fontVisualFactor(fontName: string): number {
  const normalized = fontName.trim().toLowerCase();
  if (normalized === "montserrat") return 1.06;
  if (normalized === "poppins") return 0.97;
  if (normalized === "arial") return 1.02;
  return 1;
}

function previewMetrics(width: number, height: number, padX: number, padY: number, fontName: string) {
  const safeW = Math.max(1, Math.floor(width));
  const safeH = Math.max(1, Math.floor(height));
  const effectivePadX = Math.max(20, Math.floor(padX));
  const effectivePadY = Math.max(20, Math.floor(padY));
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

  const scaleX = stageWidth / safeW;
  const scaleY = stageHeight / safeH;
  const scaledPadX = Math.max(2, Math.round(effectivePadX * scaleX));
  const scaledPadY = Math.max(2, Math.round(effectivePadY * scaleY));
  const captionSize = clamp(
    Math.round(BACKEND_SUBTITLE_FONT_SIZE * PREVIEW_FONT_SCALE * scaleY * fontVisualFactor(fontName)),
    12,
    24,
  );
  const captionLetterSpacing = clamp(Math.round(BACKEND_SUBTITLE_SPACING * PREVIEW_FONT_SCALE * scaleX * 10) / 10, 0.8, 2.8);
  const cardPadX = clamp(Math.round(stageWidth * 0.09), 12, 24);
  const cardPadY = clamp(Math.round(stageHeight * 0.06), 10, 18);
  const cardWidth = clamp(stageWidth + cardPadX * 2, 220, 472);

  return {
    stageWidth,
    stageHeight,
    scaledPadX,
    scaledPadY,
    captionSize,
    captionLetterSpacing,
    cardPadX,
    cardPadY,
    cardWidth,
  };
}

export function JobConfigPanel({
  form,
  fontOptions,
  submitting,
  notice,
  noticeType,
  previewImageUrl,
  previewLoading,
  previewError,
  onUpdateForm,
  onCreateJob,
  onFieldFormatError,
}: JobConfigPanelProps) {
  const selectedPresetId = currentPresetId(form.output_width, form.output_height);
  const previewRatioLabel = ratioLabel(form.output_width, form.output_height);
  const preview = useMemo(
    () =>
      previewMetrics(
        form.output_width,
        form.output_height,
        form.subtitle_margin_horizontal,
        form.subtitle_margin_vertical,
        form.subtitle_font_name,
      ),
    [
      form.output_width,
      form.output_height,
      form.subtitle_margin_horizontal,
      form.subtitle_margin_vertical,
      form.subtitle_font_name,
    ],
  );
  const previewStyle: CSSProperties = {
    alignSelf: "center",
    width: `${preview.cardWidth}px`,
    maxWidth: "100%",
    ["--preview-stage-width" as string]: `${preview.stageWidth}px`,
    ["--preview-stage-height" as string]: `${preview.stageHeight}px`,
    ["--preview-pad-x" as string]: `${preview.scaledPadX}px`,
    ["--preview-pad-y" as string]: `${preview.scaledPadY}px`,
    ["--preview-caption-size" as string]: `${preview.captionSize}px`,
    ["--preview-caption-spacing" as string]: `${preview.captionLetterSpacing}px`,
    ["--preview-card-pad-x" as string]: `${preview.cardPadX}px`,
    ["--preview-card-pad-y" as string]: `${preview.cardPadY}px`,
  };

  return (
    <section className="panel config-panel">
      <h2>Configuracion del job</h2>
      <div className="config-stage-layout">
        <div className="config-fields">
          <label className="field">
            <span>Link de YouTube</span>
            <input
              type="url"
              placeholder="https://www.youtube.com/watch?v=..."
              value={form.youtube_url}
              onChange={(event) => onUpdateForm("youtube_url", event.target.value)}
            />
          </label>

          <div className="field-grid">
            <label className="field small">
              <span>Clips</span>
              <select
                value={form.clips_count}
                onChange={(event) => onUpdateForm("clips_count", toNumberOr(event.target.value, 4))}
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

            <label className="field small">
              <span>Min (s)</span>
              <input
                type="text"
                inputMode="numeric"
                value={String(form.min_clip_seconds)}
                onChange={(event) => {
                  const parsed = parsePositiveInteger(event.target.value);
                  if (parsed === null) {
                    onFieldFormatError("Formato invalido en Min (s): ingresa un numero entero.");
                    return;
                  }
                  onUpdateForm("min_clip_seconds", parsed);
                }}
              />
            </label>

            <label className="field small">
              <span>Max (s)</span>
              <input
                type="text"
                inputMode="numeric"
                value={String(form.max_clip_seconds)}
                onChange={(event) => {
                  const parsed = parsePositiveInteger(event.target.value);
                  if (parsed === null) {
                    onFieldFormatError("Formato invalido en Max (s): ingresa un numero entero.");
                    return;
                  }
                  onUpdateForm("max_clip_seconds", parsed);
                }}
              />
            </label>
          </div>

          <div className="field-grid field-grid-single">
            <label className="field small">
              <span>Formato</span>
              <select
                value={selectedPresetId}
                onChange={(event) => {
                  const selected = OUTPUT_PRESETS.find((preset) => preset.id === event.target.value);
                  if (!selected) return;
                  onUpdateForm("output_width", selected.width);
                  onUpdateForm("output_height", selected.height);
                }}
              >
                {OUTPUT_PRESETS.map((preset) => (
                  <option key={preset.id} value={preset.id}>
                    {preset.label}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <div className="field-grid">
            <label className="field small">
              <span>Fuente subtitulo</span>
              <select
                value={form.subtitle_font_name}
                onChange={(event) => onUpdateForm("subtitle_font_name", event.target.value)}
              >
                {fontOptions.map((font) => (
                  <option key={font} value={font}>
                    {font}
                  </option>
                ))}
              </select>
            </label>

            <label className="field small">
              <span>Pad X</span>
              <input
                type="text"
                inputMode="numeric"
                value={String(form.subtitle_margin_horizontal)}
                onChange={(event) => {
                  const parsed = parsePositiveInteger(event.target.value);
                  if (parsed === null) {
                    onFieldFormatError("Formato invalido en Pad X: ingresa un numero entero.");
                    return;
                  }
                  onUpdateForm("subtitle_margin_horizontal", parsed);
                }}
              />
            </label>

            <label className="field small">
              <span>Pad Y (desde abajo)</span>
              <input
                type="text"
                inputMode="numeric"
                value={String(form.subtitle_margin_vertical)}
                onChange={(event) => {
                  const parsed = parsePositiveInteger(event.target.value);
                  if (parsed === null) {
                    onFieldFormatError("Formato invalido en Pad Y: ingresa un numero entero.");
                    return;
                  }
                  onUpdateForm("subtitle_margin_vertical", parsed);
                }}
              />
            </label>
          </div>

          <button className="btn btn-primary" disabled={submitting} onClick={onCreateJob}>
            {submitting ? "Creando job..." : "Generar clips"}
          </button>

          {notice && <div className={`notice notice-${noticeType}`}>{notice}</div>}
        </div>

        <div className="subtitle-preview subtitle-preview-adaptive" style={previewStyle}>
          <p>
            Preview subtitulos
            <span className="subtitle-size-chip">
              {form.output_width}x{form.output_height} ({previewRatioLabel})
            </span>
          </p>
          <div className="subtitle-stage-wrap">
            <div
              className="subtitle-stage"
              style={{
                backgroundImage: previewImageUrl
                  ? undefined
                  : `linear-gradient(160deg, rgba(10, 16, 28, 0.22), rgba(3, 7, 18, 0.32)), url(${previewSampleImage})`,
              }}
            >
              {previewImageUrl ? (
                <img
                  className="subtitle-stage-image"
                  src={previewImageUrl}
                  alt="Preview exacto de subtitulos"
                />
              ) : (
                <div
                  className="subtitle-caption"
                  style={{
                    fontFamily: `${form.subtitle_font_name}, sans-serif`,
                  }}
                >
                  ESTA FRASE SE CONSTRUYE EN VIVO
                </div>
              )}
              {previewLoading && <div className="subtitle-preview-status">Actualizando preview exacto...</div>}
            </div>
          </div>
          {previewError && <p className="subtitle-preview-error">{previewError}</p>}
        </div>
      </div>
    </section>
  );
}
