import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";

// setupTests.js mocks react-day-picker for every other suite; this file is the
// one place that exercises the real calendar, so the mocks must be undone
// before the components that import it are evaluated.
vi.unmock("react-day-picker");
vi.unmock("react-day-picker/locale");

import DateNavigator from "./DateNavigator";
import FeesHistorySection from "./FeesHistorySection";

const isOpen = () => Boolean(document.querySelector(".date-nav-popover"));

const openPicker = () => {
  fireEvent.click(document.querySelector(".date-nav-trigger"));
  if (!isOpen()) throw new Error("date picker did not open");
  return document.querySelector(".date-nav-popover");
};

const dayButton = (iso) => {
  const cell = document.querySelector(`[data-day="${iso}"]`);
  return cell ? cell.querySelector("button") : null;
};

const snapshot = {
  dph: "21",
  poplatky: {
    komodita_sluzba: "0.35",
    oze: "0",
    dan: "0.0283",
    systemove_sluzby: "0.16424",
    distribuce: { NT: "0.1", VT: "0.7" },
  },
  fixni: {
    denni: { staly_plat: "4.18" },
    mesicni: { provoz_nesitove_infrastruktury: "12.87", jistic: "710" },
  },
};

describe("DateNavigator calendar", () => {
  beforeEach(() => {
    // Fake only Date: React and testing-library keep using real timers.
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 15, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("opens on the month of the selected value, not the current month", () => {
    render(<DateNavigator value="2025-05-05" onChange={() => {}} compact maxDate="2026-11-15" />);
    openPicker();

    const selected = dayButton("2025-05-05");
    expect(selected).not.toBeNull();
    expect(selected.closest("[data-day]")).toHaveAttribute("data-selected", "true");
  });

  test("clicking an in-range day applies it and closes", () => {
    const onChange = vi.fn();
    render(<DateNavigator value="2025-05-05" onChange={onChange} compact maxDate="2026-11-15" />);
    openPicker();

    fireEvent.click(dayButton("2025-05-12"));

    expect(onChange).toHaveBeenCalledTimes(1);
    expect(onChange).toHaveBeenCalledWith("2025-05-12");
    expect(isOpen()).toBe(false);
  });

  test("days outside min/max are disabled and never close the picker", () => {
    const onChange = vi.fn();
    render(
      <DateNavigator
        value="2026-11-10"
        onChange={onChange}
        compact
        minDate="2026-11-01"
        maxDate="2026-11-15"
      />
    );

    openPicker();

    const outOfRange = dayButton("2026-11-20");
    expect(outOfRange).not.toBeNull();
    expect(outOfRange).toBeDisabled();

    fireEvent.click(outOfRange);

    expect(onChange).not.toHaveBeenCalled();
    expect(isOpen()).toBe(true);
  });
});

describe("FeesHistorySection date pickers", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 15, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("adding a period with partial defaults keeps the editor open while picking 'Platne od'", () => {
    const onSave = vi.fn(() => Promise.resolve([]));
    render(
      <FeesHistorySection
        visible
        onToggle={() => {}}
        history={[{ effective_from: "2024-01-01", effective_to: "2024-12-31", snapshot }]}
        loading={false}
        error={null}
        onSave={onSave}
        // A parent that has not loaded the live config yet passes null; a
        // partial object must not take the editor down with it.
        defaultValues={{}}
      />
    );

    fireEvent.click(screen.getByRole("button", { name: "Pridat obdobi" }));
    expect(screen.getByRole("button", { name: "Ulozit" })).toBeInTheDocument();

    const triggers = document.querySelectorAll(".fees-history-date-nav .date-nav-trigger");
    expect(triggers.length).toBe(2);
    fireEvent.click(triggers[0]);

    const picked = dayButton("2025-01-15");
    expect(picked).not.toBeNull();
    fireEvent.click(picked);

    expect(isOpen()).toBe(false);
    expect(triggers[0]).toHaveTextContent(/15\.\s*0?1\.\s*2025/);
    expect(screen.getByRole("button", { name: "Ulozit" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zrusit" })).toBeInTheDocument();
    expect(onSave).not.toHaveBeenCalled();
  });
});
