import { getQuarterHourSlotFromIso, parseIsoLocalTimeParts } from "../../utils/timeSeries";
import { buildCategoryTimeAxis, buildTooltip } from "./common";
import { getChartTheme } from "../chartTheme";

const formatIsoToTime = (iso) => {
  const parts = parseIsoLocalTimeParts(iso);
  if (!parts) return "-";
  return `${String(parts.hour).padStart(2, "0")}:${String(parts.minute).padStart(2, "0")}`;
};

export const buildBatteryChartData = (batteryData) => {
  const map = new Map();
  const historyPoints = batteryData?.history?.points || [];
  const projectionPoints = batteryData?.projection?.points || [];

  // Find the last history point that actually contains SoC data.
  // This prevents the blue line from extending flat to the end of the day if the backend returns empty slots.
  const lastValidHistoryPoint = [...historyPoints].reverse().find((p) => p.soc_percent != null);
  const lastHistoryTime = lastValidHistoryPoint?.time || null;

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
    map.set(point.time, row);
  });

  // Stitching: ensure projection starts from the last valid history point
  if (lastValidHistoryPoint && projectionPoints.length > 0) {
    const row = map.get(lastValidHistoryPoint.time) || {
      time: lastValidHistoryPoint.time,
      timeLabel: formatIsoToTime(lastValidHistoryPoint.time),
      slot: getQuarterHourSlotFromIso(lastValidHistoryPoint.time),
    };
    if (row.socProjected == null) {
      row.socProjected = row.soc ?? lastValidHistoryPoint.soc_percent ?? null;
    }
    map.set(lastValidHistoryPoint.time, row);
  }

  const projectionStartMs = projectionPoints.length ? new Date(projectionPoints[0].time).getTime() : null;
  const lastHistoryMs = lastHistoryTime ? new Date(lastHistoryTime).getTime() : null;
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
      const rowTimeMs = new Date(normalizedRow.time).getTime();

      if (Number.isFinite(normalizedRow.soc)) {
        lastSoc = normalizedRow.soc;
      } else if (lastSoc != null && lastHistoryMs != null && rowTimeMs <= lastHistoryMs) {
        normalizedRow.soc = lastSoc;
      } else {
        normalizedRow.soc = null;
      }

      if (Number.isFinite(normalizedRow.socProjected)) {
        lastProjectedSoc = normalizedRow.socProjected;
      } else if (projectionStartMs != null && rowTimeMs >= projectionStartMs && lastProjectedSoc != null) {
        normalizedRow.socProjected = lastProjectedSoc;
      }

      normalizedRow.batteryPower = Number.isFinite(normalizedRow.batteryPower)
        ? normalizedRow.batteryPower
        : 0;
      return normalizedRow;
    });
};

const buildBatteryTimeAxis = () =>
  buildCategoryTimeAxis({
    stepSize: 4,
    labelFormatter: (_, label) => (typeof label === "string" && label.endsWith(":00") ? label : ""),
  });

export const buildBatterySocChartConfig = (chartData) => {
  const theme = getChartTheme();
  const socColor = theme.accentGreen || "rgba(34, 197, 94, 0.92)";
  const projectionColor = theme.accentAmber || "rgba(245, 158, 11, 0.98)";

  return {
    pointPayloads: chartData,
    data: {
      labels: chartData.map((item) => item.timeLabel),
      datasets: [
        {
          label: "Stav baterie (%)",
          data: chartData.map((item) => item.soc),
          borderColor: socColor,
          backgroundColor: "rgba(34, 197, 94, 0.12)",
          borderWidth: 2.5,
          pointRadius: 0,
          pointHoverRadius: 4,
          spanGaps: true,
          tension: 0.28,
        },
        {
          label: "Projekce SoC",
          data: chartData.map((item) => item.socProjected ?? null),
          borderColor: projectionColor,
          backgroundColor: "rgba(245, 158, 11, 0.14)",
          borderWidth: 2.5,
          pointRadius: 0,
          pointHoverRadius: 5,
          borderDash: [7, 5],
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
            { label: "Stav baterie", value: point.soc == null ? "-" : `${Number(point.soc).toFixed(1)} %`, color: socColor },
            { label: "Projekce SoC", value: point.socProjected == null ? "-" : `${Number(point.socProjected).toFixed(1)} %`, color: projectionColor },
            { label: "Výkon baterie", value: `${Math.round(point.batteryPower)} W`, color: theme.text },
          ],
        };
      }),
    },
  },
  };
};

export const buildBatteryPowerChartConfig = (chartData) => {
  const theme = getChartTheme();
  const chargeColor = theme.accentBlue || "rgba(56, 189, 248, 0.82)";
  const dischargeColor = theme.accentRed || "rgba(239, 68, 68, 0.82)";

  return {
    pointPayloads: chartData,
    data: {
      labels: chartData.map((item) => item.timeLabel),
      datasets: [
        {
          type: "bar",
          label: "Nabíjení/Vybíjení (W)",
          data: chartData.map((item) => item.batteryPower),
          backgroundColor: chartData.map((item) =>
            item.batteryPower >= 0 ? dischargeColor : chargeColor
          ),
          borderRadius: 5,
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
          sections: [{ label: "Výkon baterie", value: `${Math.round(point.batteryPower)} W`, color: point.batteryPower >= 0 ? dischargeColor : chargeColor }],
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
  };
};
