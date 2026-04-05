import React from "react";
import MonthNavigator from "./MonthNavigator";
import { formatDate, formatMonthLabel } from "../utils/formatters";

const MonthlySummaryCard = ({
  selectedMonth,
  setSelectedMonth,
  monthlySummary,
  monthlyTotals,
  monthlyError,
}) => {
  let footerNetKwh = null;
  let footerNetCost = null;
  let footerKwhClass = "";
  let footerCostClass = "";

  if (monthlyTotals) {
    const kwhBought = monthlyTotals.kwh_total || 0;
    const kwhSold = monthlyTotals.export_kwh_total || 0;
    if (monthlyTotals.kwh_total != null || monthlyTotals.export_kwh_total != null) {
      footerNetKwh = kwhBought - kwhSold;
      footerKwhClass = footerNetKwh > 0 ? "cell-buy" : (footerNetKwh < 0 ? "cell-sell" : "");
    }
    
    const costBought = monthlyTotals.cost_total || 0;
    const costSold = monthlyTotals.sell_total || 0;
    if (monthlyTotals.cost_total != null || monthlyTotals.sell_total != null) {
      footerNetCost = costBought - costSold;
      footerCostClass = footerNetCost > 0 ? "cell-buy" : (footerNetCost < 0 ? "cell-sell" : "");
    }
  }

  let content = null;
  if (monthlyError) {
    content = <div className="alert error">{monthlyError}</div>;
  } else if (!monthlySummary.length) {
    content = <div className="muted-note">Mesicni souhrn neni k dispozici.</div>;
  } else {
    content = (
      <div className="table-responsive">
        <table className="data-table table-spaced">
          <thead>
            <tr>
              <th className="cell-left">Den</th>
              <th className="cell-left">Datum</th>
              <th className="cell-right cell-buy">Nakup (kWh)</th>
              <th className="cell-right cell-buy">Naklady (Kc)</th>
              <th className="cell-right cell-sell">Prodej (kWh)</th>
              <th className="cell-right cell-sell">Trzby (Kc)</th>
              <th className="cell-right">Netto (kWh)</th>
              <th className="cell-right">Netto (Kc)</th>
            </tr>
          </thead>
          <tbody>
            {monthlySummary.map((day) => {
              const dt = new Date(`${day.date}T00:00:00`);
              const dayName = dt.toLocaleDateString("cs-CZ", { weekday: "short" });
              
              const kwhBought = day.kwh_total || 0;
              const kwhSold = day.export_kwh_total || 0;
              const netKwh = (day.kwh_total != null || day.export_kwh_total != null) ? kwhBought - kwhSold : null;
              
              const costBought = day.cost_total || 0;
              const costSold = day.sell_total || 0;
              const netCost = (day.cost_total != null || day.sell_total != null) ? costBought - costSold : null;
              
              const kwhClass = netKwh > 0 ? "cell-buy" : (netKwh < 0 ? "cell-sell" : "");
              const costClass = netCost > 0 ? "cell-buy" : (netCost < 0 ? "cell-sell" : "");

              return (
                <tr key={day.date}>
                  <td>{dayName}</td>
                  <td>{formatDate(dt)}</td>
                  <td className="cell-right cell-buy">{day.kwh_total == null ? "-" : day.kwh_total.toFixed(2)}</td>
                  <td className="cell-right cell-buy">{day.cost_total == null ? "-" : day.cost_total.toFixed(2)}</td>
                  <td className="cell-right cell-sell">{day.export_kwh_total == null ? "-" : day.export_kwh_total.toFixed(2)}</td>
                  <td className="cell-right cell-sell">{day.sell_total == null ? "-" : day.sell_total.toFixed(2)}</td>
                  <td className={`cell-right ${kwhClass}`}>{netKwh == null ? "-" : (netKwh > 0 ? "+" : "") + netKwh.toFixed(2)}</td>
                  <td className={`cell-right ${costClass}`}>{netCost == null ? "-" : (netCost > 0 ? "+" : "") + netCost.toFixed(2)}</td>
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
                <td className={`cell-right ${footerKwhClass}`}>{footerNetKwh == null ? "-" : (footerNetKwh > 0 ? "+" : "") + footerNetKwh.toFixed(2)}</td>
                <td className={`cell-right ${footerCostClass}`}>{footerNetCost == null ? "-" : (footerNetCost > 0 ? "+" : "") + footerNetCost.toFixed(2)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    );
  }

  return (
    <div className="card card-top">
      <div className="card-header">
        <h3>Souhrn za mesic - {formatMonthLabel(selectedMonth)}</h3>
      </div>
      <MonthNavigator value={selectedMonth} onChange={setSelectedMonth} />
      {content}
    </div>
  );
};

export default MonthlySummaryCard;
