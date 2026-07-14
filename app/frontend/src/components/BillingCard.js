import React from "react";
import MonthNavigator from "./MonthNavigator";
import YearNavigator from "./YearNavigator";
import { formatCurrency, formatMonthLabel } from "../utils/formatters";
import { elektroappApi } from "../api/elektroappApi";

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

  const downloadInvoiceDetail = async (kind) => {
    const csvData = await elektroappApi.getInvoiceDetailCsv(billingMonth, kind);
    const blob = new Blob([csvData], { type: "text/csv;charset=utf-8" });
    const link = document.createElement("a");
    link.href = URL.createObjectURL(blob);
    link.download = `elektroapp-detail-${kind === "supply" ? "dodavka" : "vykup"}-${billingMonth}.csv`;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(link.href);
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
    const actualValue = actual.net_total ?? actual.total_cost;
    const settlementEstimate = billingData.settlement_estimate;
    const invoice = billingData.invoice?.[pastMonth ? "actual" : "projected"];
    const dphMultiplier = 1 + Number(billingData.invoice?.dph_percent || 0) / 100;
    const invoiceKwh = (invoice?.regulated?.distribution_nt_kwh || 0) + (invoice?.regulated?.distribution_vt_kwh || 0);
    const invoiceRow = (label, quantity, unit, amount, className = "") => (
      <tr key={label}>
        <td className={className}>{label}</td>
        <td className="cell-right">{quantity == null ? "-" : Number(quantity).toFixed(unit === "kWh" ? 2 : 0)}</td>
        <td>{unit}</td>
        <td className={`cell-right ${className}`}>{formatCurrency(amount)}</td>
        <td className={`cell-right ${className}`}>{formatCurrency(amount == null ? null : amount * dphMultiplier)}</td>
      </tr>
    );
    const actualLabel = pastMonth
      ? "Náklady měsíce"
      : `Náklady za ${daysWithData} dní z ${daysInMonth}`;
    const totalCostClass = (actualValue || 0) > 0 ? "cell-buy" : ((actualValue || 0) < 0 ? "cell-sell" : "");

    return (
      <div className="billing-content">
        {invoice && (
          <div className="table-responsive invoice-preview">
            <div className="invoice-preview__status">{pastMonth ? "Skutečné vyúčtování" : "Průběžný odhad za celý měsíc"}</div>
            {billingData.invoice?.price_provider !== "ote" && billingData.invoice?.price_provider !== "ote-cr.cz" && (
              <div className="invoice-preview__note">Pro přímé porovnání EUR/MWh a kurzu ČNB v detailním CSV nastavte zdroj cen OTE.</div>
            )}
            <table className="data-table table-spaced invoice-preview__table">
              <thead>
                <tr>
                  <th className="cell-left">Položka</th>
                  <th className="cell-right">Množství</th>
                  <th>Jednotka</th>
                  <th className="cell-right">Bez DPH</th>
                  <th className="cell-right">S DPH</th>
                </tr>
              </thead>
              <tbody>
                <tr className="invoice-preview__section"><td colSpan="5">Obchodní platby</td></tr>
                {invoiceRow("Stálý plat", billingData.days_in_month, "den", invoice.commercial?.standing_charge, "cell-buy")}
                {invoiceRow("Cena za služby obchodu", invoiceKwh, "kWh", invoice.commercial?.supplier_service, "cell-buy")}
                {invoiceRow("Cena za silovou elektřinu", invoiceKwh, "kWh", invoice.commercial?.spot_energy, "cell-buy")}
                <tr className="invoice-preview__subtotal"><td colSpan="3">Součet obchodní platby</td><td className="cell-right">{formatCurrency(invoice.commercial?.total)}</td><td className="cell-right">{formatCurrency(invoice.commercial?.total * dphMultiplier)}</td></tr>
                <tr className="invoice-preview__section"><td colSpan="5">Regulované platby</td></tr>
                {invoiceRow("Distribuované množství elektřiny NT", invoice.regulated?.distribution_nt_kwh, "kWh", invoice.regulated?.distribution_nt, "cell-buy")}
                {invoiceRow("Distribuované množství elektřiny VT", invoice.regulated?.distribution_vt_kwh, "kWh", invoice.regulated?.distribution_vt, "cell-buy")}
                {invoiceRow("Měsíční plat za příkon - jistič", 1, "měsíc", invoice.regulated?.breaker, "cell-buy")}
                {invoiceRow("Cena za provoz nesíťové infrastruktury", 1, "měsíc", invoice.regulated?.infrastructure, "cell-buy")}
                {invoiceRow("Cena na podporu výkupu elektřiny (OZE)", invoiceKwh, "kWh", invoice.regulated?.oze, "cell-buy")}
                {invoiceRow("Daň z elektřiny", invoiceKwh, "kWh", invoice.regulated?.electricity_tax, "cell-buy")}
                {invoiceRow("Systémové služby ČEPS, a.s.", invoiceKwh, "kWh", invoice.regulated?.system_services, "cell-buy")}
                <tr className="invoice-preview__subtotal"><td colSpan="3">Součet regulované platby</td><td className="cell-right">{formatCurrency(invoice.regulated?.total)}</td><td className="cell-right">{formatCurrency(invoice.regulated?.total * dphMultiplier)}</td></tr>
              </tbody>
              <tfoot>
                <tr><td colSpan="3">Dodávka energií</td><td className="cell-right">{formatCurrency(invoice.supply_without_vat)}</td><td className="cell-right">{formatCurrency(invoice.supply_with_vat)}</td></tr>
                <tr className="cell-sell"><td colSpan="4">Výkup elektřiny</td><td className="cell-right">{formatCurrency(-Number(invoice.sell_total || 0))}</td></tr>
                {billingData.monthly_advance > 0 && <tr className="cell-sell"><td colSpan="4">Vyúčtované zálohy</td><td className="cell-right">{formatCurrency(-Number(billingData.monthly_advance))}</td></tr>}
                <tr><td colSpan="4">Výsledek vyúčtování</td><td className="cell-right">{formatCurrency(invoice.net_after_sell - Number(billingData.monthly_advance || 0))}</td></tr>
              </tfoot>
            </table>
          </div>
        )}
        {!invoice && <div className="table-responsive">
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
                <td className={`cell-right ${totalCostClass}`}>{formatCurrency(actualValue)}</td>
              </tr>
              {!pastMonth && (
                <tr style={{ fontStyle: "italic", opacity: 0.8 }}>
                  <td>Odhad pro celý měsíc</td>
                  <td className="cell-right">{formatCurrency(projected.net_total ?? projected.total_cost)}</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>}
        {!pastMonth && settlementEstimate != null && (
          <div className={`billing-settlement-estimate ${settlementEstimate >= 0 ? "is-refund" : "is-surcharge"}`}>
            <strong>{settlementEstimate >= 0 ? "Odhad vratky" : "Odhad doplatku"}: </strong>
            {Math.abs(settlementEstimate).toLocaleString("cs-CZ", { minimumFractionDigits: 2, maximumFractionDigits: 2 })} Kč
            <span>Záloha {billingData.monthly_advance?.toLocaleString("cs-CZ")} Kč</span>
          </div>
        )}
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
              const cost = item.actual?.net_total ?? item.actual?.total_cost ?? 0;
              const costClass = cost > 0 ? "cell-buy" : (cost < 0 ? "cell-sell" : "");
              return (
                <tr key={item.month}>
                  <td>{formatMonthLabel(item.month)}</td>
                  <td className={`cell-right ${costClass}`}>{formatCurrency(cost)}</td>
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
                <td className={`cell-right ${(billingData.totals.actual?.net_total ?? billingData.totals.actual?.total_cost ?? 0) > 0 ? "cell-buy" : ((billingData.totals.actual?.net_total ?? billingData.totals.actual?.total_cost ?? 0) < 0 ? "cell-sell" : "")}`}>
                  {formatCurrency(billingData.totals.actual?.net_total ?? billingData.totals.actual?.total_cost)}
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
      {billingMode === "month" && (
        <div className="invoice-export-actions">
          <button type="button" className="ghost-button" onClick={() => downloadInvoiceDetail("supply")}>Detail dodávky CSV</button>
          <button type="button" className="ghost-button" onClick={() => downloadInvoiceDetail("export")}>Detail výkupu CSV</button>
        </div>
      )}
      {billingMode === "year" && renderBillingYear()}
    </div>
  );
};

export default BillingCard;
