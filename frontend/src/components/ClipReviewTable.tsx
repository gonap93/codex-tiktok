import { Fragment, useState } from "react";
import { Check, X } from "lucide-react";
import type { BusyAction, ClipArtifact } from "../types";

interface ClipReviewTableProps {
  clips: ClipArtifact[];
  onOpenClip: (clip: ClipArtifact) => void;
  onReviewClip: (clipIndex: number, approved: boolean | null, rejectionReason?: string) => void;
  approvedCount: number;
  canPublish: boolean;
  busyAction: BusyAction;
  onPublish: () => void;
}

function reviewChipClass(status: ClipArtifact["review_status"]): string {
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

function publishLabel(status: ClipArtifact["publish_status"]): string {
  switch (status) {
    case "publishing":
      return "Publicando";
    case "published":
      return "Publicado";
    case "failed":
      return "Error";
    default:
      return "";
  }
}

export function ClipReviewTable({
  clips,
  onOpenClip,
  onReviewClip,
  approvedCount,
  canPublish,
  busyAction,
  onPublish,
}: ClipReviewTableProps) {
  const [rejectionDrafts, setRejectionDrafts] = useState<Record<number, string>>({});
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());

  const handleSelectAll = () => {
    for (const clip of clips) {
      if (clip.review_status !== "approved") {
        onReviewClip(clip.index, true);
      }
    }
  };

  const handleDeselectAll = () => {
    for (const clip of clips) {
      if (clip.review_status === "approved") {
        onReviewClip(clip.index, false);
      }
    }
  };

  const handleResetAll = () => {
    for (const clip of clips) {
      if (clip.review_status === "approved") {
        onReviewClip(clip.index, null);
      }
    }
  };

  const toggleExpand = (clipIndex: number) => {
    setExpandedRows((prev) => {
      const next = new Set(prev);
      if (next.has(clipIndex)) {
        next.delete(clipIndex);
      } else {
        next.add(clipIndex);
      }
      return next;
    });
  };

  const handleReject = (clipIndex: number) => {
    const reason = (rejectionDrafts[clipIndex] || "").trim();
    onReviewClip(clipIndex, false, reason);
    setExpandedRows((prev) => {
      const next = new Set(prev);
      next.delete(clipIndex);
      return next;
    });
  };

  return (
    <div className="review-table-wrap">
      <div className="review-table-toolbar">
        <button className="btn btn-mini btn-ghost" onClick={handleSelectAll} type="button">
          Aprobar todos
        </button>
        <button className="btn btn-mini btn-ghost" onClick={handleDeselectAll} type="button">
          Desaprobar todos
        </button>
        <button className="btn btn-mini btn-ghost" onClick={handleResetAll} type="button">
          Resetear todos
        </button>
      </div>

      <div className="review-table-scroll">
        <table className="review-table">
          <thead>
            <tr>
              <th>#</th>
              <th>Thumbnail</th>
              <th>Titulo</th>
              <th>Rango</th>
              <th>Duracion</th>
              <th>Score</th>
              <th>Estado</th>
              <th>Acciones</th>
            </tr>
          </thead>
          <tbody>
            {clips.map((clip) => (
              <Fragment key={clip.index}>
                <tr
                  className={`review-row${clip.review_status === "approved" ? " review-row--approved" : ""}${clip.review_status === "rejected" ? " review-row--rejected" : ""}`}
                >
                  <td>{clip.index}</td>
                  <td>
                    <button
                      className="review-thumb"
                      onClick={() => onOpenClip(clip)}
                      style={
                        clip.thumbnail_url
                          ? { backgroundImage: `url(${clip.thumbnail_url})` }
                          : undefined
                      }
                      type="button"
                    >
                      {clip.thumbnail_url ? (
                        <img src={clip.thumbnail_url} alt={`Clip ${clip.index}`} />
                      ) : (
                        <span className="thumb-placeholder">&#9654;</span>
                      )}
                    </button>
                  </td>
                  <td
                    className={
                      clip.review_status === "rejected" ? "review-title--rejected" : ""
                    }
                  >
                    {clip.title}
                  </td>
                  <td>
                    {clip.start.toFixed(1)}s &rarr; {clip.end.toFixed(1)}s
                  </td>
                  <td>{clip.duration.toFixed(1)}s</td>
                  <td>{clip.score > 0 ? clip.score.toFixed(0) : "\u2014"}</td>
                  <td>
                    <span
                      className={`status-chip status-chip--sm ${reviewChipClass(clip.review_status)}`}
                    >
                      {reviewLabel(clip.review_status)}
                    </span>
                    {clip.publish_status !== "not_published" && (
                      <span className="review-publish-chip">{publishLabel(clip.publish_status)}</span>
                    )}
                  </td>
                  <td>
                    <div className="review-action-btns">
                      <button
                        className={`btn btn-mini ${clip.review_status === "approved" ? "btn-ok" : "btn-outline"}`}
                        onClick={() => onReviewClip(clip.index, true)}
                        type="button"
                        title="Aprobar"
                      >
                        <Check size={14} />
                      </button>
                      <button
                        className={`btn btn-mini ${clip.review_status === "rejected" ? "btn-bad" : "btn-outline"}`}
                        onClick={() => toggleExpand(clip.index)}
                        type="button"
                        title="Rechazar"
                      >
                        <X size={14} />
                      </button>
                      {clip.review_status !== "pending" && (
                        <button
                          className="btn btn-mini btn-ghost"
                          onClick={() => onReviewClip(clip.index, null)}
                          type="button"
                          title="Resetear a pendiente"
                        >
                          &#8634;
                        </button>
                      )}
                      <button
                        className="btn btn-mini btn-ghost"
                        onClick={() => onOpenClip(clip)}
                        type="button"
                        title="Ver detalles del clip"
                      >
                        Ver Detalles
                      </button>
                    </div>
                  </td>
                </tr>
                {expandedRows.has(clip.index) && (
                  <tr className="review-row-expanded">
                    <td colSpan={8}>
                      <div className="review-rejection-form">
                        <input
                          type="text"
                          value={rejectionDrafts[clip.index] || ""}
                          onChange={(e) =>
                            setRejectionDrafts((d) => ({ ...d, [clip.index]: e.target.value }))
                          }
                          placeholder="Motivo de rechazo (opcional)"
                          maxLength={300}
                        />
                        <button
                          className="btn btn-mini btn-bad"
                          onClick={() => handleReject(clip.index)}
                          type="button"
                        >
                          Confirmar
                        </button>
                      </div>
                    </td>
                  </tr>
                )}
              </Fragment>
            ))}
          </tbody>
        </table>
      </div>

      <div className="review-sticky-footer">
        <span className="review-footer-count">
          {approvedCount} clip{approvedCount !== 1 ? "s" : ""} aprobado{approvedCount !== 1 ? "s" : ""}
        </span>
        <button
          className="btn btn-publish"
          disabled={!canPublish || busyAction !== ""}
          onClick={onPublish}
          type="button"
        >
          {busyAction === "publish"
            ? "Publicando..."
            : `Publicar aprobados${canPublish ? ` (${approvedCount})` : ""}`}
        </button>
      </div>
    </div>
  );
}
