import { describe, expect, test } from "vitest";
import { deriveEnergyFlows } from "./EnergyFlowCard";

describe("deriveEnergyFlows", () => {
  test("marks import as grid to home and export as home to target", () => {
    const flows = deriveEnergyFlows({
      pvPower: 7800,
      batteryPower: 0,
      gridImport: 2200,
      gridExport: 390,
    });

    expect(flows.find((flow) => flow.id === "solar")).toMatchObject({ active: true, direction: "source-to-home" });
    expect(flows.find((flow) => flow.id === "import")).toMatchObject({ active: true, direction: "target-to-home" });
    expect(flows.find((flow) => flow.id === "export")).toMatchObject({ active: true, direction: "home-to-target" });
  });

  test("uses negative battery power as discharge to home", () => {
    const flows = deriveEnergyFlows({ batteryPower: -2270 });

    expect(flows.find((flow) => flow.id === "battery")).toMatchObject({
      active: true,
      direction: "source-to-home",
      watts: 2270,
    });
  });

  test("uses positive battery power as charging toward battery", () => {
    const flows = deriveEnergyFlows({ batteryPower: 1450 });

    expect(flows.find((flow) => flow.id === "battery")).toMatchObject({
      active: true,
      direction: "home-to-battery",
      watts: 1450,
    });
  });
});
