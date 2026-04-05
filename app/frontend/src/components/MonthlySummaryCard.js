import React, { useState, useMemo } from "react";
import MonthNavigator from "./MonthNavigator";
import { formatDate, formatMonthLabel } from "../utils/formatters";

const MonthlySummaryCard = ({
  selectedMonth,
  setSelectedMonth,
  monthlySummary,
  monthlyTotals,
  monthlyError,
}) => {
  const [sortConfig, setSortConfig] = useState({ key: "date", direction: "asc" });

  const sortedData = useMemo(() => {
    let sortableData = [...monthlySummary].map(day => {
      const kwhBought = day.kwh_total || 0;
      const kwhSold = day.export_kwh_total || 0;
      const netKwh = (day.kwh_total != null || day.export_kwh_total != null) ? kwhBought - kwhSold : null;
      
      const costBought = day.cost_total || 0;
      const costSold = day.sell_total || 0;
      const netCost = (day.cost_total != null || day.sell_total != null) ? costBought - costSold : null;

      return {
        ...day,
        netKwh,
        netCost
      };
    });

    if (sortConfig.key) {
      sortableData.sort((a, b) => {
        let aVal = a[sortConfig.key];
        let bVal = b[sortConfig.key];

        if (aVal == null) return 1;
        if (bVal == null) return -1;

        if (aVal < bVal) {
          return sortConfig.direction === "asc" ? -1 : 1;
        }
        if (aVal > bVal) {
          return sortConfig.direction === "asc" ? 1 : -1;
        }
        return 0;
      });
    }
    return sortableData;
  }, [monthlySummary, sortConfig]);

  const requestSort = (key) => {
    let direction = "asc";
    if (sortConfig.key === key && sortConfig.direction === "asc") {
      direction = "desc";
    }
    setSortConfig({ key, direction });
  };

  const getSortIcon = (key) => {
    if (sortConfig.key !== key) return "↕";
    return sortConfig.direction === "asc" ? "↑" : "↓";
  };

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

  if (monthlyError) return null; // Handled by DataCard wrapper
  if (!monthlySummary.length && !monthlyError) return null; // Handled by DataCard wrapper

  return (
    <div className="summary-card-inner">
      <MonthNavigator value={selectedMonth} onChange={setSelectedMonth} />
      <div className="table-responsive sticky-container" style={{ maxHeight: "400px" }}>
        <table className="data-table table-spaced">
          <thead className="sticky-header">
            <tr>
              <th className="cell-left sortable" onClick={() => requestSort("date")}>
                Den {getSortIcon("date")}
              </th>
              <th className="cell-left">Datum</th>
              <th className="cell-right sortable" onClick={() => requestSort("kwh_total")}>
                Nákup (kWh) {getSortIcon("kwh_total")}
              </th>
              <th className="cell-right sortable" onClick={() => requestSort("cost_total")}>
                Náklady (Kč) {getSortIcon("cost_total")}
              </th>
              <th className="cell-right sortable" onClick={() => requestSort("export_kwh_total")}>
                Prodej (kWh) {getSortIcon("export_kwh_total")}
              </th>
              <th className="cell-right sortable" onClick={() => requestSort("sell_total")}>
                Tržby (Kč) {getSortIcon("sell_total")}
              </th>
              <th className="cell-right sortable" onClick={() => requestSort("netKwh")}>
                Netto (kWh) {getSortIcon("netKwh")}
              </th>
              <th className="cell-right sortable" onClick={() => requestSort("netCost")}>
                Netto (Kč) {getSortIcon("netCost")}
              </th>
            </tr>
          </thead>
          <tbody>
            {sortedData.map((day) => {
              const dt = new Date(`${day.date}T00:00:00`);
              const dayName = dt.toLocaleDateString("cs-CZ", { weekday: "short" });
              const kwhClass = day.netKwh > 0 ? "cell-buy" : (day.netKwh < 0 ? "cell-sell" : "");
              const costClass = day.netCost > 0 ? "cell-buy" : (day.netCost < 0 ? "cell-sell" : "");

              return (
                <tr key={day.date}>
                  <td>{dayName}</td>
                  <td>{formatDate(dt)}</td>
                  <td className="cell-right">{day.kwh_total == null ? "-" : day.kwh_total.toFixed(2)}</td>
                  <td className="cell-right cell-buy">{day.cost_total == null ? "-" : day.cost_total.toFixed(2)}</td>
                  <td className="cell-right">{day.export_kwh_total == null ? "-" : day.export_kwh_total.toFixed(2)}</td>
                  <td className="cell-right cell-sell">{day.sell_total == null ? "-" : day.sell_total.toFixed(2)}</td>
                  <td className={`cell-right ${kwhClass}`}>{day.netKwh == null ? "-" : (day.netKwh > 0 ? "+" : "") + day.netKwh.toFixed(2)}</td>
                  <td className={`cell-right ${costClass}`}>{day.netCost == null ? "-" : (day.netCost > 0 ? "+" : "") + day.netCost.toFixed(2)}</td>
                </tr>
              );
            })}
          </tbody>
          {monthlyTotals && (
            <tfoot>
              <tr className="sticky-footer">
                <td colSpan={2}>Součet</td>
                <td className="cell-right">{monthlyTotals.kwh_total?.toFixed(2)}</td>
                <td className="cell-right cell-buy">{monthlyTotals.cost_total?.toFixed(2)}</td>
                <td className="cell-right">{monthlyTotals.export_kwh_total?.toFixed(2)}</td>
                <td className="cell-right cell-sell">{monthlyTotals.sell_total?.toFixed(2)}</td>
                <td className={`cell-right ${footerKwhClass}`}>{footerNetKwh == null ? "-" : (footerNetKwh > 0 ? "+" : "") + footerNetKwh.toFixed(2)}</td>
                <td className={`cell-right ${footerCostClass}`}>{footerNetCost == null ? "-" : (footerNetCost > 0 ? "+" : "") + footerNetCost.toFixed(2)}</td>
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    </div>
  );
};

export default MonthlySummaryCard;
