import { Clock, PanelLeftClose, PanelLeft } from "lucide-react";
import type { PageType } from "../types";

interface SidebarProps {
  activePage: PageType;
  onNavigate: (page: PageType) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
  runningJobId?: string;
}

export function Sidebar({ activePage, onNavigate, collapsed, onToggleCollapse, runningJobId }: SidebarProps) {
  return (
    <aside className={`sidebar${collapsed ? " sidebar--collapsed" : ""}`}>
      <div className="sidebar-top-row">
        <div className="sidebar-user">
          <img src="/blipr_logo.png" alt="Blipr" className="sidebar-logo" />
          <span className="sidebar-username">Blipr</span>
        </div>
        <button
          className="sidebar-collapse-btn"
          onClick={onToggleCollapse}
          type="button"
          aria-label={collapsed ? "Expandir sidebar" : "Colapsar sidebar"}
        >
          {collapsed ? <PanelLeft size={18} /> : <PanelLeftClose size={18} />}
        </button>
      </div>

      <nav className="sidebar-nav">
        <p className="sidebar-section-label">Menu</p>
        <button
          className={`sidebar-item ${activePage === "overview" ? "sidebar-item--active" : ""}`}
          onClick={() => onNavigate("overview")}
          type="button"
        >
          <svg
            className="sidebar-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <rect x="3" y="3" width="7" height="7" rx="1" />
            <rect x="14" y="3" width="7" height="7" rx="1" />
            <rect x="3" y="14" width="7" height="7" rx="1" />
            <rect x="14" y="14" width="7" height="7" rx="1" />
          </svg>
          <span>Overview</span>
        </button>
        <button
          className={`sidebar-item ${activePage === "clipper" ? "sidebar-item--active" : ""}`}
          onClick={() => onNavigate("clipper")}
          type="button"
        >
          <svg
            className="sidebar-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="6" cy="6" r="3" />
            <circle cx="6" cy="18" r="3" />
            <line x1="20" y1="4" x2="8.12" y2="15.88" />
            <line x1="14.47" y1="14.48" x2="20" y2="20" />
            <line x1="8.12" y1="8.12" x2="12" y2="12" />
          </svg>
          <span>Blipr</span>
        </button>
        <button
          className={`sidebar-item ${activePage === "channels" ? "sidebar-item--active" : ""}`}
          onClick={() => onNavigate("channels")}
          type="button"
        >
          <svg
            className="sidebar-icon"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71" />
            <path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71" />
          </svg>
          <span>Channels</span>
        </button>
        <button
          className={`sidebar-item ${activePage === "historial" ? "sidebar-item--active" : ""}`}
          onClick={() => onNavigate("historial")}
          type="button"
        >
          <Clock className="sidebar-icon" size={20} />
          <span>Historial</span>
        </button>
      </nav>

      {runningJobId && (
        <button
          className="sidebar-running-job"
          onClick={() => onNavigate("clipper")}
          type="button"
        >
          <span className="sidebar-running-dot" />
          <span>1 job en curso</span>
        </button>
      )}
    </aside>
  );
}
