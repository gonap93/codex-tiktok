import { useEffect } from "react";
import { Search, Sun, Moon } from "lucide-react";
import type { ThemeMode } from "../types";

interface HeaderProps {
  theme: ThemeMode;
  onToggleTheme: () => void;
  onOpenSearch: () => void;
  runningJobId?: string;
  onGoToJob?: () => void;
}

export function Header({ theme, onToggleTheme, onOpenSearch, runningJobId, onGoToJob }: HeaderProps) {
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        onOpenSearch();
      }
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onOpenSearch]);

  return (
    <header className="dashboard-header">
      <div className="header-spacer" />

      <button className="header-search-btn" onClick={onOpenSearch} type="button">
        <Search size={16} />
        <span>Buscar...</span>
        <kbd className="header-search-kbd">&#8984;K</kbd>
      </button>

      {runningJobId && (
        <button className="header-running-chip" onClick={onGoToJob} type="button">
          <span className="header-running-dot" />
          <span>1 job en curso</span>
        </button>
      )}

      <button
        className="header-theme-btn"
        onClick={onToggleTheme}
        type="button"
        aria-label="Cambiar tema"
      >
        {theme === "dark" ? <Sun size={20} /> : <Moon size={20} />}
      </button>
    </header>
  );
}
