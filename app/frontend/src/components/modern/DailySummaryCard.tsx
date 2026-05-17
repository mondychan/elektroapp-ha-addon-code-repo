import React from "react";
import { formatCurrency } from "../../utils/formatters";

export type SummaryTone = "neutral" | "cost" | "gain" | "net-positive" | "net-negative" | "net-zero";

export const getSummaryTone = (kind: "cost" | "gain" | "net" | "neutral", value?: number | null): SummaryTone => {
  if (kind === "cost") return value == null || value === 0 ? "neutral" : "cost";
  if (kind === "gain") return value == null || value === 0 ? "neutral" : "gain";
  if (kind === "net") {
    if (value == null || value === 0) return "net-zero";
    return value > 0 ? "net-negative" : "net-positive";
  }
  return "neutral";
};

const formatKwh = (value?: number | null) => (value == null || Number.isNaN(Number(value)) ? "-" : `${Number(value).toFixed(2)} kWh`);
const formatPowerKw = (value?: number | null) =>
  value == null || Number.isNaN(Number(value)) ? "-" : `${(Number(value) / 1000).toFixed(2)} kW`;

const DailySummaryCard = ({
  costsSummary,
  exportSummary,
  batteryData,
  solarForecast,
}: {
  costsSummary: any;
  exportSummary: any;
  batteryData: any;
  solarForecast: any;
}) => {
  const production = solarForecast?.actual?.production_today_kwh ?? solarForecast?.status?.energy_production_today_kwh;
  const houseLoad = batteryData?.current_energy?.house_load_w;
  const importKwh = costsSummary?.kwh_total;
  const exportKwh = exportSummary?.export_kwh_total;
  const importCost = costsSummary?.cost_total;
  const exportRevenue = exportSummary?.sell_total;
  const netCost =
    importCost != null || exportRevenue != null
      ? (importCost || 0) - (exportRevenue || 0)
      : null;

  const rows = [
    { label: "Vyrobeno (FV)", today: formatKwh(production), cost: "-", tone: "neutral" as SummaryTone },
    { label: "Spotřeba domu", today: formatPowerKw(houseLoad), cost: "-", tone: "neutral" as SummaryTone },
    { label: "Import ze sítě", today: formatKwh(importKwh), cost: formatCurrency(importCost), tone: getSummaryTone("cost", importCost) },
    { label: "Export do sítě", today: formatKwh(exportKwh), cost: formatCurrency(exportRevenue), tone: getSummaryTone("gain", exportRevenue) },
    { label: "Netto", today: "-", cost: formatCurrency(netCost), tone: getSummaryTone("net", netCost) },
  ];

  return (
    <div className="daily-summary">
      <table className="data-table daily-summary__table">
        <thead>
          <tr>
            <th className="cell-left">Položka</th>
            <th className="cell-right">Dnes</th>
            <th className="cell-right">Náklady</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className={`daily-summary__row daily-summary__row--${row.tone}`}>
              <td>{row.label}</td>
              <td className="cell-right">{row.today}</td>
              <td className={`cell-right daily-summary__money daily-summary__money--${row.tone}`}>{row.cost}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DailySummaryCard;
