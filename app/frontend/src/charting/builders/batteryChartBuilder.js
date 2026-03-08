import { getQuarterHourSlotFromIso, parseIsoLocalTimeParts } from "../../utils/timeSeries";
import { buildCategoryTimeAxis, buildTooltip } from "./common";

const formatIsoToTime = (iso) => {
  const parts = parseIsoLocalTimeParts(iso);
  if (!parts) return "-";
  return `${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}`;
};

export const buildBatteryChartData = (batteryData) => {
  const map = new Map();
  const historyPoints = batteryData?.history?.points || [];
  const projectionPoints = batteryData?.projection?.points || [];

  historyPoints.forEach((point) => {
    const row = map.get(point.time) || {
      time: point.time,
      timeLabel: formatIsoToTime(point.time),
      slot: getQuarterHourSlotFromIso(point.time),
    };
    row.soc = point.soc_percent ?? null;
    row.batteryPower = point.battery_power_w ?? null;
    map.set(point.time, row);
  });

  projectionPoints.forEach((point, index) => {
    const row = map.get(point.time) || {
      time: point.time,
      timeLabel: formatIsoToTime(point.time),
      slot: getQuarterHourSlotFromIso(point.time),
    };
    row.socProjected = point.soc_percent ?? null;
    if (index === 0 && row.soc == null) {
      row.soc = point.soc_percent ?? null;
    }
    map.set(point.time, row);
  });

  const lastHistoryPoint = historyPoints[historyPoints.length - 1];
  if (lastHistoryPoint && projectionPoints.length > 0) {
    const row = map.get(lastHistoryPoint.time) || {
      time: lastHistoryPoint.time,
      timeLabel: formatIsoToTime(lastHistoryPoint.time),
      slot: getQuarterHourSlotFromIso(lastHistoryPoint.time),
    };
    if (row.socProjected == null) {
      row.socProjected = row.soc ?? lastHistoryPoint.soc_percent ?? null;
    }
    map.set(lastHistoryPoint.time, row);
  }

  const projectionStartMs = projectionPoints.length ? new Date(projectionPoints[0].time).getTime() : null;
  let lastSoc = null;
  let lastProjectedSoc = null;

  return [...map.values()]
    .sort((a, b) => {
      if (Number.isInteger(a.slot) && Number.isInteger(b.slot)) {
        return a.slot - b.slot;
      }
      return a.time.localeCompare(b.time);
    })
    .map((row) => {
      const normalizedRow = { ...row };
      if (Number.isFinite(normalizedRow.soc)) {
        lastSoc = normalizedRow.soc;
      } else if (lastSoc != null) {
        normalizedRow.soc = lastSoc;
      }

      const rowTimeMs = new Date(normalizedRow.time).getTime();
      if (Number.isFinite(normalizedRow.socProjected)) {
        lastProjectedSoc = normalizedRow.socProjected;
      } else if (projectionStartMs != null && rowTimeMs >= projectionStartMs && lastProjectedSoc != null) {
        normalizedRow.socProjected = lastProjectedSoc;
      }

      normalizedRow.batteryPower = Number.isFinite(normalizedRow.batteryPower) ? normalizedRow.batteryPower : 0;
      return normalizedRow;
    });
};

const buildBatteryTimeAxis = () =>
  buildCategoryTimeAxis({
    stepSize: 4,
    labelFormatter: (_, label) => (typeof label === "string" && label.endsWith(":00") ? label : ""),
  });

export const buildBatterySocChartConfig = (chartData) => ({
  pointPayloads: chartData,
  data: {
    labels: chartData.map((item) => item.timeLabel),
    datasets: [
      {
        label: "SoC",
        data: chartData.map((item) => item.soc),
        borderColor: "rgba(45, 127, 249, 0.92)",
        backgroundColor: "rgba(45, 127, 249, 0.12)",
        borderWidth: 2.5,
        pointRadius: 0,
        pointHoverRadius: 4,
        tension: 0.28,
      },
      {
        label: "Projekce SoC",
        data: chartData.map((item) => item.socProjected ?? null),
        borderColor: "rgba(255, 122, 89, 0.98)",
        backgroundColor: "rgba(255, 122, 89, 0.14)",
        borderWidth: 3,
        pointRadius: 0,
        pointHoverRadius: 5,
        borderDash: [8, 6],
        spanGaps: true,
        tension: 0.24,
      },
    ],
  },
  options: {
    interaction: {
      mode: "index",
      intersect: false,
    },
    scales: {
      x: buildBatteryTimeAxis(),
      y: {
        min: 0,
        max: 100,
        title: {
          display: true,
          text: "SoC %",
        },
      },
    },
    plugins: {
      tooltip: buildTooltip(({ points }) => {
        const point = chartData[points?.[0]?.dataIndex] || null;
        if (!point) return null;
        return {
          title: point.timeLabel,
          sections: [
            { label: "SoC", value: `${Number(point.soc ?? 0).toFixed(1)} %`, color: "rgba(45, 127, 249, 0.92)" },
            {
              label: "Projekce SoC",
              value: point.socProjected == null ? "-" : `${Number(point.socProjected).toFixed(1)} %`,
              color: "rgba(255, 122, 89, 0.98)",
            },
            { label: "Vykon baterie", value: `${Math.round(point.batteryPower)} W`, color: "rgba(255,255,255,0.92)" },
          ],
        };
      }),
    },
  },
});

export const buildBatteryPowerChartConfig = (chartData) => ({
  pointPayloads: chartData,
  data: {
    labels: chartData.map((item) => item.timeLabel),
    datasets: [
      {
        type: "bar",
        label: "Vykon baterie",
        data: chartData.map((item) => item.batteryPower),
        backgroundColor: chartData.map((item) =>
          item.batteryPower >= 0 ? "rgba(255, 122, 89, 0.82)" : "rgba(45, 127, 249, 0.82)"
        ),
        borderRadius: 6,
        borderSkipped: false,
      },
    ],
  },
  options: {
    scales: {
      x: buildBatteryTimeAxis(),
      y: {
        title: {
          display: true,
          text: "W",
        },
      },
    },
    plugins: {
      tooltip: buildTooltip(({ points }) => {
        const point = chartData[points?.[0]?.dataIndex] || null;
        if (!point) return null;
        return {
          title: point.timeLabel,
          sections: [{ label: "Vykon baterie", value: `${Math.round(point.batteryPower)} W`, color: "rgba(255, 122, 89, 0.82)" }],
        };
      }),
      annotation: {
        annotations: {
          zeroLine: {
            type: "line",
            yMin: 0,
            yMax: 0,
            borderColor: "rgba(120, 129, 145, 0.45)",
            borderWidth: 1.5,
          },
        },
      },
    },
  },
});
