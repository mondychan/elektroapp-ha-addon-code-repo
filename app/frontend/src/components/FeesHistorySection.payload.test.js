import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import FeesHistorySection from "./FeesHistorySection";

// The backend rejects PUT /fees-history entries whose snapshot does not carry
// the canonical dph_percent / kwh_fees / fixed keys.  These tests pin the exact
// payload the editor sends so that a rename on either side fails loudly here
// instead of as a 400 in the UI.
const history = [
  {
    effective_from: "2024-01-01",
    effective_to: "2024-12-31",
    snapshot: {
      dph_percent: 21,
      kwh_fees: {
        komodita_sluzba: 0.35,
        oze: 0,
        dan: 0.0283,
        systemove_sluzby: 0.16424,
        distribuce: { NT: 0.1165, VT: 0.75477 },
      },
      fixed: {
        daily: { staly_plat: 4.18 },
        monthly: { provoz_nesitove_infrastruktury: 12.87, jistic: 710 },
      },
      prodej: { koeficient_snizeni_ceny: 390, fixni_cena_enabled: false, fixni_cena: 0 },
      nakup: { fixni_cena_enabled: false, fixni_cena: 0 },
    },
  },
];

const renderSection = (overrides = {}) => {
  const onSave = vi.fn(() => Promise.resolve([]));
  render(
    <FeesHistorySection
      visible
      onToggle={() => {}}
      history={history}
      loading={false}
      error={null}
      onSave={onSave}
      defaultValues={null}
      {...overrides}
    />
  );
  return onSave;
};

describe("FeesHistorySection payload schema", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 10, 20, 12, 0, 0));
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test("editing an existing period saves the canonical snapshot keys", async () => {
    const onSave = renderSection();

    fireEvent.click(screen.getByRole("button", { name: "Upravit" }));
    fireEvent.click(screen.getByRole("button", { name: "Ulozit" }));

    expect(onSave).toHaveBeenCalledTimes(1);
    const payload = onSave.mock.calls[0][0];
    expect(payload).toHaveLength(1);

    const snapshot = payload[0].snapshot;
    expect(snapshot).toMatchObject({
      dph_percent: 21,
      kwh_fees: {
        komodita_sluzba: 0.35,
        oze: 0,
        dan: 0.0283,
        systemove_sluzby: 0.16424,
        distribuce: { NT: 0.1165, VT: 0.75477 },
      },
      fixed: {
        daily: { staly_plat: 4.18 },
        monthly: { provoz_nesitove_infrastruktury: 12.87, jistic: 710 },
      },
    });
    // Legacy names must never reach PUT /fees-history.
    expect(snapshot).not.toHaveProperty("dph");
    expect(snapshot).not.toHaveProperty("poplatky");
    expect(snapshot).not.toHaveProperty("fixni");
    expect(payload[0].effective_to).toBe("2024-12-31");
  });

  test("unknown snapshot fields survive an edit of that period", async () => {
    const withExtension = [
      {
        ...history[0],
        snapshot: { ...history[0].snapshot, extension: { preserve: true } },
      },
    ];
    const onSave = renderSection({ history: withExtension });

    fireEvent.click(screen.getByRole("button", { name: "Upravit" }));
    fireEvent.click(screen.getByRole("button", { name: "Ulozit" }));

    const [snapshot] = onSave.mock.calls[0][0];
    expect(snapshot.snapshot.extension).toEqual({ preserve: true });
  });

  test("a period added before the live config loads still saves valid fields", async () => {
    const onSave = renderSection({ defaultValues: {} });

    fireEvent.click(screen.getByRole("button", { name: "Pridat obdobi" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Ulozit" })[0]);

    const [firstSave] = onSave.mock.calls;
    expect(firstSave).toBeTruthy();
    const entry = firstSave[0].find((item) => item.effective_from === "2025-01-01");
    expect(entry).toBeTruthy();
    expect(entry.snapshot).toHaveProperty("dph_percent");
    expect(entry.snapshot).toHaveProperty("kwh_fees");
    expect(entry.snapshot).toHaveProperty("fixed");
  });
});
