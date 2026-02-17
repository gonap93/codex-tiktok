import { ClipCard } from "./ClipCard";
import type { BusyAction, ClipArtifact, JobState, NoticeType } from "../types";

interface PipelinePanelProps {
  jobId: string;
  job: JobState | null;
  progress: number;
  notice: string;
  noticeType: NoticeType;
  busyAction: BusyAction;
  approvedCount: number;
  rejectedCount: number;
  canRestart: boolean;
  canRegenerate: boolean;
  canPublish: boolean;
  logs: string[];
  onRestart: () => void;
  onRegenerate: () => void;
  onPublish: () => void;
  onStartNew: () => void;
  onOpenClip: (clip: ClipArtifact) => void;
  onReviewClip: (clipIndex: number, approved: boolean, rejectionReason?: string) => void;
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

function publishLabel(status: ClipArtifact["publish_status"]): string {
  switch (status) {
    case "publishing":
      return "Publicando";
    case "published":
      return "Publicado";
    case "failed":
      return "Error publicacion";
    default:
      return "Sin publicar";
  }
}

export function PipelinePanel({
  jobId,
  job,
  progress,
  notice,
  noticeType,
  busyAction,
  approvedCount,
  rejectedCount,
  canRestart,
  canRegenerate,
  canPublish,
  logs,
  onRestart,
  onRegenerate,
  onPublish,
  onStartNew,
  onOpenClip,
  onReviewClip,
}: PipelinePanelProps) {
  return (
    <section className="panel output-panel">
      <div className="status-head">
        <div>
          <h2>Estado del pipeline</h2>
          {jobId && <p className="job-id">Job ID: {jobId}</p>}
        </div>
        <span className={`status-chip status-${job?.status ?? "queued"}`}>{statusLabel(job?.status)}</span>
      </div>

      <div className="progress-shell" role="progressbar" aria-valuenow={Math.round(progress)}>
        <div className="progress-fill" style={{ width: `${progress}%` }} />
      </div>
      <p className="step-line">
        {Math.round(progress)}% - {job?.current_step ?? "Sin actividad"}
      </p>

      {notice && <div className={`notice notice-${noticeType}`}>{notice}</div>}

      <div className="action-row">
        <button className="btn btn-secondary" disabled={!canRestart || busyAction !== ""} onClick={onRestart}>
          {busyAction === "restart" ? "Reiniciando..." : "Reiniciar proceso"}
        </button>

        <button className="btn btn-ghost" disabled={!canRegenerate || busyAction !== ""} onClick={onRegenerate}>
          {busyAction === "regenerate" ? "Regenerando..." : "Regenerar clips"}
        </button>

        <button className="btn btn-publish" disabled={!canPublish || busyAction !== ""} onClick={onPublish}>
          {busyAction === "publish"
            ? "Publicando..."
            : `Publicar aprobados${canPublish ? ` (${approvedCount})` : ""}`}
        </button>

        <button className="btn btn-outline" disabled={busyAction !== ""} onClick={onStartNew}>
          Nuevo job
        </button>
      </div>

      <div className="stats">
        <article>
          <strong>{job?.clips.length ?? 0}</strong>
          <span>Clips generados</span>
        </article>
        <article>
          <strong>{approvedCount}</strong>
          <span>Aprobados</span>
        </article>
        <article>
          <strong>{rejectedCount}</strong>
          <span>Rechazados</span>
        </article>
      </div>

      <div className="clips-grid">
        {(job?.clips ?? []).map((clip) => (
          <ClipCard
            key={clip.url}
            clip={clip}
            onOpen={onOpenClip}
            onReview={onReviewClip}
            publishLabel={publishLabel}
          />
        ))}
      </div>

      {!job?.clips?.length && <p className="empty">Todavia no hay clips para revisar.</p>}

      <div className="logs">
        <h3>Logs</h3>
        {logs.length === 0 && <p className="empty">Sin logs por ahora.</p>}
        {logs.map((line, idx) => (
          <p key={`${line}-${idx}`}>{line}</p>
        ))}
      </div>
    </section>
  );
}
