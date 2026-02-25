import { Fragment, useEffect, useRef, useState } from "react";
import { Check, X } from "lucide-react";
import type { BusyAction, ClipArtifact } from "../types";

interface PublishDraft {
  caption: string;
  title: string;
  scheduleTime: string;
}

interface PublishResult {
  success: boolean;
  message: string;
}

interface ClipReviewTableProps {
  clips: ClipArtifact[];
  onOpenClip: (clip: ClipArtifact) => void;
  onReviewClip: (clipIndex: number, approved: boolean | null, rejectionReason?: string) => void;
  approvedCount: number;
  canPublish: boolean;
  busyAction: BusyAction;
  onPublish: () => void;
  clipCaptions: Record<number, string>;
  clipCaptionLoading: Set<number>;
  onPublishClip: (clipIndex: number, caption: string, title: string, scheduleTime: string | null) => Promise<{ success: boolean; post_id: string }>;
  onPublishAllApproved: (publishData: Array<{ clipIndex: number; caption: string; title: string; scheduleTime: string | null }>) => Promise<Array<{ clip_id: string; success: boolean; post_id: string; error: string }>>;
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
  clipCaptions,
  clipCaptionLoading,
  onPublishClip,
  onPublishAllApproved,
}: ClipReviewTableProps) {
  const [rejectionDrafts, setRejectionDrafts] = useState<Record<number, string>>({});
  const [expandedRows, setExpandedRows] = useState<Set<number>>(new Set());
  const [publishDrafts, setPublishDrafts] = useState<Record<number, PublishDraft>>({});
  const [publishingClips, setPublishingClips] = useState<Set<number>>(new Set());
  const [publishResults, setPublishResults] = useState<Record<number, PublishResult>>({});
  const [bulkPublishing, setBulkPublishing] = useState(false);
  const [bulkResult, setBulkResult] = useState<PublishResult | null>(null);
  const prevCaptionsRef = useRef<Record<number, string>>({});

  // Sync captions into publish drafts when they arrive
  useEffect(() => {
    const prev = prevCaptionsRef.current;
    for (const [idxStr, caption] of Object.entries(clipCaptions)) {
      const idx = Number(idxStr);
      if (caption && caption !== prev[idx]) {
        setPublishDrafts((drafts) => {
          if (drafts[idx]?.caption) return drafts; // already customised by user
          return {
            ...drafts,
            [idx]: {
              caption,
              title: caption.slice(0, 150),
              scheduleTime: drafts[idx]?.scheduleTime ?? "",
            },
          };
        });
      }
    }
    prevCaptionsRef.current = clipCaptions;
  }, [clipCaptions]);

  // Clear drafts/results for clips no longer approved
  useEffect(() => {
    const approvedSet = new Set(clips.filter((c) => c.review_status === "approved").map((c) => c.index));
    setPublishDrafts((prev) => {
      const next: Record<number, PublishDraft> = {};
      for (const [idx, draft] of Object.entries(prev)) {
        if (approvedSet.has(Number(idx))) next[Number(idx)] = draft;
      }
      return next;
    });
    setPublishResults((prev) => {
      const next: Record<number, PublishResult> = {};
      for (const [idx, result] of Object.entries(prev)) {
        if (approvedSet.has(Number(idx))) next[Number(idx)] = result;
      }
      return next;
    });
  }, [clips]);

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

  const updateDraft = (clipIndex: number, patch: Partial<PublishDraft>) => {
    setPublishDrafts((prev) => ({
      ...prev,
      [clipIndex]: { ...(prev[clipIndex] ?? { caption: "", title: "", scheduleTime: "" }), ...patch },
    }));
  };

  const handlePublishSingle = async (clipIndex: number) => {
    const draft = publishDrafts[clipIndex];
    if (!draft?.caption) return;
    setPublishingClips((prev) => new Set([...prev, clipIndex]));
    setPublishResults((prev) => ({ ...prev, [clipIndex]: { success: false, message: "" } }));
    try {
      await onPublishClip(clipIndex, draft.caption, draft.title, draft.scheduleTime || null);
      setPublishResults((prev) => ({ ...prev, [clipIndex]: { success: true, message: "Publicado" } }));
    } catch (err) {
      setPublishResults((prev) => ({
        ...prev,
        [clipIndex]: { success: false, message: err instanceof Error ? err.message : "Error al publicar" },
      }));
    } finally {
      setPublishingClips((prev) => {
        const next = new Set(prev);
        next.delete(clipIndex);
        return next;
      });
    }
  };

  const handleBulkPublish = async () => {
    const approvedClips = clips.filter((c) => c.review_status === "approved");
    const publishData = approvedClips
      .filter((c) => publishDrafts[c.index]?.caption)
      .map((c) => ({
        clipIndex: c.index,
        caption: publishDrafts[c.index].caption,
        title: publishDrafts[c.index].title,
        scheduleTime: publishDrafts[c.index].scheduleTime || null,
      }));

    if (publishData.length === 0) return;

    setBulkPublishing(true);
    setBulkResult(null);
    try {
      const results = await onPublishAllApproved(publishData);
      const successCount = results.filter((r) => r.success).length;
      const failCount = results.length - successCount;
      setBulkResult({ success: failCount === 0, message: `OK=${successCount}, FAIL=${failCount}` });
      for (const r of results) {
        const idx = Number(r.clip_id.split(":")[1]);
        if (!Number.isNaN(idx)) {
          setPublishResults((prev) => ({
            ...prev,
            [idx]: { success: r.success, message: r.success ? "Publicado" : r.error },
          }));
        }
      }
    } catch (err) {
      setBulkResult({ success: false, message: err instanceof Error ? err.message : "Error al publicar" });
    } finally {
      setBulkPublishing(false);
    }
  };

  const approvedWithCaptions = clips.filter(
    (c) => c.review_status === "approved" && publishDrafts[c.index]?.caption,
  ).length;

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

        {approvedCount > 0 && (
          <button
            className="btn btn-mini btn-publish"
            onClick={handleBulkPublish}
            disabled={bulkPublishing || approvedWithCaptions === 0}
            type="button"
            title={approvedWithCaptions === 0 ? "Espera a que se generen los captions" : undefined}
          >
            {bulkPublishing ? "Publicando..." : `Post all approved (${approvedCount})`}
          </button>
        )}

        {bulkResult && (
          <span className={`publish-result ${bulkResult.success ? "publish-result--ok" : "publish-result--error"}`}>
            {bulkResult.message}
          </span>
        )}
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

                {/* Rejection form */}
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

                {/* Publish form for approved clips */}
                {clip.review_status === "approved" && (
                  <tr className="review-row-publish">
                    <td colSpan={8}>
                      <div className="publish-form">
                        {clipCaptionLoading.has(clip.index) ? (
                          <p className="publish-loading">Generando caption con IA...</p>
                        ) : (
                          <>
                            <div className="publish-form-caption">
                              <label htmlFor={`caption-${clip.index}`}>Caption</label>
                              <textarea
                                id={`caption-${clip.index}`}
                                value={publishDrafts[clip.index]?.caption ?? ""}
                                onChange={(e) => updateDraft(clip.index, { caption: e.target.value })}
                                placeholder="Caption para TikTok..."
                                rows={3}
                                maxLength={2200}
                              />
                            </div>
                            <div className="publish-form-row">
                              <div className="publish-form-group">
                                <label htmlFor={`title-${clip.index}`}>Titulo</label>
                                <input
                                  id={`title-${clip.index}`}
                                  type="text"
                                  value={publishDrafts[clip.index]?.title ?? ""}
                                  onChange={(e) => updateDraft(clip.index, { title: e.target.value })}
                                  maxLength={150}
                                  placeholder="Titulo del video..."
                                />
                              </div>
                              <div className="publish-form-group">
                                <label htmlFor={`schedule-${clip.index}`}>Programar (opcional)</label>
                                <input
                                  id={`schedule-${clip.index}`}
                                  type="datetime-local"
                                  value={publishDrafts[clip.index]?.scheduleTime ?? ""}
                                  onChange={(e) => updateDraft(clip.index, { scheduleTime: e.target.value })}
                                />
                              </div>
                              <div className="publish-form-action">
                                <button
                                  className="btn btn-publish"
                                  onClick={() => handlePublishSingle(clip.index)}
                                  disabled={
                                    publishingClips.has(clip.index) ||
                                    !publishDrafts[clip.index]?.caption
                                  }
                                  type="button"
                                >
                                  {publishingClips.has(clip.index) ? "Publicando..." : "Post a TikTok"}
                                </button>
                              </div>
                            </div>
                            {publishResults[clip.index]?.message && (
                              <span
                                className={`publish-result ${publishResults[clip.index].success ? "publish-result--ok" : "publish-result--error"}`}
                              >
                                {publishResults[clip.index].message}
                              </span>
                            )}
                          </>
                        )}
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
