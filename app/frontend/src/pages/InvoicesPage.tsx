import React, { useEffect, useState } from "react";
import { elektroappApi } from "../api/elektroappApi";
import BillingCard from "../components/BillingCard";
import DataCard from "../components/common/DataCard";

const currentMonth = () => new Date().toISOString().slice(0, 7);

const InvoicesPage = ({ maxMonth }: { maxMonth: string }) => {
  const [month, setMonth] = useState(currentMonth());
  const [billingData, setBillingData] = useState<any>(null);
  const [billingError, setBillingError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [documents, setDocuments] = useState<any[]>([]);
  const [auditResults, setAuditResults] = useState<Record<string, any>>({});
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
    try { const result = await elektroappApi.auditInvoice(id); setAuditResults((previous) => ({ ...previous, [id]: result })); }
    catch (error: any) { setMessage(error?.response?.data?.detail || "Audit se nepodařilo spustit."); }
  };

  return <div className="invoice-page">
    <DataCard title="Virtuální vyúčtování" loading={loading} error={billingError}>
      <BillingCard billingMode="month" setBillingMode={() => {}} billingMonth={month} setBillingMonth={setMonth} billingYear={month.slice(0, 4)} setBillingYear={() => {}} maxMonth={maxMonth} maxYear={maxMonth.slice(0, 4)} billingData={billingData} billingLoading={loading} billingError={billingError} />
    </DataCard>
    <DataCard title="Skutečné faktury a audit">
      <label className="invoice-upload"><input type="file" accept=".pdf,.xlsx" multiple onChange={upload} /><span>Nahrát PDF nebo XLSX</span></label>
      {message && <div className="config-muted invoice-page__message">{message}</div>}
      <div className="invoice-document-list">
        {documents.map((document) => {
          const parsed = document.parsed || {}; const result = auditResults[document.id];
          return <div className="invoice-document" key={document.id}>
            <div><strong>{document.filename}</strong><span>{parsed.document_type || "Dokument"} · {parsed.period || [parsed.period_from, parsed.period_to].filter(Boolean).join(" - ")}</span></div>
            <div className="invoice-document__actions"><button type="button" onClick={() => audit(document.id)}>Provést audit</button><button type="button" className="ghost-button" onClick={async () => { await elektroappApi.deleteInvoice(document.id); await loadDocuments(); }}>Smazat</button></div>
            {result && <div className={`invoice-audit invoice-audit--${result.overall}`}><strong>{result.overall === "match" ? "Shoda" : result.overall === "warning" ? "Varování" : "Chyba"}</strong>{result.comparisons?.map((item: any) => <span key={item.field}>{item.field}: faktura {item.expected}, aplikace {item.actual}, rozdíl {item.difference} ({item.difference_percent} %)</span>)}</div>}
          </div>;
        })}
        {!documents.length && <div className="config-muted">Zatím nebyly nahrány žádné faktury.</div>}
      </div>
    </DataCard>
  </div>;
};

export default InvoicesPage;
