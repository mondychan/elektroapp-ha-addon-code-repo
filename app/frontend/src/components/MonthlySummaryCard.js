import React from "react";
import { formatDate, formatMonthLabel } from "../utils/formatters";

const MonthlySummaryCard = ({
  selectedMonth,
  setSelectedMonth,
  monthlySummary,
  monthlyTotals,
  monthlyError,
}) => {
  let content = null;
  if (monthlyError) {
    content = <div className="alert error">{monthlyError}</div>;
  } else if (!monthlySummary.length) {
    content = <div className="muted-note">Mesicni souhrn neni k dispozici.</div>;
  } else {
    content = (
      <table className="data-table table-spaced">
        <thead>
          <tr>
            <th className="cell-left">Den</th>
            <th className="cell-left">Datum</th>
            <th className="cell-right cell-buy">Nakup (kWh)</th>
            <th className="cell-right cell-buy">Naklady (Kc)</th>
            <th className="cell-right cell-sell">Prodej (kWh)</th>
            <th className="cell-right cell-sell">Trzby (Kc)</th>
          </tr>
        </thead>
        <tbody>
          {monthlySummary.map((day) => {
            const dt = new Date(`${day.date}T00:00:00`);
            const dayName = dt.toLocaleDateString("cs-CZ", { weekday: "short" });
            return (
              <tr key={day.date}>
                <td>{dayName}</td>
                <td>{formatDate(dt)}</td>
                <td className="cell-right cell-buy">{day.kwh_total == null ? "-" : day.kwh_total.toFixed(2)}</td>
                <td className="cell-right cell-buy">{day.cost_total == null ? "-" : day.cost_total.toFixed(2)}</td>
                <td className="cell-right cell-sell">{day.export_kwh_total == null ? "-" : day.export_kwh_total.toFixed(2)}</td>
                <td className="cell-right cell-sell">{day.sell_total == null ? "-" : day.sell_total.toFixed(2)}</td>
              </tr>
            );
          })}
        </tbody>
        {monthlyTotals && (
          <tfoot>
            <tr>
              <td colSpan={2}>Soucet</td>
              <td className="cell-right cell-buy">{monthlyTotals.kwh_total?.toFixed(2)}</td>
              <td className="cell-right cell-buy">{monthlyTotals.cost_total?.toFixed(2)}</td>
              <td className="cell-right cell-sell">{monthlyTotals.export_kwh_total?.toFixed(2)}</td>
              <td className="cell-right cell-sell">{monthlyTotals.sell_total?.toFixed(2)}</td>
            </tr>
          </tfoot>
        )}
      </table>
    );
  }

  return (
    <div className="card card-top">
      <div className="card-header">
        <h3>Souhrn za mesic - {formatMonthLabel(selectedMonth)}</h3>
      </div>
      <div className="toolbar">
        <input type="month" value={selectedMonth} onChange={(e) => setSelectedMonth(e.target.value)} />
        <button
          onClick={() => {
            const today = new Date();
            const y = today.getFullYear();
            const m = String(today.getMonth() + 1).padStart(2, "0");
            setSelectedMonth(`${y}-${m}`);
          }}
        >
          Tento mesic
        </button>
      </div>
      {content}
    </div>
  );
};

export default MonthlySummaryCard;
