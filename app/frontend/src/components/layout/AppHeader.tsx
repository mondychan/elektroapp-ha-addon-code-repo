import React from "react";
import ThemeToggle from "../common/ThemeToggle";

export type PageMode = "overview" | "costs" | "battery" | "hp" | "pnd" | "settings";

interface AppHeaderProps {
  pageMode: PageMode;
  setPageMode: (mode: PageMode) => void;
  theme: "light" | "dark" | "system";
  setTheme: (theme: "light" | "dark" | "system") => void;
}

const AppHeader: React.FC<AppHeaderProps> = ({ pageMode, setPageMode, theme, setTheme }) => {
  return (
    <header className="app-header">
      <div>
        <h1>Elektroapp</h1>
        <div className="subhead">Ceny, nákup a prodej energie v reálném čase</div>
      </div>
      <div className="header-toggles">
        <div className="view-mode-toggle" role="tablist" aria-label="Režim stránky">
          <button
            type="button"
            className={`view-mode-btn ${pageMode === "overview" ? "is-active" : ""}`}
            onClick={() => setPageMode("overview")}
            role="tab"
            aria-selected={pageMode === "overview"}
          >
            Přehled
          </button>
          <button
            type="button"
            className={`view-mode-btn ${pageMode === "costs" ? "is-active" : ""}`}
            onClick={() => setPageMode("costs")}
            role="tab"
            aria-selected={pageMode === "costs"}
          >
            Detail
          </button>
          <button
            type="button"
            className={`view-mode-btn ${pageMode === "pnd" ? "is-active" : ""}`}
            onClick={() => setPageMode("pnd")}
            role="tab"
            aria-selected={pageMode === "pnd"}
          >
            PND
          </button>
          <button
            type="button"
            className={`view-mode-btn ${pageMode === "hp" ? "is-active" : ""}`}
            onClick={() => setPageMode("hp")}
            role="tab"
            aria-selected={pageMode === "hp"}
          >
            HP
          </button>
        </div>
        <ThemeToggle theme={theme} setTheme={setTheme} />
      </div>
    </header>
  );
};

export default AppHeader;
