import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Search, Clock } from "lucide-react";
import type { JobState } from "../types";

const API_BASE = "";

interface SearchModalProps {
  onClose: () => void;
  onSelectJob: (job: JobState) => void;
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

export function SearchModal({ onClose, onSelectJob }: SearchModalProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState("");
  const [jobs, setJobs] = useState<JobState[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function fetchJobs() {
      try {
        const resp = await fetch(`${API_BASE}/api/jobs`);
        if (!resp.ok) return;
        const data = (await resp.json()) as JobState[];
        if (!cancelled) {
          setJobs(data.sort((a, b) => b.created_at.localeCompare(a.created_at)));
          setLoading(false);
        }
      } catch {
        if (!cancelled) setLoading(false);
      }
    }
    fetchJobs();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const filtered = useMemo(() => {
    if (!query.trim()) return jobs;
    const q = query.toLowerCase();
    return jobs.filter(
      (j) =>
        j.youtube_url.toLowerCase().includes(q) ||
        j.job_id.toLowerCase().includes(q) ||
        j.clips.some((c) => c.title.toLowerCase().includes(q)),
    );
  }, [jobs, query]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query]);

  const handleSelect = useCallback(
    (job: JobState) => {
      onSelectJob(job);
    },
    [onSelectJob],
  );

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        e.preventDefault();
        onClose();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveIndex((i) => Math.min(i + 1, filtered.length - 1));
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveIndex((i) => Math.max(i - 1, 0));
      }
      if (e.key === "Enter" && filtered[activeIndex]) {
        e.preventDefault();
        handleSelect(filtered[activeIndex]);
      }
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
  }, [filtered, activeIndex, onClose, handleSelect]);

  return (
    <div className="search-modal-backdrop" onClick={onClose}>
      <div className="search-modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="search-modal-input-wrap">
          <Search className="search-modal-icon" size={18} />
          <input
            ref={inputRef}
            className="search-modal-input"
            type="text"
            placeholder="Buscar jobs por URL, ID o titulo de clip..."
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>

        <div className="search-modal-results">
          {loading && <p className="search-modal-empty">Cargando...</p>}
          {!loading && filtered.length === 0 && (
            <p className="search-modal-empty">
              {query ? "Sin resultados" : "No hay jobs recientes"}
            </p>
          )}
          {!loading &&
            filtered.map((job, idx) => (
              <button
                key={job.job_id}
                className={`search-modal-result${idx === activeIndex ? " search-modal-result--active" : ""}`}
                onClick={() => handleSelect(job)}
                onMouseEnter={() => setActiveIndex(idx)}
                type="button"
              >
                <div className="search-modal-result-info">
                  <span className="search-modal-result-id">{job.job_id.slice(0, 8)}</span>
                  <span className="search-modal-result-url" title={job.youtube_url}>
                    {job.youtube_url.length > 50
                      ? job.youtube_url.slice(0, 50) + "..."
                      : job.youtube_url}
                  </span>
                </div>
                <div className="search-modal-result-meta">
                  <span className={`status-chip status-chip--sm status-${job.status}`}>
                    {statusLabel(job.status)}
                  </span>
                  <span className="search-modal-result-date">
                    <Clock size={12} />
                    {formatDate(job.created_at)}
                  </span>
                </div>
              </button>
            ))}
        </div>
      </div>
    </div>
  );
}
