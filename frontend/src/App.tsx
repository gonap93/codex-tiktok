import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ClipModal } from "./components/ClipModal";
import { JobConfigPanel } from "./components/JobConfigPanel";
import { PipelinePanel } from "./components/PipelinePanel";
import { SetupInstructions } from "./components/SetupInstructions";
import { ThemeToggle } from "./components/ThemeToggle";
import type {
  BusyAction,
  ClipArtifact,
  FormState,
  JobState,
  JobStatus,
  NoticeType,
  ThemeMode,
} from "./types";

const API_BASE = "";
const THEME_STORAGE_KEY = "clipmaker-theme";
const PREVIEW_SUBTITLE_TEXT = "ESTA FRASE SE CONSTRUYE EN VIVO";

const FONT_OPTIONS = ["Inter", "Montserrat", "Poppins", "Arial"];

const DEFAULT_FORM: FormState = {
  youtube_url: "",
  clips_count: 4,
  min_clip_seconds: 12,
  max_clip_seconds: 95,
  subtitle_font_name: "Inter",
  subtitle_margin_horizontal: 56,
  subtitle_margin_vertical: 46,
  output_width: 1080,
  output_height: 1920,
};

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (saved === "dark" || saved === "light") return saved;
  return "light";
}

function parseApiError(body: unknown): string {
  if (!body || typeof body !== "object") return "Ocurrio un error en la API.";
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    const joined = detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          const msg = (item as { msg?: unknown }).msg;
          if (typeof msg === "string") return msg;
        }
        return null;
      })
      .filter(Boolean)
      .join(" | ");
    if (joined) return joined;
  }
  const nested = (body as { error?: { message?: unknown } }).error?.message;
  if (typeof nested === "string") return nested;
  return "Ocurrio un error en la API.";
}

async function apiJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, init);
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(parseApiError(body));
  }
  return body as T;
}

export default function App() {
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [jobId, setJobId] = useState<string>("");
  const [job, setJob] = useState<JobState | null>(null);
  const [notice, setNotice] = useState<string>("");
  const [noticeType, setNoticeType] = useState<NoticeType>("info");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [busyAction, setBusyAction] = useState<BusyAction>("");
  const [modalClip, setModalClip] = useState<ClipArtifact | null>(null);
  const [previewImageUrl, setPreviewImageUrl] = useState<string>("");
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [previewError, setPreviewError] = useState<string>("");

  const streamRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const retryRef = useRef<number>(0);
  const lastUpdateRef = useRef<number>(0);
  const statusRef = useRef<JobStatus | null>(null);

  const progress = Math.max(0, Math.min(100, job?.progress ?? 0));

  const approvedCount = useMemo(
    () => (job?.clips ?? []).filter((clip) => clip.review_status === "approved").length,
    [job?.clips],
  );

  const rejectedCount = useMemo(
    () => (job?.clips ?? []).filter((clip) => clip.review_status === "rejected").length,
    [job?.clips],
  );

  const allRejected = useMemo(
    () => (job?.clips?.length ?? 0) > 0 && rejectedCount === (job?.clips?.length ?? 0),
    [job?.clips?.length, rejectedCount],
  );

  const canPublish = Boolean(job && job.status === "completed" && approvedCount > 0);
  const canRegenerate = Boolean(job && job.status === "completed" && allRejected);
  const canRestart = Boolean(job && (job.status === "running" || job.status === "failed"));
  const inPipelineStage = Boolean(jobId);

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    window.localStorage.setItem(THEME_STORAGE_KEY, theme);
  }, [theme]);

  const clearReconnectTimer = () => {
    if (reconnectTimerRef.current !== null) {
      window.clearTimeout(reconnectTimerRef.current);
      reconnectTimerRef.current = null;
    }
  };

  const closeStream = useCallback(() => {
    if (streamRef.current) {
      streamRef.current.close();
      streamRef.current = null;
    }
    clearReconnectTimer();
  }, []);

  const connectStream = useCallback(
    (targetJobId: string) => {
      closeStream();

      const source = new EventSource(`${API_BASE}/api/jobs/${targetJobId}/stream`);
      streamRef.current = source;

      source.onmessage = (event) => {
        try {
          const next = JSON.parse(event.data) as JobState;
          retryRef.current = 0;
          const parsed = Date.parse(next.updated_at);
          lastUpdateRef.current = Number.isNaN(parsed) ? Date.now() : parsed;
          statusRef.current = next.status;
          setJob(next);
          if (next.error) {
            setNoticeType("error");
            setNotice(next.error);
          }
        } catch {
          setNoticeType("error");
          setNotice("No se pudo procesar un evento en vivo.");
        }
      };

      source.onerror = () => {
        const currentStatus = statusRef.current;
        if (currentStatus === "completed" || currentStatus === "failed") return;
        retryRef.current += 1;

        if (retryRef.current > 8) {
          setNoticeType("error");
          setNotice("Conexion inestable con updates en vivo. Usa Reiniciar proceso.");
          return;
        }

        if (streamRef.current) {
          streamRef.current.close();
          streamRef.current = null;
        }

        clearReconnectTimer();
        reconnectTimerRef.current = window.setTimeout(() => connectStream(targetJobId), 2200);
      };
    },
    [closeStream],
  );

  useEffect(() => {
    return () => {
      closeStream();
    };
  }, [closeStream]);

  useEffect(() => {
    const interval = window.setInterval(() => {
      if (!job || job.status !== "running") return;
      if (!lastUpdateRef.current) return;
      const staleMs = Date.now() - lastUpdateRef.current;
      if (staleMs > 180_000) {
        setNoticeType("error");
        setNotice(`No hay avances hace ${Math.floor(staleMs / 1000)}s. Usa Reiniciar proceso.`);
      }
    }, 10_000);

    return () => window.clearInterval(interval);
  }, [job]);

  useEffect(() => {
    if (inPipelineStage) return;
    const controller = new AbortController();
    const timer = window.setTimeout(async () => {
      try {
        setPreviewLoading(true);
        const payload = await apiJson<{ preview_url: string }>("/api/preview/subtitle-frame", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            subtitle_font_name: form.subtitle_font_name,
            subtitle_margin_horizontal: form.subtitle_margin_horizontal,
            subtitle_margin_vertical: form.subtitle_margin_vertical,
            output_width: form.output_width,
            output_height: form.output_height,
            subtitle_text: PREVIEW_SUBTITLE_TEXT,
          }),
          signal: controller.signal,
        });
        setPreviewImageUrl(payload.preview_url);
        setPreviewError("");
      } catch (error) {
        if (controller.signal.aborted) return;
        setPreviewError(error instanceof Error ? error.message : "No se pudo generar preview exacto.");
      } finally {
        if (!controller.signal.aborted) {
          setPreviewLoading(false);
        }
      }
    }, 280);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [
    inPipelineStage,
    form.subtitle_font_name,
    form.subtitle_margin_horizontal,
    form.subtitle_margin_vertical,
    form.output_width,
    form.output_height,
  ]);

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const validateForm = () => {
    if (!form.youtube_url.trim()) {
      throw new Error("Ingresa un link de YouTube.");
    }
    if (form.min_clip_seconds > form.max_clip_seconds) {
      throw new Error("La duracion minima no puede ser mayor que la maxima.");
    }
    if (form.subtitle_margin_horizontal < 20 || form.subtitle_margin_vertical < 20) {
      throw new Error("Pad X y Pad Y deben ser >= 20.");
    }
    if (
      !Number.isInteger(form.min_clip_seconds) ||
      !Number.isInteger(form.max_clip_seconds) ||
      !Number.isInteger(form.subtitle_margin_horizontal) ||
      !Number.isInteger(form.subtitle_margin_vertical) ||
      !Number.isInteger(form.output_width) ||
      !Number.isInteger(form.output_height)
    ) {
      throw new Error("Formato invalido: todos los campos numericos deben ser enteros.");
    }
    if (
      form.output_width < 320 ||
      form.output_height < 320 ||
      form.output_width > 3840 ||
      form.output_height > 3840
    ) {
      throw new Error("El tamaño de salida debe estar entre 320 y 3840.");
    }
    if (form.output_width % 2 !== 0 || form.output_height % 2 !== 0) {
      throw new Error("Width y Height deben ser numeros pares.");
    }
  };

  const resetRunUi = () => {
    setJob(null);
    setModalClip(null);
    setNotice("");
    retryRef.current = 0;
    lastUpdateRef.current = 0;
    statusRef.current = null;
  };

  const handleStartNew = () => {
    closeStream();
    setJobId("");
    resetRunUi();
  };

  const handleCreateJob = async () => {
    try {
      validateForm();
      setSubmitting(true);
      resetRunUi();
      const payload = await apiJson<{ job_id: string }>("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setJobId(payload.job_id);
      connectStream(payload.job_id);
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : "No se pudo iniciar el job.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleReview = async (clipIndex: number, approved: boolean, rejectionReason = "") => {
    if (!jobId) return;
    const trimmedReason = rejectionReason.trim();
    if (!approved && trimmedReason.length < 4) {
      setNoticeType("error");
      setNotice("Para rechazar un clip, agrega un motivo de al menos 4 caracteres.");
      return;
    }
    try {
      const updated = await apiJson<JobState>(`/api/jobs/${jobId}/clips/${clipIndex}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved,
          rejection_reason: approved ? null : trimmedReason,
        }),
      });
      setJob(updated);
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : "No se pudo actualizar el clip.");
    }
  };

  const handleRegenerate = async () => {
    if (!jobId) return;
    try {
      validateForm();
      setBusyAction("regenerate");
      const updated = await apiJson<JobState>(`/api/jobs/${jobId}/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      setJob(updated);
      setNoticeType("info");
      setNotice("Regeneracion iniciada usando cache.");
      connectStream(jobId);
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : "No se pudo regenerar.");
    } finally {
      setBusyAction("");
    }
  };

  const handleRestart = async () => {
    if (!jobId) return;
    try {
      validateForm();
      setBusyAction("restart");
      const updated = await apiJson<JobState>(`/api/jobs/${jobId}/restart`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...form, use_cache: true }),
      });
      setJob(updated);
      setNoticeType("info");
      setNotice("Proceso reiniciado.");
      connectStream(jobId);
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : "No se pudo reiniciar.");
    } finally {
      setBusyAction("");
    }
  };

  const handlePublish = async () => {
    if (!jobId) return;
    try {
      setBusyAction("publish");
      const result = await apiJson<{ published_count: number; failed_count: number }>(
        `/api/jobs/${jobId}/publish-approved`,
        { method: "POST" },
      );
      setNoticeType("info");
      setNotice(`Publicacion finalizada. OK=${result.published_count}, FAIL=${result.failed_count}.`);
    } catch (error) {
      setNoticeType("error");
      setNotice(error instanceof Error ? error.message : "No se pudo publicar.");
    } finally {
      setBusyAction("");
    }
  };

  const logs = useMemo(() => [...(job?.logs ?? [])].reverse(), [job?.logs]);

  return (
    <div className="app">
      <div className="ambient ambient-a" />
      <div className="ambient ambient-b" />

      <header className="topbar">
        <div>
          <p className="eyebrow">ClipMaker</p>
          <h1>{inPipelineStage ? "Pipeline Monitor" : "Studio Control Deck"}</h1>
          {inPipelineStage && (
            <p className="lead">
              Seguimiento en vivo del pipeline, revision de clips y publicacion de aprobados.
            </p>
          )}
        </div>
        <ThemeToggle
          theme={theme}
          onToggle={() => setTheme((prev) => (prev === "light" ? "dark" : "light"))}
        />
      </header>

      {!inPipelineStage && (
        <section className="layout layout-setup">
          <SetupInstructions />
        </section>
      )}

      <main className={`layout ${inPipelineStage ? "layout-pipeline" : "layout-setup"}`}>
        {!inPipelineStage ? (
          <JobConfigPanel
            form={form}
            fontOptions={FONT_OPTIONS}
            submitting={submitting}
            notice={notice}
            noticeType={noticeType}
            previewImageUrl={previewImageUrl}
            previewLoading={previewLoading}
            previewError={previewError}
            onUpdateForm={updateForm}
            onCreateJob={handleCreateJob}
            onFieldFormatError={(message) => {
              setNoticeType("error");
              setNotice(message);
            }}
          />
        ) : (
          <PipelinePanel
            jobId={jobId}
            job={job}
            progress={progress}
            notice={notice}
            noticeType={noticeType}
            busyAction={busyAction}
            approvedCount={approvedCount}
            rejectedCount={rejectedCount}
            canRestart={canRestart}
            canRegenerate={canRegenerate}
            canPublish={canPublish}
            logs={logs}
            onRestart={handleRestart}
            onRegenerate={handleRegenerate}
            onPublish={handlePublish}
            onStartNew={handleStartNew}
            onOpenClip={setModalClip}
            onReviewClip={handleReview}
          />
        )}
      </main>

      {modalClip && <ClipModal clip={modalClip} onClose={() => setModalClip(null)} />}
    </div>
  );
}
