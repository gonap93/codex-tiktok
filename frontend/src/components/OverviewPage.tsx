import { useEffect, useMemo, useState } from "react";
import type { ClipArtifact, JobState } from "../types";

const API_BASE = "";

function statusLabel(status?: JobState["status"]): string {
  switch (status) {
    case "queued":
      return "En cola";
    case "running":
      return "En proceso";
    case "completed":
      return "Completado";
    case "failed":
      return "Fallo";
    default:
      return "Sin iniciar";
  }
}

function reviewBadgeClass(status: ClipArtifact["review_status"]): string {
  switch (status) {
    case "approved":
      return "status-completed";
    case "rejected":
      return "status-failed";
    default:
      return "status-queued";
  }
}

function reviewLabel(status: ClipArtifact["review_status"]): string {
  switch (status) {
    case "approved":
      return "Aprobado";
    case "rejected":
      return "Rechazado";
    default:
      return "Pendiente";
  }
}

function formatDate(isoString: string): string {
  try {
    const date = new Date(isoString);
    return date.toLocaleString("es-AR", {
      day: "2-digit",
      month: "short",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return isoString;
  }
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  const secs = Math.round(seconds % 60);
  return `${mins}m ${secs}s`;
}

interface DayActivity {
  label: string;
  count: number;
  pct: number;
}

function computeDailyActivity(jobs: JobState[]): DayActivity[] {
  const days: DayActivity[] = [];
  const now = new Date();
  const dayLabels = ["Dom", "Lun", "Mar", "Mie", "Jue", "Vie", "Sab"];

  const counts: Record<string, number> = {};
  for (let i = 6; i >= 0; i--) {
    const d = new Date(now);
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    counts[key] = 0;
  }

  for (const job of jobs) {
    for (const clip of job.clips) {
      const jobDate = job.created_at.slice(0, 10);
      if (jobDate in counts) {
        counts[jobDate]++;
      }
    }
  }

  const maxCount = Math.max(1, ...Object.values(counts));
  for (const [dateStr, count] of Object.entries(counts)) {
    const d = new Date(dateStr + "T00:00:00");
    days.push({
      label: dayLabels[d.getDay()],
      count,
      pct: (count / maxCount) * 100,
    });
  }

  return days;
}

interface OverviewPageProps {
  onNavigate?: (page: "clipper") => void;
}

export function OverviewPage({ onNavigate }: OverviewPageProps) {
  const [jobs, setJobs] = useState<JobState[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    async function fetchJobs() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/api/jobs`);
        if (!response.ok) throw new Error("Failed to fetch");
        const data = (await response.json()) as JobState[];
        if (!cancelled) {
          setJobs(data.sort((a, b) => b.created_at.localeCompare(a.created_at)));
        }
      } catch {
        // Silently handle — overview shows empty state
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchJobs();
    return () => {
      cancelled = true;
    };
  }, []);

  const totalClips = useMemo(
    () => jobs.reduce((sum, j) => sum + j.clips.length, 0),
    [jobs],
  );

  const totalDuration = useMemo(
    () => jobs.reduce((sum, j) => sum + j.clips.reduce((s, c) => s + c.duration, 0), 0),
    [jobs],
  );

  const publishedClips = useMemo(
    () => jobs.reduce((sum, j) => sum + j.clips.filter((c) => c.publish_status === "published").length, 0),
    [jobs],
  );

  const recentClips = useMemo(() => {
    const all: (ClipArtifact & { jobId: string })[] = [];
    for (const job of jobs) {
      for (const clip of job.clips) {
        all.push({ ...clip, jobId: job.job_id });
      }
    }
    return all.slice(0, 6);
  }, [jobs]);

  const recentJobs = useMemo(() => jobs.slice(0, 5), [jobs]);

  const dailyActivity = useMemo(() => computeDailyActivity(jobs), [jobs]);

  if (loading) {
    return (
      <div className="overview-page">
        <h2 className="page-title">Overview</h2>
        <p className="empty">Cargando...</p>
      </div>
    );
  }

  if (jobs.length === 0) {
    return (
      <div className="overview-page">
        <h2 className="page-title">Overview</h2>
        <div className="overview-empty-state">
          <div className="overview-empty-icon">
            <svg
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              width="56"
              height="56"
            >
              <circle cx="6" cy="6" r="3" />
              <circle cx="6" cy="18" r="3" />
              <line x1="20" y1="4" x2="8.12" y2="15.88" />
              <line x1="14.47" y1="14.48" x2="20" y2="20" />
              <line x1="8.12" y1="8.12" x2="12" y2="12" />
            </svg>
          </div>
          <h3>Pega un link de YouTube para generar tus primeros clips</h3>
          <p>Configura los parametros y genera clips optimizados para redes sociales.</p>
          {onNavigate && (
            <button className="btn btn-primary overview-cta" onClick={() => onNavigate("clipper")}>
              Ir al Clipper
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className="overview-page">
      <h2 className="page-title">Overview</h2>
      <p className="page-subtitle">Resumen de tu actividad de generacion de clips.</p>

      {/* Metrics */}
      <div className="overview-metrics">
        <article className="metric-card">
          <strong>{totalClips}</strong>
          <span>Total clips</span>
        </article>
        <article className="metric-card">
          <strong>{jobs.length}</strong>
          <span>Total jobs</span>
        </article>
        <article className="metric-card">
          <strong>{formatDuration(totalDuration)}</strong>
          <span>Duracion procesada</span>
        </article>
        <article className="metric-card">
          <strong>{publishedClips}</strong>
          <span>Clips publicados</span>
        </article>
      </div>

      {/* Activity */}
      <section className="overview-section">
        <h3>Actividad (7 dias)</h3>
        <div className="activity-chart">
          {dailyActivity.map((day, i) => (
            <div className="activity-bar-wrap" key={i}>
              <span className="activity-count">{day.count > 0 ? day.count : ""}</span>
              <div className="activity-bar" style={{ height: `${Math.max(day.pct, 4)}%` }} />
              <span className="activity-label">{day.label}</span>
            </div>
          ))}
        </div>
      </section>

      {/* Recent clips */}
      {recentClips.length > 0 && (
        <section className="overview-section">
          <h3>Clips recientes</h3>
          <div className="overview-clips-grid">
            {recentClips.map((clip) => (
              <article className="overview-clip-card" key={`${clip.jobId}-${clip.index}`}>
                <div className="overview-clip-thumb">
                  {clip.thumbnail_url ? (
                    <img src={clip.thumbnail_url} alt={clip.title} className="thumb-image" />
                  ) : (
                    <span className="thumb-placeholder">Preview</span>
                  )}
                </div>
                <div className="overview-clip-info">
                  <p className="overview-clip-title" title={clip.title}>{clip.title}</p>
                  <div className="overview-clip-meta">
                    <span>{clip.duration.toFixed(1)}s</span>
                    <span className={`status-chip status-chip--sm ${reviewBadgeClass(clip.review_status)}`}>
                      {reviewLabel(clip.review_status)}
                    </span>
                  </div>
                </div>
              </article>
            ))}
          </div>
        </section>
      )}

      {/* Recent jobs */}
      {recentJobs.length > 0 && (
        <section className="overview-section">
          <h3>Jobs recientes</h3>
          <div className="overview-jobs-list">
            {recentJobs.map((job) => (
              <div className="overview-job-row" key={job.job_id}>
                <div className="overview-job-info">
                  <span className="overview-job-url" title={job.youtube_url}>
                    {job.youtube_url}
                  </span>
                  <span className="overview-job-date">{formatDate(job.created_at)}</span>
                </div>
                <div className="overview-job-badges">
                  <span className={`status-chip status-chip--sm status-${job.status}`}>
                    {statusLabel(job.status)}
                  </span>
                  <span className="overview-job-clips">{job.clips.length} clips</span>
                </div>
              </div>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
