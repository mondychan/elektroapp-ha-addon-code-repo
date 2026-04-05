import React from "react";
import ThemeToggle from "../common/ThemeToggle";

interface AppHeaderProps {
  pageMode: "overview" | "detail";
  setPageMode: (mode: "overview" | "detail") => void;
  theme: "light" | "dark";
  setTheme: (theme: "light" | "dark") => void;
}

const AppHeader: React.FC<AppHeaderProps> = ({ pageMode, setPageMode, theme, setTheme }) => {
  return (
    <header className="app-header">
      <div>
        <h1>Elektroapp</h1>
        <div className="subhead">Ceny, nakup a prodej energie v realnem case</div>
      </div>
      <div className="header-toggles">
        <div className="view-mode-toggle" role="tablist" aria-label="Rezimu stranky">
          <button
            type="button"
            className={`view-mode-btn ${pageMode === "overview" ? "is-active" : ""}`}
            onClick={() => setPageMode("overview")}
            role="tab"
            aria-selected={pageMode === "overview"}
          >
            Prehled
          </button>
          <button
            type="button"
            className={`view-mode-btn ${pageMode === "detail" ? "is-active" : ""}`}
            onClick={() => setPageMode("detail")}
            role="tab"
            aria-selected={pageMode === "detail"}
          >
            Detail
          </button>
        </div>
        <ThemeToggle theme={theme} setTheme={setTheme} />
      </div>
    </header>
  );
};

export default AppHeader;
