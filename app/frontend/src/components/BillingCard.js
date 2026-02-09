import React from "react";
import { formatCurrency, formatMonthLabel } from "../utils/formatters";

const BillingCard = ({
  billingMode,
  setBillingMode,
  billingMonth,
  setBillingMonth,
  billingYear,
  setBillingYear,
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
      ? "Naklady mesice"
      : `Naklady za ${daysWithData} dni z ${daysInMonth}`;

    return (
      <div>
        <div className="summary">
          {actualLabel}: {formatCurrency(actual.total_cost)}
          {!pastMonth && ` | Odhad pro tento mesic: ${formatCurrency(projectedNet)}`}
        </div>
        {!pastMonth && (
          <div className="config-muted">
            Data za {daysWithData} dni z {daysInMonth}.
          </div>
        )}
        <table className="data-table table-spaced">
          <tbody>
            <tr>
              <td className="cell-buy">Nakup</td>
              <td className="cell-right cell-buy">
                {actual.kwh_total == null ? "-" : `${actual.kwh_total.toFixed(2)} kWh`}
              </td>
            </tr>
            <tr>
              <td className="cell-buy">Variabilni naklady</td>
              <td className="cell-right cell-buy">{formatCurrency(actual.variable_cost)}</td>
            </tr>
            <tr>
              <td className="cell-buy">Fixni poplatky</td>
              <td className="cell-right cell-buy">{formatCurrency(actual.fixed_cost)}</td>
            </tr>
            <tr>
              <td className="cell-sell">Trzby</td>
              <td className="cell-right cell-sell">{formatCurrency(actual.sell_total)}</td>
            </tr>
            <tr>
              <td className="cell-buy">{actualLabel}</td>
              <td className="cell-right cell-buy">{formatCurrency(actual.total_cost)}</td>
            </tr>
            {!pastMonth && (
              <tr>
                <td>Odhad pro tento mesic</td>
                <td className="cell-right">{formatCurrency(projectedNet)}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
    );
  };

  const renderBillingYear = () => {
    if (!billingData || !billingData.months) return null;
    const showProjectionColumn = billingData.year === currentYear;
    return (
      <table className="data-table table-spaced">
        <thead>
          <tr>
            <th className="cell-left">Mesic</th>
            <th className="cell-right cell-buy">Naklady mesice</th>
            {showProjectionColumn && <th className="cell-right">Projekce mesice (po prodeji)</th>}
          </tr>
        </thead>
        <tbody>
          {billingData.months.map((item) => (
            <tr key={item.month}>
              <td>{formatMonthLabel(item.month)}</td>
              <td className="cell-right cell-buy">{formatCurrency(item.actual?.total_cost)}</td>
              {showProjectionColumn && (
                <td className="cell-right">
                  {isPastMonth(item.month) ? "-" : formatCurrency(item.projected?.net_total ?? item.projected?.total_cost)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
        {billingData.totals && (
          <tfoot>
            <tr>
              <td>Soucet</td>
              <td className="cell-right cell-buy">
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
    );
  };

  return (
    <div className="card card-top">
      <div className="card-header">
        <h3>Odhad vyuctovani</h3>
      </div>
      <div className="toolbar">
        <select value={billingMode} onChange={(e) => setBillingMode(e.target.value)}>
          <option value="month">Mesic</option>
          <option value="year">Rok</option>
        </select>
        {billingMode === "month" ? (
          <>
            <input type="month" value={billingMonth} onChange={(e) => setBillingMonth(e.target.value)} />
            <button
              onClick={() => {
                const today = new Date();
                const y = today.getFullYear();
                const m = String(today.getMonth() + 1).padStart(2, "0");
                setBillingMonth(`${y}-${m}`);
              }}
            >
              Tento mesic
            </button>
          </>
        ) : (
          <>
            <input
              type="number"
              min="2000"
              max="2100"
              value={billingYear}
              onChange={(e) => setBillingYear(e.target.value)}
            />
            <button onClick={() => setBillingYear(String(new Date().getFullYear()))}>Tento rok</button>
          </>
        )}
      </div>
      {billingError && <div className="alert error">{billingError}</div>}
      {billingLoading && <div className="config-muted">Pocitam odhad vyuctovani...</div>}
      {!billingLoading && billingMode === "month" && renderBillingMonth()}
      {!billingLoading && billingMode === "year" && renderBillingYear()}
    </div>
  );
};

export default BillingCard;
