import React, { useEffect, useRef, useState } from "react";
import logoDark from "../../assets/elektroapp-logo-dark.png";
import logoLight from "../../assets/elektroapp-logo-light.png";
import ThemeToggle from "../common/ThemeToggle";
import { useLocalStorageState } from "../../hooks/useLocalStorageState";
import {
  IconBattery,
  IconBulb,
  IconCalendar,
  IconChart,
  IconGrid,
  IconGridTower,
  IconMenu,
  IconPin,
  IconPinOff,
  IconPlug,
  IconRefresh,
  IconSettings,
  IconSun,
  IconTable,
  IconTrend,
  IconX,
} from "./icons";

export type PageMode =
  | "overview"
  | "costs"
  | "recommendations"
  | "battery"
  | "solar"
  | "monthly"
  | "invoices"
  | "dip"
  | "stats"
  | "hp"
  | "pnd"
  | "settings";

interface AppShellProps {
  pageMode: PageMode;
  setPageMode: (mode: PageMode) => void;
  theme: "light" | "dark" | "system";
  setTheme: (theme: "light" | "dark" | "system") => void;
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  lastUpdatedAt?: string | null;
  refreshing?: boolean;
  onRefresh: () => void;
  version?: string | null;
  children: React.ReactNode;
}

type NavItem = {
  id: PageMode;
  label: string;
  icon: React.ReactNode;
  ariaLabel?: string;
};

const navItems: NavItem[] = [
  { id: "overview", label: "Přehled", icon: <IconGrid /> },
  { id: "costs", label: "Detail", icon: <IconChart /> },
  { id: "recommendations", label: "Doporučení", icon: <IconBulb /> },
  { id: "battery", label: "Baterie", icon: <IconBattery /> },
  { id: "solar", label: "Soláry / FV", icon: <IconSun /> },
  { id: "pnd", label: "Síť / PND", ariaLabel: "PND", icon: <IconGridTower /> },
  { id: "dip", label: "Distribuční portál", ariaLabel: "DIP", icon: <IconGridTower /> },
  { id: "monthly", label: "Měsíční přehled", icon: <IconTable /> },
  { id: "invoices", label: "Vyúčtování", icon: <IconTable /> },
  { id: "stats", label: "Statistiky", icon: <IconTrend /> },
  { id: "settings", label: "Nastavení", icon: <IconSettings /> },
];

const BrandLogo = ({ className = "" }: { className?: string }) => (
  <span className={`modern-brand-logo ${className}`.trim()} role="img" aria-label="Elektroapp">
    <img className="modern-brand-logo__image modern-brand-logo__image--dark" src={logoDark} alt="" aria-hidden="true" />
    <img className="modern-brand-logo__image modern-brand-logo__image--light" src={logoLight} alt="" aria-hidden="true" />
  </span>
);

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
}: {
  item: NavItem;
  active: boolean;
  onClick: () => void;
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
    <span>{item.label}</span>
  </button>
);

const AppShell: React.FC<AppShellProps> = ({
  pageMode,
  setPageMode,
  theme,
  setTheme,
  selectedDate,
  setSelectedDate,
  lastUpdatedAt,
  refreshing,
  onRefresh,
  version,
  children,
}) => {
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [dockedPreference, setDockedPreference] = useLocalStorageState<"true" | "false">("elektroapp.nav.docked", "false");
  const [isDesktopDockAllowed, setIsDesktopDockAllowed] = useState(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return false;
    return window.matchMedia("(min-width: 1024px)").matches;
  });
  const menuButtonRef = useRef<HTMLButtonElement | null>(null);
  const drawerRef = useRef<HTMLElement | null>(null);

  const isDocked = dockedPreference === "true" && isDesktopDockAllowed;
  const isDrawerVisible = drawerOpen || isDocked;

  const focusMenuButton = () => {
    window.requestAnimationFrame(() => menuButtonRef.current?.focus());
  };

  const handleCloseDrawer = () => {
    setDrawerOpen(false);
    focusMenuButton();
  };

  const handleNav = (mode: PageMode) => {
    setPageMode(mode);
    if (!isDocked) {
      setDrawerOpen(false);
      focusMenuButton();
    }
  };

  const handleMenuToggle = () => {
    if (isDocked) {
      setDockedPreference("false");
      setDrawerOpen(false);
      focusMenuButton();
      return;
    }
    setDrawerOpen((prev) => !prev);
  };

  const handleDock = () => {
    setDockedPreference("true");
    setDrawerOpen(false);
  };

  const handleUndock = () => {
    setDockedPreference("false");
    setDrawerOpen(false);
    focusMenuButton();
  };

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return undefined;
    const mediaQuery = window.matchMedia("(min-width: 1024px)");
    const handleChange = () => setIsDesktopDockAllowed(mediaQuery.matches);
    handleChange();
    mediaQuery.addEventListener("change", handleChange);
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, []);

  useEffect(() => {
    if (!drawerOpen || isDocked) return undefined;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        handleCloseDrawer();
      }
    };
    document.addEventListener("keydown", handleKeyDown);
    window.requestAnimationFrame(() => drawerRef.current?.focus());
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [drawerOpen, isDocked]);

  const rootClassName = [
    "modern-app-shell",
    isDrawerVisible ? "is-nav-open" : "",
    isDocked ? "is-nav-docked" : "",
  ].filter(Boolean).join(" ");

  const drawerClassName = [
    "modern-sidebar",
    isDrawerVisible ? "is-open" : "",
    isDocked ? "is-docked" : "",
  ].filter(Boolean).join(" ");

  const menuButtonLabel = isDocked ? "Odepnout menu" : drawerOpen ? "Zavřít menu" : "Otevřít menu";

  return (
    <div className={rootClassName}>
      <a href="#modern-main-content" className="skip-link">
        Přeskočit na obsah
      </a>
      <aside
        id="modern-navigation-drawer"
        ref={drawerRef}
        className={drawerClassName}
        aria-label="Hlavní navigace"
        aria-hidden={!isDrawerVisible}
        tabIndex={isDrawerVisible ? -1 : undefined}
      >
        <div className="modern-sidebar__header">
          <BrandLogo className="modern-brand-logo--drawer" />
          <div className="modern-sidebar__actions">
            {isDesktopDockAllowed ? (
              <button
                type="button"
                className="modern-icon-button modern-sidebar__pin"
                onClick={isDocked ? handleUndock : handleDock}
                aria-label={isDocked ? "Odepnout menu" : "Připnout menu"}
                title={isDocked ? "Odepnout menu" : "Připnout menu"}
              >
                {isDocked ? <IconPinOff size={18} /> : <IconPin size={18} />}
              </button>
            ) : null}
            {!isDocked ? (
              <button
                type="button"
                className="modern-icon-button modern-sidebar__close"
                onClick={handleCloseDrawer}
                aria-label="Zavřít menu"
                title="Zavřít menu"
              >
                <IconX size={18} />
              </button>
            ) : null}
          </div>
        </div>

        <nav className="modern-sidebar__nav" role="tablist" aria-label="Hlavní navigace">
          {navItems.map((item) => (
            <NavButton key={item.id} item={item} active={pageMode === item.id} onClick={() => handleNav(item.id)} />
          ))}
          <div className="modern-sidebar__divider" />
          <NavButton
            item={{ id: "hp", label: "HP", icon: <IconPlug /> }}
            active={pageMode === "hp"}
            onClick={() => handleNav("hp")}
          />
        </nav>

        <div className="modern-sidebar__footer">
          <span>Home Assistant</span>
          <small>Verze doplňku: {version || "-"}</small>
        </div>
      </aside>

      {drawerOpen && !isDocked ? (
        <button type="button" className="modern-sidebar-backdrop" aria-label="Zavřít menu" onClick={handleCloseDrawer} />
      ) : null}

      <div className="modern-workspace">
        <header className="modern-topbar">
          <div className="modern-topbar__title">
            <button
              ref={menuButtonRef}
              type="button"
              className="modern-icon-button modern-menu-button"
              onClick={handleMenuToggle}
              aria-label={menuButtonLabel}
              aria-expanded={isDrawerVisible}
              aria-controls="modern-navigation-drawer"
              title={menuButtonLabel}
            >
              <IconMenu size={20} />
            </button>
            <BrandLogo className="modern-brand-logo--topbar" />
          </div>

          <div className="modern-topbar__controls">
            <span className="modern-updated">{formatUpdated(lastUpdatedAt)}</span>
            <button type="button" className="modern-icon-button" onClick={onRefresh} disabled={refreshing} aria-label="Obnovit data" title="Obnovit data">
              {refreshing ? "..." : <IconRefresh size={18} />}
            </button>
            <label className="modern-date-control">
              <span className="sr-only">Datum</span>
              <IconCalendar size={16} />
              <input type="date" value={selectedDate} onChange={(event) => setSelectedDate(event.target.value)} />
            </label>
            <ThemeToggle theme={theme} setTheme={setTheme} />
          </div>
        </header>

        <main id="modern-main-content" className="modern-content">{children}</main>
      </div>
    </div>
  );
};

export default AppShell;
