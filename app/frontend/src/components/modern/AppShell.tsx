import React, { useState } from "react";
import { PageMode } from "../layout/AppHeader";
import ThemeToggle from "../common/ThemeToggle";

type UiLayout = "modern" | "legacy";

interface AppShellProps {
  pageMode: PageMode;
  setPageMode: (mode: PageMode) => void;
  theme: "light" | "dark" | "system";
  setTheme: (theme: "light" | "dark" | "system") => void;
  uiLayout: UiLayout;
  setUiLayout: (layout: UiLayout) => void;
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  lastUpdatedAt?: string | null;
  refreshing?: boolean;
  onRefresh: () => void;
  version?: string | null;
  children: React.ReactNode;
}

const navItems: Array<{ id: PageMode; label: string; short?: string; icon: string; ariaLabel?: string }> = [
  { id: "overview", label: "Přehled", icon: "▦" },
  { id: "costs", label: "Detail", icon: "↗" },
  { id: "recommendations", label: "Doporučení", short: "Dop.", icon: "◌" },
  { id: "battery", label: "Baterie", icon: "▣" },
  { id: "solar", label: "Soláry / FV", icon: "☀" },
  { id: "pnd", label: "Síť / PND", ariaLabel: "PND", icon: "⌁" },
  { id: "monthly", label: "Měsíční přehled", icon: "▤" },
  { id: "stats", label: "Statistiky", icon: "▥" },
  { id: "settings", label: "Nastavení", icon: "⚙" },
];

const mobileItems = navItems.filter((item) => ["overview", "costs", "recommendations", "battery", "settings"].includes(item.id));

const formatUpdated = (value?: string | null) => {
  if (!value) return "Aktualizováno: -";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return "Aktualizováno: -";
  return `Aktualizováno: dnes ${dt.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" })}`;
};

const NavButton = ({
  item,
  active,
  onClick,
  compact = false,
}: {
  item: { id: PageMode; label: string; short?: string; icon: string; ariaLabel?: string };
  active: boolean;
  onClick: () => void;
  compact?: boolean;
}) => (
  <button
    type="button"
    className={`modern-nav-item ${active ? "is-active" : ""}`.trim()}
    onClick={onClick}
    aria-current={active ? "page" : undefined}
    aria-label={item.ariaLabel}
    aria-selected={active}
    role="tab"
    title={item.label}
  >
    <span className="modern-nav-item__icon" aria-hidden="true">{item.icon}</span>
    <span>{compact ? item.short || item.label : item.label}</span>
  </button>
);

const AppShell: React.FC<AppShellProps> = ({
  pageMode,
  setPageMode,
  theme,
  setTheme,
  uiLayout,
  setUiLayout,
  selectedDate,
  setSelectedDate,
  lastUpdatedAt,
  refreshing,
  onRefresh,
  version,
  children,
}) => {
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const handleNav = (mode: PageMode) => {
    setPageMode(mode);
    setSidebarOpen(false);
  };

  return (
    <div className="modern-app-shell">
      <aside className={`modern-sidebar ${sidebarOpen ? "is-open" : ""}`.trim()} aria-label="Hlavní navigace">
        <div className="modern-sidebar__brand">
          <span className="modern-brand-mark" aria-hidden="true">ϟ</span>
          <strong>Elektroapp</strong>
        </div>
        <nav className="modern-sidebar__nav" role="tablist" aria-label="Hlavní navigace">
          {navItems.map((item) => (
            <NavButton key={item.id} item={item} active={pageMode === item.id} onClick={() => handleNav(item.id)} />
          ))}
          <div className="modern-sidebar__divider" />
          <NavButton
            item={{ id: "hp", label: "HP", icon: "⌘" }}
            active={pageMode === "hp"}
            onClick={() => handleNav("hp")}
          />
        </nav>
        <div className="modern-sidebar__footer">
          <span>Home Assistant</span>
          <small>Verze doplňku: {version || "-"}</small>
        </div>
      </aside>

      {sidebarOpen ? <button type="button" className="modern-sidebar-backdrop" aria-label="Zavřít navigaci" onClick={() => setSidebarOpen(false)} /> : null}

      <div className="modern-workspace">
        <header className="modern-topbar">
          <div className="modern-topbar__title">
            <button type="button" className="modern-icon-button modern-menu-button" onClick={() => setSidebarOpen(true)} aria-label="Otevřít navigaci">
              ☰
            </button>
            <span className="modern-brand-mark" aria-hidden="true">ϟ</span>
            <strong>Elektroapp</strong>
          </div>

          <div className="modern-topbar__controls">
            <span className="modern-updated">{formatUpdated(lastUpdatedAt)}</span>
            <button type="button" className="modern-icon-button" onClick={onRefresh} disabled={refreshing} aria-label="Obnovit data" title="Obnovit data">
              {refreshing ? "…" : "↻"}
            </button>
            <label className="modern-date-control">
              <span className="sr-only">Datum</span>
              <input type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} />
            </label>
            <div className="modern-layout-toggle" role="group" aria-label="Vzhled aplikace">
              <button type="button" className={uiLayout === "modern" ? "is-active" : ""} onClick={() => setUiLayout("modern")}>
                Moderní
              </button>
              <button type="button" className={uiLayout === "legacy" ? "is-active" : ""} onClick={() => setUiLayout("legacy")}>
                Legacy
              </button>
            </div>
            <ThemeToggle theme={theme} setTheme={setTheme} />
          </div>
        </header>

        <main className="modern-content">{children}</main>
      </div>

      <nav className="modern-bottom-nav" aria-label="Mobilní navigace">
        {mobileItems.map((item) => (
          <NavButton key={item.id} item={item} active={pageMode === item.id} onClick={() => handleNav(item.id)} compact />
        ))}
      </nav>
    </div>
  );
};

export default AppShell;
