import { buildBatteryChartData } from "../charting/builders/batteryChartBuilder";

describe("buildBatteryChartData", () => {
  test("adds a projection anchor on the last real SoC point", () => {
    const batteryData = {
      history: {
        points: [
          { time: "2026-03-08T10:00:00+01:00", soc_percent: 72, battery_power_w: 800 },
          { time: "2026-03-08T10:15:00+01:00", soc_percent: 73, battery_power_w: 900 },
        ],
      },
      projection: {
        points: [
          { time: "2026-03-08T10:30:00+01:00", soc_percent: 74 },
          { time: "2026-03-08T10:45:00+01:00", soc_percent: 76 },
        ],
      },
    };

    const chartData = buildBatteryChartData(batteryData);

    expect(chartData).toEqual([
      {
        time: "2026-03-08T10:00:00+01:00",
        timeLabel: "10:00",
        soc: 72,
        batteryPower: 800,
      },
      {
        time: "2026-03-08T10:15:00+01:00",
        timeLabel: "10:15",
        soc: 73,
        batteryPower: 900,
        socProjected: 73,
      },
      {
        time: "2026-03-08T10:30:00+01:00",
        timeLabel: "10:30",
        soc: 74,
        batteryPower: 0,
        socProjected: 74,
      },
      {
        time: "2026-03-08T10:45:00+01:00",
        timeLabel: "10:45",
        soc: 74,
        batteryPower: 0,
        socProjected: 76,
      },
    ]);
  });

  test("keeps SoC continuous and battery power at zero when intermediate data are missing", () => {
    const batteryData = {
      history: {
        points: [
          { time: "2026-03-08T10:00:00+01:00", soc_percent: 72, battery_power_w: 800 },
          { time: "2026-03-08T10:15:00+01:00", soc_percent: null, battery_power_w: null },
          { time: "2026-03-08T10:30:00+01:00", soc_percent: 73, battery_power_w: 900 },
        ],
      },
      projection: {
        points: [],
      },
    };

    const chartData = buildBatteryChartData(batteryData);

    expect(chartData[0]).toMatchObject({ soc: 72, batteryPower: 800 });
    expect(chartData[1]).toMatchObject({ soc: 72, batteryPower: 0 });
    expect(chartData[2]).toMatchObject({ soc: 73, batteryPower: 900 });
  });
});
