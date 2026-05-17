import React from "react";
import { formatCurrency } from "../../utils/formatters";

const formatKwh = (value?: number | null) => (value == null || Number.isNaN(Number(value)) ? "-" : `${Number(value).toFixed(2)} kWh`);

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
  const netCost =
    costsSummary?.cost_total != null || exportSummary?.sell_total != null
      ? (costsSummary?.cost_total || 0) - (exportSummary?.sell_total || 0)
      : null;

  const rows = [
    { label: "Vyrobeno (FV)", today: formatKwh(production), cost: "-" },
    { label: "Spotřeba domu", today: houseLoad == null ? "-" : `${(Number(houseLoad) / 1000).toFixed(2)} kW`, cost: "-" },
    { label: "Import ze sítě", today: formatKwh(importKwh), cost: formatCurrency(costsSummary?.cost_total) },
    { label: "Export do sítě", today: formatKwh(exportKwh), cost: formatCurrency(exportSummary?.sell_total) },
    { label: "Netto", today: "-", cost: formatCurrency(netCost) },
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
            <tr key={row.label}>
              <td>{row.label}</td>
              <td className="cell-right">{row.today}</td>
              <td className="cell-right">{row.cost}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};

export default DailySummaryCard;
