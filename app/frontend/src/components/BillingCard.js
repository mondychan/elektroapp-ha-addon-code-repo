import React from "react";
import MonthNavigator from "./MonthNavigator";
import YearNavigator from "./YearNavigator";
import { formatCurrency, formatMonthLabel } from "../utils/formatters";

const BillingCard = ({
  billingMode,
  setBillingMode,
  billingMonth,
  setBillingMonth,
  billingYear,
  setBillingYear,
  maxMonth,
  maxYear,
  billingData,
  billingLoading,
  billingError,
}) => {
  const now = new Date();
  const currentYear = now.getFullYear();
  const currentMonth = now.getMonth() + 1;

  const isPastMonth = (monthStr) => {
    if (!monthStr) return false;
    const [y, m] = monthStr.split("-").map(Number);
    if (!y || !m) return false;
    return y < currentYear || (y === currentYear && m < currentMonth);
  };

  if (billingLoading || billingError) return null; // Handled by DataCard

  const renderBillingMonth = () => {
    if (!billingData) return null;
    const actual = billingData.actual || {};
    const projected = billingData.projected || {};
    const targetMonth = billingData.month || billingMonth;
    const pastMonth = isPastMonth(targetMonth);
    const daysWithData = billingData.days_with_data ?? 0;
    const daysInMonth = billingData.days_in_month ?? 0;
    const projectedNet = projected.net_total ?? projected.total_cost;
    const actualLabel = pastMonth
      ? "Náklady měsíce"
      : `Náklady za ${daysWithData} dní z ${daysInMonth}`;

    const totalCostClass = (actual.total_cost || 0) > 0 ? "cell-buy" : ((actual.total_cost || 0) < 0 ? "cell-sell" : "");

    return (
      <div className="billing-content">
        <div className="table-responsive">
          <table className="data-table table-spaced">
            <tbody>
              <tr>
                <td>Nákup energie</td>
                <td className="cell-right">
                  {actual.kwh_total == null ? "-" : `${actual.kwh_total.toFixed(2)} kWh`}
                </td>
              </tr>
              <tr>
                <td className="cell-buy">Variabilní náklady</td>
                <td className="cell-right cell-buy">{formatCurrency(actual.variable_cost)}</td>
              </tr>
              <tr>
                <td className="cell-buy">Fixní poplatky</td>
                <td className="cell-right cell-buy">{formatCurrency(actual.fixed_cost)}</td>
              </tr>
              <tr>
                <td className="cell-sell">Tržby z prodeje</td>
                <td className="cell-right cell-sell">{formatCurrency(actual.sell_total)}</td>
              </tr>
              <tr style={{ borderTop: "2px solid var(--border)", fontWeight: "600" }}>
                <td className={totalCostClass}>{actualLabel}</td>
                <td className={`cell-right ${totalCostClass}`}>{formatCurrency(actual.total_cost)}</td>
              </tr>
              {!pastMonth && (
                <tr style={{ fontStyle: "italic", opacity: 0.8 }}>
                  <td>Odhad pro celý měsíc</td>
                  <td className="cell-right">{formatCurrency(projectedNet)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderBillingYear = () => {
    if (!billingData || !billingData.months) return null;
    const showProjectionColumn = billingData.year === currentYear;
    return (
      <div className="table-responsive sticky-container" style={{ maxHeight: "400px" }}>
        <table className="data-table table-spaced">
          <thead className="sticky-header">
            <tr>
              <th className="cell-left">Měsíc</th>
              <th className="cell-right">Náklady měsíce</th>
              {showProjectionColumn && <th className="cell-right">Projekce (po prodeji)</th>}
            </tr>
          </thead>
          <tbody>
            {billingData.months.map((item) => {
              const cost = item.actual?.total_cost || 0;
              const costClass = cost > 0 ? "cell-buy" : (cost < 0 ? "cell-sell" : "");
              return (
                <tr key={item.month}>
                  <td>{formatMonthLabel(item.month)}</td>
                  <td className={`cell-right ${costClass}`}>{formatCurrency(item.actual?.total_cost)}</td>
                  {showProjectionColumn && (
                    <td className="cell-right">
                      {isPastMonth(item.month) ? "-" : formatCurrency(item.projected?.net_total ?? item.projected?.total_cost)}
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
          {billingData.totals && (
            <tfoot>
              <tr className="sticky-footer">
                <td>Součet</td>
                <td className={`cell-right ${(billingData.totals.actual?.total_cost || 0) > 0 ? "cell-buy" : ((billingData.totals.actual?.total_cost || 0) < 0 ? "cell-sell" : "")}`}>
                  {formatCurrency(billingData.totals.actual?.total_cost)}
                </td>
                {showProjectionColumn && (
                  <td className="cell-right">
                    {formatCurrency(billingData.totals.projected?.net_total ?? billingData.totals.projected?.total_cost)}
                  </td>
                )}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
    );
  };

  return (
    <div className="billing-card-inner">
      <div className="toolbar" style={{ marginBottom: "1rem", display: "flex", gap: "1rem", alignItems: "center" }}>
        <select 
          className="select-styled" 
          value={billingMode} 
          onChange={(e) => setBillingMode(e.target.value)}
          style={{ padding: "8px", borderRadius: "8px", background: "var(--panel-2)", border: "1px solid var(--border)", color: "var(--text)" }}
        >
          <option value="month">Měsíc</option>
          <option value="year">Rok</option>
        </select>
        {billingMode === "month" ? (
          <MonthNavigator value={billingMonth} onChange={setBillingMonth} maxMonth={maxMonth} />
        ) : (
          <YearNavigator value={billingYear} onChange={setBillingYear} maxYear={maxYear} />
        )}
      </div>
      {billingMode === "month" && renderBillingMonth()}
      {billingMode === "year" && renderBillingYear()}
    </div>
  );
};

export default BillingCard;
