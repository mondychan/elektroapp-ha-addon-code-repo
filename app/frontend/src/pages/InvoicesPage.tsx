import React, { useEffect, useMemo, useState } from "react";
import { elektroappApi } from "../api/elektroappApi";
import BillingCard from "../components/BillingCard";
import DataCard from "../components/common/DataCard";

const currentMonth = () => new Date().toISOString().slice(0, 7);
const documentLabels: Record<string, string> = {
  invoice_pdf: "Vyúčtovací faktura",
  supply_detail_xlsx: "Detail dodávky",
  export_detail_xlsx: "Detail výkupu",
};
const fieldLabels: Record<string, string> = {
  quantity_mwh: "Množství",
  total_czk: "Částka",
  supply_without_vat: "Dodávka bez DPH",
  commercial_without_vat: "Obchodní platby bez DPH",
  regulated_without_vat: "Regulované platby bez DPH",
  export_total: "Výkup elektřiny",
};

const documentPeriod = (document: any) => {
  const parsed = document.parsed || {};
  const from = parsed.period_from;
  const to = parsed.period_to;
  if (from && to) {
    const formatDate = (input: string) => new Date(`${input}T12:00:00`).toLocaleDateString("cs-CZ");
    return { key: `${from}|${to}`, label: `${formatDate(from)} - ${formatDate(to)}` };
  }
  const label = parsed.period || "Neurčené období";
  return { key: label, label };
};

const InvoicesPage = ({ maxMonth }: { maxMonth: string }) => {
  const [month, setMonth] = useState(currentMonth());
  const [billingData, setBillingData] = useState<any>(null);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [auditResults, setAuditResults] = useState<Record<string, any>>({});
  const [auditingIds, setAuditingIds] = useState<Set<string>>(new Set());
  const [deletingIds, setDeletingIds] = useState<Set<string>>(new Set());
  const [message, setMessage] = useState("");

  const loadDocuments = async () => setDocuments((await elektroappApi.getInvoices())?.documents || []);
  useEffect(() => {
    setLoading(true); setBillingError(null);
    elektroappApi.getBillingMonth(month).then(setBillingData).catch((error) => setBillingError(error?.response?.data?.detail || "Nepodařilo se načíst virtuální fakturu.")).finally(() => setLoading(false));
  }, [month]);
  useEffect(() => { loadDocuments(); }, []);

  const upload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files || []); if (!files.length) return;
    setMessage("Nahrávám a zpracovávám dokumenty...");
    try { await elektroappApi.uploadInvoices(files); await loadDocuments(); setMessage(`Zpracováno dokumentů: ${files.length}`); }
    catch (error: any) { setMessage(error?.response?.data?.detail || "Dokumenty se nepodařilo zpracovat."); }
    event.target.value = "";
  };

  const audit = async (id: string) => {
    setAuditingIds((previous) => new Set(previous).add(id));
    try { const result = await elektroappApi.auditInvoice(id); setAuditResults((previous) => ({ ...previous, [id]: result })); }
    catch (error: any) { setMessage(error?.response?.data?.detail || "Audit se nepodařilo spustit."); }
    finally { setAuditingIds((previous) => { const next = new Set(previous); next.delete(id); return next; }); }
  };

  const remove = async (id: string) => {
    setDeletingIds((previous) => new Set(previous).add(id));
    try { await elektroappApi.deleteInvoice(id); await loadDocuments(); }
    catch (error: any) { setMessage(error?.response?.data?.detail || "Dokument se nepodařilo smazat."); }
    finally { setDeletingIds((previous) => { const next = new Set(previous); next.delete(id); return next; }); }
  };

  const documentGroups = useMemo(() => {
    const groups = new Map<string, { label: string; documents: any[] }>();
    documents.forEach((document) => {
      const period = documentPeriod(document);
      const group: { label: string; documents: any[] } = groups.get(period.key) || { label: period.label, documents: [] };
      group.documents.push(document);
      groups.set(period.key, group);
    });
    return Array.from(groups.entries()).sort(([left], [right]) => right.localeCompare(left, "cs"));
  }, [documents]);

  return <div className="invoice-page">
    <DataCard title="Virtuální vyúčtování" loading={loading} error={billingError}>
      <BillingCard billingMode="month" setBillingMode={() => {}} billingMonth={month} setBillingMonth={setMonth} billingYear={month.slice(0, 4)} setBillingYear={() => {}} maxMonth={maxMonth} maxYear={maxMonth.slice(0, 4)} billingData={billingData} billingLoading={loading} billingError={billingError} />
    </DataCard>
    <DataCard title="Skutečné faktury a audit">
      <label className="invoice-upload"><input type="file" accept=".pdf,.xlsx" multiple onChange={upload} /><span>Nahrát PDF nebo XLSX</span></label>
      {message && <div className="config-muted invoice-page__message">{message}</div>}
      <div className="invoice-document-list">
        {documentGroups.map(([periodKey, group]) => <section className="invoice-period-group" key={periodKey}>
          <header className="invoice-period-group__header"><h3>{group.label}</h3><span>{group.documents.length} {group.documents.length === 1 ? "dokument" : group.documents.length < 5 ? "dokumenty" : "dokumentů"}</span></header>
          {group.documents.map((document) => {
            const parsed = document.parsed || {}; const result = auditResults[document.id];
            const auditing = auditingIds.has(document.id); const deleting = deletingIds.has(document.id);
            const statusLabel = result?.overall === "match" ? "Shoda" : result?.overall === "warning" ? "Varování" : result?.overall === "error" ? "Chyba" : "Neauditováno";
            return <article className="invoice-document" key={document.id} aria-busy={auditing || deleting}>
              <div className="invoice-document__identity"><span className="invoice-document__type">{documentLabels[parsed.document_type] || "Dokument"}</span><strong title={document.filename}>{document.filename}</strong></div>
              <span className={`invoice-status invoice-status--${result?.overall || "idle"}`}>{auditing ? "Probíhá audit" : statusLabel}</span>
              <div className="invoice-document__actions">
                <button type="button" onClick={() => audit(document.id)} disabled={auditing || deleting}>{auditing && <span className="invoice-spinner" aria-hidden="true" />}{auditing ? "Načítám data" : "Provést audit"}</button>
                <button type="button" className="ghost-button" onClick={() => remove(document.id)} disabled={auditing || deleting}>{deleting ? "Mažu…" : "Smazat"}</button>
              </div>
              {auditing && <div className="invoice-audit-progress"><span className="invoice-spinner" aria-hidden="true" /><span>Načítám historické ceny a porovnávám dokument…</span></div>}
              {result && !auditing && <div className={`invoice-audit invoice-audit--${result.overall}`}>
                <table><thead><tr><th>Položka</th><th>Faktura</th><th>Aplikace</th><th>Rozdíl</th><th>Odchylka</th></tr></thead><tbody>{result.comparisons?.map((item: any) => <tr key={item.field}><th>{fieldLabels[item.field] || item.field}</th><td>{item.expected}</td><td>{item.actual}</td><td>{item.difference}</td><td>{item.difference_percent} %</td></tr>)}</tbody></table>
              </div>}
            </article>;
          })}
        </section>)}
        {!documents.length && <div className="config-muted">Zatím nebyly nahrány žádné faktury.</div>}
      </div>
    </DataCard>
  </div>;
};

export default InvoicesPage;
