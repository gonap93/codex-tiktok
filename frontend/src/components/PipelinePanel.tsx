import { useEffect, useRef } from "react";
import { ClipReviewTable } from "./ClipReviewTable";
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
  onReviewClip: (clipIndex: number, approved: boolean | null, rejectionReason?: string) => void;
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

function logLevelClass(line: string): string {
  if (line.includes("[ERROR]")) return "terminal-line--error";
  if (line.includes("[SUCCESS]")) return "terminal-line--success";
  return "";
}

function TerminalLogs({ logs }: { logs: string[] }) {
  const containerRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [logs]);

  return (
    <div className="terminal-logs" ref={containerRef}>
      {logs.length === 0 && <p className="terminal-empty">Sin logs por ahora.</p>}
      {logs.map((line, idx) => (
        <p className={`terminal-line ${logLevelClass(line)}`} key={`${idx}-${line}`}>{line}</p>
      ))}
    </div>
  );
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
  const isError = job?.status === "failed";
  const isCompleted = job?.status === "completed";

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
        {isError && (
          <button className="btn btn-primary" disabled={!canRestart || busyAction !== ""} onClick={onRestart}>
            {busyAction === "restart" ? "Reiniciando..." : "Reiniciar proceso"}
          </button>
        )}

        {isCompleted && (
          <button className="btn btn-ghost" disabled={!canRegenerate || busyAction !== ""} onClick={onRegenerate}>
            {busyAction === "regenerate" ? "Regenerando..." : "Regenerar clips"}
          </button>
        )}

        <button
          className={`btn ${isError ? "btn-outline btn-outline--danger" : "btn-outline"}`}
          disabled={busyAction !== ""}
          onClick={onStartNew}
        >
          {isError ? "Eliminar y empezar nuevo" : "Nuevo job"}
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

      {(job?.clips ?? []).length > 0 && (
        <ClipReviewTable
          clips={job!.clips}
          onOpenClip={onOpenClip}
          onReviewClip={onReviewClip}
          approvedCount={approvedCount}
          canPublish={canPublish}
          busyAction={busyAction}
          onPublish={onPublish}
        />
      )}

      {!job?.clips?.length && <p className="empty">Todavia no hay clips para revisar.</p>}

      <div className="terminal-section">
        <h3>Logs</h3>
        <TerminalLogs logs={logs} />
      </div>
    </section>
  );
}
