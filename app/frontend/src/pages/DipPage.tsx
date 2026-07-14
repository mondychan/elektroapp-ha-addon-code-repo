import React, { useEffect, useState } from "react";
import { elektroappApi } from "../api/elektroappApi";
import DataCard from "../components/common/DataCard";

const display = (input: any) => input === null || input === undefined || input === "" ? "-" : String(input);
const Fields = ({ items }: { items: Array<[string, any]> }) => <dl className="dip-fields">{items.map(([label, item]) => <React.Fragment key={label}><dt>{label}</dt><dd>{display(item)}</dd></React.Fragment>)}</dl>;

const DipPage = () => {
  const [status, setStatus] = useState<any>(null); const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true); const [error, setError] = useState<string | null>(null);
  const load = async () => { setLoading(true); setError(null); try { const [s, p] = await Promise.all([elektroappApi.getDipStatus(), elektroappApi.getDipProfile()]); setStatus(s); setProfile(p); } catch (e: any) { setError(e?.response?.data?.detail?.message || e?.response?.data?.detail || "DIP data se nepodařilo načíst."); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);
  const sync = async () => { setLoading(true); setError(null); try { await elektroappApi.syncDip(); await load(); } catch (e: any) { setError(e?.response?.data?.detail?.message || e?.response?.data?.detail || "Synchronizace DIP selhala."); setLoading(false); } };
  const points = profile?.supply_points || [];
  return <div className="dip-page">
    <DataCard title="Distribuční portál" loading={loading} error={error}><div className="dip-status"><div><strong>{status?.healthy ? "Připojeno" : status?.configured ? "Nakonfigurováno" : "Vypnuto"}</strong><span>Poslední synchronizace: {display(status?.last_sync_at)}</span></div><button type="button" onClick={sync} disabled={loading || !status?.configured}>Synchronizovat</button></div></DataCard>
    {points.map((point: any) => { const tech = point.technical || {}; const contract = point.contract || {}; const contact = point.contact || {};
      return <DataCard key={point.ean} title={`${point.kind || "Odběrné místo"} · ${point.ean || "-"}`}>
        <div className="dip-section-grid">
          <section><h3>Odběrné místo</h3><Fields items={[["Číslo OM", point.supply_point_number], ["EAN", point.ean], ["Adresa", point.supply_address], ["Poznámka", point.note], ["Zákazník", point.customer_name], ["Trvalá adresa", point.permanent_address], ["Zasílací adresa", point.mailing_address]]} /></section>
          <section><h3>Kontakt</h3><Fields items={[["Jméno", [contact.first_name, contact.last_name].filter(Boolean).join(" ")], ["E-mail", contact.email], ["Telefon", contact.telephone]]} /></section>
          <section><h3>Technické údaje</h3><Fields items={[["Napěťová hladina", tech.voltage_level], ["Typ měření", tech.metering_type], ["Elektroměr", tech.meter_id], ["Poslední odečet", tech.last_reading_date], ["VT", tech.last_vt_kwh], ["NT", tech.last_nt_kwh], ["Fáze", tech.phases], ["Jistič", tech.breaker_amps ? `${tech.breaker_amps} A` : null], ["Fakturovaný jistič", tech.billed_breaker_amps ? `${tech.billed_breaker_amps} A` : null], ["Sazba", tech.distribution_tariff], ["Instalovaný výkon", tech.installed_power_kw ? `${tech.installed_power_kw} kW` : null], ["Rezervovaný výkon", tech.reserved_power_kw ? `${tech.reserved_power_kw} kW` : null], ["Maximum dodávky", tech.max_delivered_power_kw ? `${tech.max_delivered_power_kw} kW` : null], ["Akumulace", tech.accumulation === true ? "Ano" : tech.accumulation === false ? "Ne" : null]]} /></section>
          <section><h3>Smlouva a platby</h3><Fields items={[["Stav distribuce", contract.distribution_status], ["Typ smlouvy", contract.type], ["Dodavatel", contract.supplier], ["Elektronická faktura", contract.electronic_invoice === true ? "Ano" : contract.electronic_invoice === false ? "Ne" : null], ["Způsoby plateb", (contract.payment_methods || []).map((x: any) => x.method).filter(Boolean).join(", ")]]} /></section>
        </div>
        <section className="dip-table-section"><h3>Historie odečtů</h3><div className="dip-table-wrap"><table><thead><tr><th>Datum</th><th>Elektroměr</th><th>VT</th><th>NT</th><th>Důvod</th><th>Způsob</th></tr></thead><tbody>{(point.readings || []).map((row: any, index: number) => <tr key={`${row.datumOdectu}-${index}`}><td>{row.datumOdectu}</td><td>{row.sernr}</td><td>{row.stavVt} {row.vtUnitRead}</td><td>{row.stavNt} {row.ntUnitRead}</td><td>{row.duvodOdectuText}</td><td>{row.istablartText}</td></tr>)}</tbody></table></div></section>
        <section className="dip-table-section"><h3>Časy spínání</h3>{(point.tariff_switching || []).map((row: any, index: number) => <div className="dip-signal" key={index}><strong>{row.den || row.datum || row.signal}</strong><span>{row.casy}</span></div>)}{!point.tariff_switching?.length && <span className="config-muted">Nejsou dostupné.</span>}</section>
        <section className="dip-table-section"><h3>Plánované odstávky</h3>{point.planned_outages?.length ? point.planned_outages.map((item: any, index: number) => <pre key={index}>{JSON.stringify(item, null, 2)}</pre>) : <span className="config-muted">Nejsou evidovány žádné odstávky.</span>}</section>
      </DataCard>; })}
    {!loading && !points.length && <DataCard title="Odběrná místa"><span className="config-muted">DIP zatím nemá synchronizovaný profil.</span></DataCard>}
  </div>;
};
export default DipPage;
