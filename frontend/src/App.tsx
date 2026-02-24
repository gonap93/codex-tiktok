import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { ChannelsPage } from "./components/ChannelsPage";
import { ClipModal } from "./components/ClipModal";
import { Header } from "./components/Header";
import { HistoryPage } from "./components/HistoryPage";
import { JobWizard } from "./components/JobWizard";
import { OverviewPage } from "./components/OverviewPage";
import { PipelinePanel } from "./components/PipelinePanel";
import { SearchModal } from "./components/SearchModal";
import { Sidebar } from "./components/Sidebar";
import type {
  BusyAction,
  ClipArtifact,
  FormState,
  JobState,
  JobStatus,
  NoticeType,
  PageType,
  ThemeMode,
} from "./types";

const API_BASE = "";
const THEME_STORAGE_KEY = "clipmaker-theme";
const SIDEBAR_COLLAPSED_KEY = "clipmaker-sidebar-collapsed";

const FONT_OPTIONS = ["Bebas Neue", "Montserrat", "Oswald", "Roboto Condensed", "Anton"];

const DEFAULT_FORM: FormState = {
  youtube_url: "",
  clips_count: 4,
  ai_choose_count: false,
  content_genre: "",
  specific_moments_instruction: "",
  subtitle_font_name: "Bebas Neue",
  subtitle_margin_horizontal: 56,
  subtitle_margin_vertical: 46,
  output_width: 1080,
  output_height: 1920,
  subtitles_enabled: true,
  subtitle_preset: "",
  aspect_ratio: "9:16",
  video_language: "es",
  subtitle_font_size: 36,
  subtitle_position_x: 50,
  subtitle_position_y: 85,
};

function getInitialTheme(): ThemeMode {
  if (typeof window === "undefined") return "light";
  const saved = window.localStorage.getItem(THEME_STORAGE_KEY);
  if (saved === "dark" || saved === "light") return saved;
  return "light";
}

function getInitialSidebarCollapsed(): boolean {
  if (typeof window === "undefined") return false;
  return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "true";
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

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function buildJobPayload(form: FormState): Omit<FormState, "aspect_ratio" | "subtitle_position_x" | "subtitle_position_y"> {
  const { aspect_ratio, subtitle_position_x, subtitle_position_y, ...rest } = form;
  const MARGIN_MIN = 20;
  const MARGIN_H_MAX = 300; // backend request limit
  const MARGIN_V_MAX = 220; // keep subtitles inside visible frame
  const y = clamp(subtitle_position_y, 5, 95);
  const yNorm = (y - 5) / 90;
  const computedMarginHorizontal = Math.min(
    MARGIN_H_MAX,
    Math.max(
      MARGIN_MIN,
      Math.round(form.output_width * (1 - (2 * Math.abs(subtitle_position_x - 50)) / 100) / 2),
    ),
  );
  const computedMarginVertical = Math.round(MARGIN_V_MAX - yNorm * (MARGIN_V_MAX - MARGIN_MIN));

  return {
    ...rest,
    subtitle_margin_horizontal: computedMarginHorizontal,
    subtitle_margin_vertical: clamp(computedMarginVertical, MARGIN_MIN, MARGIN_V_MAX),
  };
}

export default function App() {
  const [theme, setTheme] = useState<ThemeMode>(getInitialTheme);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(getInitialSidebarCollapsed);
  const [activePage, setActivePage] = useState<PageType>("overview");
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [jobId, setJobId] = useState<string>("");
  const [job, setJob] = useState<JobState | null>(null);
  const [notice, setNotice] = useState<string>("");
  const [noticeType, setNoticeType] = useState<NoticeType>("info");
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [busyAction, setBusyAction] = useState<BusyAction>("");
  const [modalClip, setModalClip] = useState<ClipArtifact | null>(null);
  const [searchOpen, setSearchOpen] = useState<boolean>(false);

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
  const isJobRunning = Boolean(jobId && job && (job.status === "running" || job.status === "queued"));

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
          // Close the SSE connection on terminal states
          if (next.status === "completed" || next.status === "failed") {
            source.close();
            streamRef.current = null;
            clearReconnectTimer();
          }
        } catch {
          setNoticeType("error");
          setNotice("No se pudo procesar un evento en vivo.");
        }
      };

      source.onerror = () => {
        const currentStatus = statusRef.current;
        if (currentStatus === "completed" || currentStatus === "failed") {
          source.close();
          streamRef.current = null;
          clearReconnectTimer();
          return;
        }
        retryRef.current += 1;

        if (retryRef.current > 8) {
          setNoticeType("error");
          setNotice("Conexion inestable con updates en vivo.");
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

  const updateForm = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
  };

  const validateForm = () => {
    if (!form.youtube_url.trim()) {
      throw new Error("Ingresa un link de YouTube.");
    }
    if (
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
      throw new Error("El tamano de salida debe estar entre 320 y 3840.");
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
      const apiPayload = buildJobPayload(form);
      const payload = await apiJson<{ job_id: string }>("/api/jobs", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(apiPayload),
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

  const handleReview = async (clipIndex: number, approved: boolean | null, rejectionReason = "") => {
    if (!jobId) return;
    const trimmedReason = rejectionReason.trim();
    try {
      const updated = await apiJson<JobState>(`/api/jobs/${jobId}/clips/${clipIndex}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          approved,
          rejection_reason: approved === false ? (trimmedReason || null) : null,
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
      const apiPayload = buildJobPayload(form);
      const updated = await apiJson<JobState>(`/api/jobs/${jobId}/regenerate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(apiPayload),
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
      const apiPayload = buildJobPayload(form);
      const updated = await apiJson<JobState>(`/api/jobs/${jobId}/restart`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ...apiPayload, use_cache: true }),
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

  const loadJobFromHistory = useCallback(
    (selectedJob: JobState) => {
      setJobId(selectedJob.job_id);
      setJob(selectedJob);
      connectStream(selectedJob.job_id);
      setActivePage("clipper");
      setSearchOpen(false);
      setNotice("");
    },
    [connectStream],
  );

  const logs = useMemo(() => job?.logs ?? [], [job?.logs]);

  const toggleSidebarCollapsed = () => {
    setSidebarCollapsed((prev) => {
      const next = !prev;
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      return next;
    });
  };

  const sidebarWidth = sidebarCollapsed ? "64px" : "240px";

  return (
    <>
      <div className="app-layout" style={{ "--sidebar-width": sidebarWidth } as React.CSSProperties}>
        <Sidebar
          activePage={activePage}
          onNavigate={setActivePage}
          collapsed={sidebarCollapsed}
          onToggleCollapse={toggleSidebarCollapsed}
          runningJobId={isJobRunning ? jobId : ""}
        />

        <main className="main-content">
          <Header
            theme={theme}
            onToggleTheme={() => setTheme((prev) => (prev === "light" ? "dark" : "light"))}
            onOpenSearch={() => setSearchOpen(true)}
            runningJobId={isJobRunning ? jobId : ""}
            onGoToJob={() => setActivePage("clipper")}
          />

          {activePage === "clipper" && (
            <>
              {!inPipelineStage && (
                <JobWizard
                  form={form}
                  fontOptions={FONT_OPTIONS}
                  submitting={submitting}
                  notice={notice}
                  noticeType={noticeType}
                  onUpdateForm={updateForm}
                  onCreateJob={handleCreateJob}
                  onFieldFormatError={(message) => {
                    setNoticeType("error");
                    setNotice(message);
                  }}
                />
              )}

              {inPipelineStage && (
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
            </>
          )}

          {activePage === "overview" && <OverviewPage onNavigate={setActivePage} />}

          {activePage === "channels" && <ChannelsPage />}

          {activePage === "historial" && <HistoryPage />}
        </main>
      </div>

      {modalClip && <ClipModal clip={modalClip} onClose={() => setModalClip(null)} />}

      {searchOpen && (
        <SearchModal
          onClose={() => setSearchOpen(false)}
          onSelectJob={loadJobFromHistory}
        />
      )}
    </>
  );
}
