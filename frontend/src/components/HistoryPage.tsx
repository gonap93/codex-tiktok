import { useCallback, useEffect, useState } from "react";
import type { ClipArtifact, JobState } from "../types";

const API_BASE = "";

function parseApiError(body: unknown): string {
  if (!body || typeof body !== "object") return "Error al publicar.";
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail === "string") return detail;
  return "Error al publicar.";
}

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

function reviewLabel(status: string): string {
  switch (status) {
    case "approved":
      return "Aprobado";
    case "rejected":
      return "Rechazado";
    default:
      return "Pendiente";
  }
}

function publishLabel(status: string): string {
  switch (status) {
    case "publishing":
      return "Publicando";
    case "published":
      return "Publicado";
    case "failed":
      return "Error";
    default:
      return "Sin publicar";
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

interface PublishDraft {
  caption: string;
  title: string;
  scheduleTime: string;
}

export function HistoryPage() {
  const [jobs, setJobs] = useState<JobState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedJob, setSelectedJob] = useState<JobState | null>(null);
  const [expandedClipIndex, setExpandedClipIndex] = useState<number | null>(null);
  const [publishDrafts, setPublishDrafts] = useState<Record<string, PublishDraft>>({});
  const [publishingClipKey, setPublishingClipKey] = useState<string | null>(null);
  const [publishError, setPublishError] = useState<string | null>(null);

  const fetchJobs = useCallback(async () => {
    const response = await fetch(`${API_BASE}/api/jobs`);
    if (!response.ok) throw new Error("No se pudieron cargar los jobs.");
    const data = (await response.json()) as JobState[];
    setJobs(data.sort((a, b) => b.created_at.localeCompare(a.created_at)));
    return data;
  }, []);

  const fetchJob = useCallback(async (jobId: string): Promise<JobState> => {
    const response = await fetch(`${API_BASE}/api/jobs/${jobId}`);
    if (!response.ok) throw new Error("No se pudo cargar el job.");
    return response.json() as Promise<JobState>;
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        setLoading(true);
        await fetchJobs();
        if (!cancelled) setError("");
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Error cargando historial.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    load();
    return () => {
      cancelled = true;
    };
  }, [fetchJobs]);

  const refetchSelectedJob = useCallback(async () => {
    if (!selectedJob) return;
    try {
      const updated = await fetchJob(selectedJob.job_id);
      setSelectedJob(updated);
      await fetchJobs();
    } catch {
      // keep current selectedJob
    }
  }, [selectedJob, fetchJob, fetchJobs]);

  const handlePublishClip = useCallback(
    async (jobId: string, clip: ClipArtifact, draft: PublishDraft) => {
      const key = `${jobId}:${clip.index}`;
      setPublishingClipKey(key);
      setPublishError(null);
      try {
        const response = await fetch(`${API_BASE}/api/publish/tiktok`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            clip_id: key,
            caption: draft.caption,
            title: draft.title,
            schedule_time: draft.scheduleTime || null,
          }),
        });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) {
          setPublishError(parseApiError(body));
          return;
        }
        await refetchSelectedJob();
      } catch (err) {
        setPublishError(err instanceof Error ? err.message : "Error de red.");
      } finally {
        setPublishingClipKey(null);
      }
    },
    [refetchSelectedJob],
  );

  const updatePublishDraft = useCallback((key: string, patch: Partial<PublishDraft>) => {
    setPublishDrafts((prev) => ({
      ...prev,
      [key]: { ...(prev[key] ?? { caption: "", title: "", scheduleTime: "" }), ...patch },
    }));
  }, []);

  useEffect(() => {
    if (selectedJob) {
      setExpandedClipIndex(null);
      setPublishError(null);
    }
  }, [selectedJob?.job_id]);

  return (
    <div className="history-page">
      <h2 className="page-title">Historial de jobs</h2>
      <p className="page-subtitle">Todos los jobs y clips generados en esta sesion.</p>

      {error && <div className="notice notice-error">{error}</div>}

      {loading && <p className="empty">Cargando historial...</p>}

      {!loading && jobs.length === 0 && !error && (
        <div className="history-table-wrap">
          <p className="history-empty">No hay jobs registrados todavia.</p>
        </div>
      )}

      {!loading && jobs.length > 0 && (
        <div className="history-table-wrap">
          <table className="history-table">
            <thead>
              <tr>
                <th>Job ID</th>
                <th>YouTube URL</th>
                <th>Estado</th>
                <th>Clips</th>
                <th>Creado</th>
                <th>Acciones</th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((job) => (
                <tr key={job.job_id}>
                  <td>
                    <code style={{ fontSize: "0.82rem" }}>{job.job_id}</code>
                  </td>
                  <td>
                    <span className="history-url" title={job.youtube_url}>
                      {job.youtube_url}
                    </span>
                  </td>
                  <td>
                    <span className={`status-chip status-${job.status}`}>{statusLabel(job.status)}</span>
                  </td>
                  <td>{job.clips.length}</td>
                  <td style={{ whiteSpace: "nowrap" }}>{formatDate(job.created_at)}</td>
                  <td>
                    <button
                      className="btn btn-mini btn-outline"
                      onClick={() => setSelectedJob(job)}
                    >
                      Ver detalles
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {selectedJob && (
        <div className="modal" onClick={() => setSelectedJob(null)}>
          <section className="history-modal-card" onClick={(e) => e.stopPropagation()}>
            <header>
              <h3>Job {selectedJob.job_id}</h3>
              <button className="btn btn-mini btn-outline" onClick={() => setSelectedJob(null)}>
                Cerrar
              </button>
            </header>
            <div className="history-modal-body">
              <div className="history-detail-grid">
                <div className="history-detail-item">
                  <span className="label">Estado</span>
                  <span className="value">
                    <span className={`status-chip status-${selectedJob.status}`}>
                      {statusLabel(selectedJob.status)}
                    </span>
                  </span>
                </div>
                <div className="history-detail-item">
                  <span className="label">Progreso</span>
                  <span className="value">{Math.round(selectedJob.progress)}%</span>
                </div>
                <div className="history-detail-item">
                  <span className="label">YouTube URL</span>
                  <span className="value">{selectedJob.youtube_url}</span>
                </div>
                <div className="history-detail-item">
                  <span className="label">Clips solicitados</span>
                  <span className="value">{selectedJob.requested_clips_count}</span>
                </div>
                <div className="history-detail-item">
                  <span className="label">Duracion</span>
                  <span className="value">
                    {selectedJob.requested_min_clip_seconds}s - {selectedJob.requested_max_clip_seconds}s
                  </span>
                </div>
                <div className="history-detail-item">
                  <span className="label">Resolucion</span>
                  <span className="value">
                    {selectedJob.requested_output_width}x{selectedJob.requested_output_height}
                  </span>
                </div>
                <div className="history-detail-item">
                  <span className="label">Fuente</span>
                  <span className="value">{selectedJob.requested_subtitle_font_name}</span>
                </div>
                <div className="history-detail-item">
                  <span className="label">Creado</span>
                  <span className="value">{formatDate(selectedJob.created_at)}</span>
                </div>
              </div>

              {selectedJob.error && (
                <div className="notice notice-error">{selectedJob.error}</div>
              )}

              {selectedJob.clips.length > 0 && (
                <>
                  <h4 style={{ margin: "8px 0 4px", fontSize: "0.95rem" }}>
                    Clips ({selectedJob.clips.length})
                  </h4>
                  <div className="history-clips-list">
                    {selectedJob.clips.map((clip) => {
                      const clipKey = `${selectedJob.job_id}:${clip.index}`;
                      const draft = publishDrafts[clipKey] ?? {
                        caption: clip.transcript_excerpt || clip.title,
                        title: clip.title,
                        scheduleTime: "",
                      };
                      const isExpanded = expandedClipIndex === clip.index;
                      const canPublish =
                        clip.publish_status !== "published" && clip.publish_status !== "publishing";
                      const isPublishing = publishingClipKey === clipKey;
                      return (
                        <div className="history-clip-block" key={clip.index}>
                          <div className="history-clip-row">
                            <strong>{clip.index}</strong>
                            <span className="history-clip-title" title={clip.title}>
                              {clip.title}
                            </span>
                            <span className="history-clip-badges">
                              <span
                                className={`status-chip ${
                                  clip.review_status === "approved"
                                    ? "status-completed"
                                    : clip.review_status === "rejected"
                                      ? "status-failed"
                                      : "status-queued"
                                }`}
                                style={{ padding: "4px 8px", fontSize: "0.72rem" }}
                              >
                                {reviewLabel(clip.review_status)}
                              </span>
                              <span
                                className={`status-chip ${
                                  clip.publish_status === "published"
                                    ? "status-completed"
                                    : clip.publish_status === "failed"
                                      ? "status-failed"
                                      : "status-queued"
                                }`}
                                style={{ padding: "4px 8px", fontSize: "0.72rem" }}
                              >
                                {publishLabel(clip.publish_status)}
                              </span>
                            </span>
                            <span className="history-clip-actions">
                              <button
                                type="button"
                                className="btn btn-mini btn-outline"
                                onClick={() =>
                                  setExpandedClipIndex((prev) => (prev === clip.index ? null : clip.index))
                                }
                              >
                                {isExpanded ? "Ocultar" : "Ver clip / Detalles"}
                              </button>
                              {canPublish && (
                                <button
                                  type="button"
                                  className="btn btn-mini btn-primary"
                                  onClick={() => {
                                    if (!isExpanded) setExpandedClipIndex(clip.index);
                                    setPublishDrafts((p) => ({
                                      ...p,
                                      [clipKey]: p[clipKey] ?? {
                                        caption: clip.transcript_excerpt || clip.title,
                                        title: clip.title,
                                        scheduleTime: "",
                                      },
                                    }));
                                  }}
                                >
                                  Publicar en TikTok
                                </button>
                              )}
                            </span>
                          </div>
                          {isExpanded && (
                            <div className="history-clip-expanded">
                              <div className="history-clip-video-wrap">
                                <video
                                  className="history-clip-video"
                                  src={clip.url}
                                  controls
                                  poster={clip.thumbnail_url || undefined}
                                  preload="metadata"
                                />
                              </div>
                              <div className="history-clip-details">
                                <h5 className="history-clip-details-title">Detalles</h5>
                                <dl className="history-clip-details-dl">
                                  <dt>Duración</dt>
                                  <dd>{clip.duration}s</dd>
                                  <dt>Score viral</dt>
                                  <dd>{clip.score != null ? Math.round(clip.score) : "—"}</dd>
                                  <dt>Inicio / Fin</dt>
                                  <dd>
                                    {clip.start != null && clip.end != null
                                      ? `${clip.start.toFixed(1)}s – ${clip.end.toFixed(1)}s`
                                      : "—"}
                                  </dd>
                                  {clip.publish_status === "published" && clip.tiktok_post_id && (
                                    <>
                                      <dt>Post ID TikTok</dt>
                                      <dd>{clip.tiktok_post_id}</dd>
                                    </>
                                  )}
                                  {clip.publish_status === "failed" && clip.publish_error && (
                                    <>
                                      <dt>Error al publicar</dt>
                                      <dd className="history-clip-error">{clip.publish_error}</dd>
                                    </>
                                  )}
                                </dl>
                                {clip.transcript_excerpt && (
                                  <>
                                    <h5 className="history-clip-details-title">Transcripción</h5>
                                    <p className="history-clip-transcript">{clip.transcript_excerpt}</p>
                                  </>
                                )}
                              </div>
                              {canPublish && (
                                <div className="history-clip-publish-form">
                                  <h5 className="history-clip-details-title">Publicar en TikTok</h5>
                                  {publishError && (
                                    <div className="notice notice-error" style={{ marginBottom: 8 }}>
                                      {publishError}
                                    </div>
                                  )}
                                  <div className="history-clip-form-row">
                                    <label htmlFor={`history-caption-${clipKey}`}>Caption</label>
                                    <textarea
                                      id={`history-caption-${clipKey}`}
                                      value={draft.caption}
                                      onChange={(e) => updatePublishDraft(clipKey, { caption: e.target.value })}
                                      rows={3}
                                      placeholder="Caption para TikTok..."
                                      className="history-clip-input"
                                    />
                                  </div>
                                  <div className="history-clip-form-row">
                                    <label htmlFor={`history-title-${clipKey}`}>Título</label>
                                    <input
                                      id={`history-title-${clipKey}`}
                                      type="text"
                                      value={draft.title}
                                      onChange={(e) => updatePublishDraft(clipKey, { title: e.target.value })}
                                      placeholder="Título del video"
                                      className="history-clip-input"
                                      maxLength={90}
                                    />
                                  </div>
                                  <div className="history-clip-form-row">
                                    <label htmlFor={`history-schedule-${clipKey}`}>Programar (opcional)</label>
                                    <input
                                      id={`history-schedule-${clipKey}`}
                                      type="datetime-local"
                                      value={draft.scheduleTime}
                                      onChange={(e) =>
                                        updatePublishDraft(clipKey, { scheduleTime: e.target.value })
                                      }
                                      className="history-clip-input"
                                    />
                                  </div>
                                  <button
                                    type="button"
                                    className="btn btn-primary"
                                    disabled={isPublishing || !draft.caption.trim()}
                                    onClick={() => handlePublishClip(selectedJob.job_id, clip, draft)}
                                  >
                                    {isPublishing ? "Publicando..." : "Publicar ahora"}
                                  </button>
                                </div>
                              )}
                            </div>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </>
              )}

              {selectedJob.logs.length > 0 && (
                <>
                  <h4 style={{ margin: "8px 0 4px", fontSize: "0.95rem" }}>Logs</h4>
                  <div className="terminal-logs" style={{ maxHeight: "200px" }}>
                    {[...selectedJob.logs].reverse().map((line, idx) => (
                      <p className="terminal-line" key={`${line}-${idx}`}>
                        {line}
                      </p>
                    ))}
                  </div>
                </>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
