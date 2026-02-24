import { useEffect, useState } from "react";
import type { JobState } from "../types";

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

export function HistoryPage() {
  const [jobs, setJobs] = useState<JobState[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedJob, setSelectedJob] = useState<JobState | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function fetchJobs() {
      try {
        setLoading(true);
        const response = await fetch(`${API_BASE}/api/jobs`);
        if (!response.ok) throw new Error("No se pudieron cargar los jobs.");
        const data = (await response.json()) as JobState[];
        if (!cancelled) {
          setJobs(data.sort((a, b) => b.created_at.localeCompare(a.created_at)));
          setError("");
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Error cargando historial.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    fetchJobs();
    return () => {
      cancelled = true;
    };
  }, []);

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
                    {selectedJob.clips.map((clip) => (
                      <div className="history-clip-row" key={clip.index}>
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
                      </div>
                    ))}
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
