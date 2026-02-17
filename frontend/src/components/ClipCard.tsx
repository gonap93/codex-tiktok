import { useEffect, useState } from "react";
import type { ClipArtifact } from "../types";

interface ClipCardProps {
  clip: ClipArtifact;
  onOpen: (clip: ClipArtifact) => void;
  onReview: (clipIndex: number, approved: boolean, rejectionReason?: string) => void;
  publishLabel: (status: ClipArtifact["publish_status"]) => string;
}

export function ClipCard({ clip, onOpen, onReview, publishLabel }: ClipCardProps) {
  const [rejectionReasonDraft, setRejectionReasonDraft] = useState<string>(clip.rejection_reason || "");

  useEffect(() => {
    setRejectionReasonDraft(clip.rejection_reason || "");
  }, [clip.index, clip.rejection_reason]);

  return (
    <article className="clip-card" key={clip.url}>
      <button className="thumb-frame" onClick={() => onOpen(clip)}>
        {clip.thumbnail_url ? (
          <img src={clip.thumbnail_url} alt={`Clip ${clip.index}`} className="thumb-image" />
        ) : (
          <span className="thumb-placeholder">Abrir preview</span>
        )}
      </button>

      <div className="clip-meta">
        <h3>
          {clip.index}. {clip.title}
        </h3>
        <p>
          {clip.start.toFixed(1)}s - {clip.end.toFixed(1)}s - {clip.duration.toFixed(2)}s
        </p>

        <div className="review-actions">
          <button
            className={`btn btn-mini ${clip.review_status === "approved" ? "btn-ok" : "btn-outline"}`}
            onClick={() => onReview(clip.index, true)}
          >
            Aprobar
          </button>
          <button
            className={`btn btn-mini ${clip.review_status === "rejected" ? "btn-bad" : "btn-outline"}`}
            onClick={() => onReview(clip.index, false, rejectionReasonDraft)}
          >
            No aprobar
          </button>
        </div>
        <label className="rejection-field">
          <span>Motivo de rechazo</span>
          <input
            type="text"
            value={rejectionReasonDraft}
            onChange={(event) => setRejectionReasonDraft(event.target.value)}
            placeholder="Ej: Hook flojo, tema repetido, poco claro..."
            maxLength={300}
          />
        </label>

        <span className="publish-chip">{publishLabel(clip.publish_status)}</span>
      </div>
    </article>
  );
}
