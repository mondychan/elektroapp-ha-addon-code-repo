import React from "react";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";
import AppShell from "./AppShell";

const setMatchMedia = (matches: boolean) => {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches,
    media: query,
    onchange: null,
    addListener: vi.fn(),
    removeListener: vi.fn(),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
    dispatchEvent: vi.fn(),
  }));
};

const renderShell = (props: Partial<React.ComponentProps<typeof AppShell>> = {}) => {
  const setPageMode = vi.fn();
  const result = render(
    <AppShell
      pageMode="overview"
      setPageMode={setPageMode}
      theme="dark"
      setTheme={vi.fn()}
      selectedDate="2026-05-19"
      setSelectedDate={vi.fn()}
      lastUpdatedAt="2026-05-19T16:02:00+02:00"
      refreshing={false}
      onRefresh={vi.fn()}
      version="0.3.35"
      {...props}
    >
      <div>Dashboard content</div>
    </AppShell>
  );

  return { ...result, setPageMode };
};

describe("AppShell drawer navigation", () => {
  beforeEach(() => {
    localStorage.clear();
    setMatchMedia(true);
  });

  test("starts without a visible drawer, docked rail, or mobile bottom nav", () => {
    const { container } = renderShell();
    const shell = container.querySelector(".modern-app-shell");
    const drawer = container.querySelector(".modern-sidebar");

    expect(shell).not.toHaveClass("is-nav-open");
    expect(shell).not.toHaveClass("is-nav-docked");
    expect(drawer).toHaveAttribute("aria-hidden", "true");
    expect(screen.queryByRole("navigation", { name: "Mobilní navigace" })).not.toBeInTheDocument();
  });

  test("hamburger opens the overlay drawer and backdrop click closes it", async () => {
    const { container } = renderShell();

    await userEvent.click(screen.getByRole("button", { name: "Otevřít menu" }));
    expect(container.querySelector(".modern-app-shell")).toHaveClass("is-nav-open");
    expect(container.querySelector(".modern-sidebar")).toHaveAttribute("aria-hidden", "false");

    fireEvent.click(container.querySelector(".modern-sidebar-backdrop") as Element);
    await waitFor(() => {
      expect(container.querySelector(".modern-app-shell")).not.toHaveClass("is-nav-open");
    });
  });

  test("Escape closes the overlay drawer", async () => {
    const { container } = renderShell();

    await userEvent.click(screen.getByRole("button", { name: "Otevřít menu" }));
    fireEvent.keyDown(document, { key: "Escape" });

    await waitFor(() => {
      expect(container.querySelector(".modern-sidebar")).toHaveAttribute("aria-hidden", "true");
    });
  });

  test("pin docks the drawer on desktop and persists the choice", async () => {
    const { container } = renderShell();

    await userEvent.click(screen.getByRole("button", { name: "Otevřít menu" }));
    await userEvent.click(screen.getByRole("button", { name: "Připnout menu" }));

    expect(localStorage.getItem("elektroapp.nav.docked")).toBe("true");
    expect(container.querySelector(".modern-app-shell")).toHaveClass("is-nav-docked");
    expect(screen.queryByRole("button", { name: "Zavřít menu" })).not.toBeInTheDocument();
  });

  test("undock clears persisted dock state and closes the menu", async () => {
    localStorage.setItem("elektroapp.nav.docked", "true");
    const { container } = renderShell();

    expect(container.querySelector(".modern-app-shell")).toHaveClass("is-nav-docked");
    await userEvent.click(container.querySelector(".modern-sidebar__pin") as Element);

    expect(localStorage.getItem("elektroapp.nav.docked")).toBe("false");
    expect(container.querySelector(".modern-app-shell")).not.toHaveClass("is-nav-docked");
    expect(container.querySelector(".modern-sidebar")).toHaveAttribute("aria-hidden", "true");
  });

  test("narrow viewports ignore persisted dock state and hide pin controls", async () => {
    setMatchMedia(false);
    localStorage.setItem("elektroapp.nav.docked", "true");
    const { container } = renderShell();

    expect(container.querySelector(".modern-app-shell")).not.toHaveClass("is-nav-docked");
    await userEvent.click(screen.getByRole("button", { name: "Otevřít menu" }));
    expect(screen.queryByRole("button", { name: "Připnout menu" })).not.toBeInTheDocument();
  });

  test("clicking a drawer navigation item switches page and closes overlay", async () => {
    const { container, setPageMode } = renderShell();

    await userEvent.click(screen.getByRole("button", { name: "Otevřít menu" }));
    await userEvent.click(screen.getByRole("tab", { name: "Detail" }));

    expect(setPageMode).toHaveBeenCalledWith("costs");
    await waitFor(() => {
      expect(container.querySelector(".modern-sidebar")).toHaveAttribute("aria-hidden", "true");
    });
  });
});
