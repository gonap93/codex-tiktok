import type { ClipArtifact } from "../types";

interface ClipModalProps {
  clip: ClipArtifact;
  onClose: () => void;
}

export function ClipModal({ clip, onClose }: ClipModalProps) {
  return (
    <div className="modal" onClick={onClose}>
      <section className="modal-card" onClick={(event) => event.stopPropagation()}>
        <header>
          <h3>
            {clip.index}. {clip.title}
          </h3>
          <button className="btn btn-mini btn-outline" onClick={onClose}>
            Cerrar
          </button>
        </header>
        <video src={clip.url} controls autoPlay preload="metadata" playsInline />
      </section>
    </div>
  );
}
