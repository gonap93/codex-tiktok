import type { ClipArtifact } from "../types";

interface ClipModalProps {
  clip: ClipArtifact;
  onClose: () => void;
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
      return "No publicado";
  }
}

export function ClipModal({ clip, onClose }: ClipModalProps) {
  return (
    <div className="modal" onClick={onClose}>
      <section className="modal-card" onClick={(event) => event.stopPropagation()}>
        <header>
          <h3>
            {clip.index}. {clip.title}
          </h3>
          <button className="btn btn-mini btn-outline" onClick={onClose} type="button">
            Cerrar
          </button>
        </header>
        <div
          className="modal-video-wrap"
          style={
            clip.thumbnail_url
              ? { backgroundImage: `url(${clip.thumbnail_url})` }
              : undefined
          }
        >
          <video
            src={clip.url}
            poster={clip.thumbnail_url || undefined}
            controls
            autoPlay
            preload="metadata"
            playsInline
          />
        </div>
        <div className="modal-meta">
          <p><strong>Titulo:</strong> {clip.title}</p>
          <p><strong>Duracion:</strong> {clip.duration.toFixed(1)}s</p>
          <p><strong>Inicio:</strong> {clip.start.toFixed(2)}s</p>
          <p><strong>Fin:</strong> {clip.end.toFixed(2)}s</p>
          <p><strong>Score:</strong> {clip.score > 0 ? clip.score.toFixed(1) : "No disponible"}</p>
          <p><strong>Ranking:</strong> #{clip.index}</p>
          <p><strong>Estado review:</strong> {reviewLabel(clip.review_status)}</p>
          <p><strong>Estado publicacion:</strong> {publishLabel(clip.publish_status)}</p>
          <p><strong>Excerpt:</strong> {clip.transcript_excerpt?.trim() || "No disponible"}</p>
        </div>
      </section>
    </div>
  );
}
