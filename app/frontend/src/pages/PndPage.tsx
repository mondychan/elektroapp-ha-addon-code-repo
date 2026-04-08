import React, { useCallback, useEffect, useMemo, useState } from "react";
import DataCard from "../components/common/DataCard";
import { elektroappApi, formatApiError } from "../api/elektroappApi";
import { Config, PndStatus } from "../types/elektroapp";

interface PndPageProps {
  config: Config | null;
  refreshConfig: () => Promise<any>;
}

interface PndFormState {
  enabled: boolean;
  username: string;
  password: string;
  meter_id: string;
  verify_on_startup: boolean;
  nightly_sync_enabled: boolean;
  nightly_sync_window_start_hour: number;
  nightly_sync_window_end_hour: number;
}

const getYesterday = () => {
  const now = new Date();
  now.setDate(now.getDate() - 1);
  return now.toISOString().slice(0, 10);
};

const buildFormState = (config: Config | null): PndFormState => ({
  enabled: Boolean(config?.pnd?.enabled),
  username: config?.pnd?.username || "",
  password: config?.pnd?.password || "",
  meter_id: config?.pnd?.meter_id || "",
  verify_on_startup: config?.pnd?.verify_on_startup ?? true,
  nightly_sync_enabled: config?.pnd?.nightly_sync_enabled ?? true,
  nightly_sync_window_start_hour: config?.pnd?.nightly_sync_window_start_hour ?? 2,
  nightly_sync_window_end_hour: config?.pnd?.nightly_sync_window_end_hour ?? 7,
});

const formatDate = (dateStr?: string | null) => {
  if (!dateStr) return "-";
  const parts = dateStr.split("-");
  if (parts.length === 3) {
    return `${parts[2]}.${parts[1]}.${parts[0]}`;
  }
  return dateStr;
};

const formatDateTime = (value?: string | null) => {
  if (!value) return "-";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("cs-CZ");
};

const getStatePresentation = (status: PndStatus | null) => {
  switch (status?.state) {
    case "not_configured":
      return {
        tone: "warning",
        title: "PND neni nakonfigurovano",
        description: status.state_message || "Dopln uzivatelske jmeno, heslo a meter_id.",
      };
    case "login_failed":
      return {
        tone: "error",
        title: "Prihlaseni do PND selhalo",
        description: status.state_message || "Zkontroluj prihlasovaci udaje do portalu PND.",
      };
    case "portal_changed":
      return {
        tone: "error",
        title: "PND zmenilo strukturu nebo endpoint contract",
        description: status.state_message || "Verify nedokaze potvrdit ocekavane HTML markery nebo datovy payload.",
      };
    case "yesterday_not_available":
      return {
        tone: "warning",
        title: "Vcerejsi data jeste nejsou publikovana",
        description: status.state_message || "Nocni sync bude zkouset PND znovu mezi 02:00 a 07:00.",
      };
    case "cache_ready":
      return {
        tone: "success",
        title: "PND cache je pripravena",
        description: status.state_message || "Prvni data jsou dostupna v lokalni cache.",
      };
    case "verified":
      return {
        tone: "info",
        title: "Verify probehlo uspesne",
        description: status.state_message || "Pripojeni a request contract jsou overene, cache je zatim prazdna.",
      };
    case "disabled":
      return {
        tone: "info",
        title: "PND integrace je vypnuta",
        description: status.state_message || "Zapni PND v konfiguraci, pokud ji chces pouzivat.",
      };
    default:
      return status
        ? {
            tone: "info",
            title: "Stav PND integrace",
            description: status.state_message || "PND integrace ceka na dalsi akci.",
          }
        : null;
  }
};

const formatDiagnosticRows = (status: PndStatus | null) => {
  const details = status?.last_error?.details;
  if (!details || typeof details !== "object") return [];

  const rows: string[] = [];
  if (details.url) rows.push(`Endpoint: ${details.url}`);
  if (details.missing_html_marker) rows.push(`Chybi HTML marker: ${details.missing_html_marker}`);
  if (details.status_code) rows.push(`HTTP status: ${details.status_code}`);
  if (details.meter_id) rows.push(`Meter ID: ${details.meter_id}`);
  if (details.range?.from && details.range?.to) rows.push(`Rozsah: ${formatDate(details.range.from)} az ${formatDate(details.range.to)}`);
  if (Array.isArray(details.payload_keys) && details.payload_keys.length) {
    rows.push(`Payload keys: ${details.payload_keys.join(", ")}`);
  }
  if (Array.isArray(details.series_names) && details.series_names.length) {
    rows.push(`Nezname serie: ${details.series_names.join(", ")}`);
  }
  if (Array.isArray(details.recognized_series) && details.recognized_series.length) {
    rows.push(`Rozpoznane serie: ${details.recognized_series.join(", ")}`);
  }
  if (Array.isArray(details.messages) && details.messages.length) {
    rows.push(`Portal message: ${details.messages.join(" | ")}`);
  }
  return rows;
};

const PndPage: React.FC<PndPageProps> = ({ config, refreshConfig }) => {
  const [form, setForm] = useState<PndFormState>(() => buildFormState(config));
  const [status, setStatus] = useState<PndStatus | null>(null);
  const [statusLoading, setStatusLoading] = useState(false);
  const [statusError, setStatusError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState(false);
  const [actionMessage, setActionMessage] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [rangeFrom, setRangeFrom] = useState(getYesterday());
  const [rangeTo, setRangeTo] = useState(getYesterday());
  const [dataLoading, setDataLoading] = useState(false);
  const [dataError, setDataError] = useState<string | null>(null);
  const [dataPreview, setDataPreview] = useState<any[]>([]);

  const statePresentation = useMemo(() => getStatePresentation(status), [status]);
  const diagnosticRows = useMemo(() => formatDiagnosticRows(status), [status]);

  useEffect(() => {
    setForm(buildFormState(config));
  }, [config]);

  const loadStatus = useCallback(async () => {
    setStatusLoading(true);
    setStatusError(null);
    try {
      const payload = await elektroappApi.getPndStatus();
      setStatus(payload);
      if (payload?.cached_from) setRangeFrom(payload.cached_from);
      if (payload?.cached_to) setRangeTo(payload.cached_to);
    } catch (err) {
      setStatusError(formatApiError(err, "Nepodarilo se nacist stav PND."));
    } finally {
      setStatusLoading(false);
    }
  }, []);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const mergedConfig = useMemo(() => {
    const base = config || ({} as Config);
    return {
      ...base,
      pnd: { ...form },
    };
  }, [config, form]);

  const handleField = (key: keyof PndFormState, value: string | boolean | number) => {
    setForm((prev) => {
      if (key === "nightly_sync_window_start_hour") {
        const nextStart = Math.max(0, Math.min(23, Number(value)));
        return {
          ...prev,
          nightly_sync_window_start_hour: nextStart,
          nightly_sync_window_end_hour: Math.max(prev.nightly_sync_window_end_hour, nextStart),
        };
      }
      if (key === "nightly_sync_window_end_hour") {
        const nextEnd = Math.max(prev.nightly_sync_window_start_hour, Math.min(23, Number(value)));
        return { ...prev, nightly_sync_window_end_hour: nextEnd };
      }
      return { ...prev, [key]: value };
    });
  };

  const handleSave = async () => {
    setSaveLoading(true);
    setSaveMessage(null);
    setSaveError(null);
    try {
      const response = await elektroappApi.saveConfig(mergedConfig);
      await refreshConfig();
      await loadStatus();
      if (response?.pnd_verify?.ok === false) {
        const suffix = response?.pnd_verify?.code ? ` [${response.pnd_verify.code}]` : "";
        setSaveError(`${response.pnd_verify.message || "PND verify po ulozeni selhalo."}${suffix}`);
      } else {
        setSaveMessage(response?.pnd_verify?.message || response?.message || "PND konfigurace ulozena.");
      }
    } catch (err) {
      setSaveError(formatApiError(err, "Ulozeni PND konfigurace selhalo."));
    } finally {
      setSaveLoading(false);
    }
  };

  const handleVerify = async () => {
    setActionLoading(true);
    setActionMessage(null);
    setActionError(null);
    try {
      const response = await elektroappApi.verifyPnd();
      await loadStatus();
      setActionMessage(response?.message || "PND verify probehlo uspesne.");
    } catch (err) {
      setActionError(formatApiError(err, "PND verify selhalo."));
    } finally {
      setActionLoading(false);
    }
  };

  const handleBackfill = async (range: string) => {
    setActionLoading(true);
    setActionMessage(null);
    setActionError(null);
    try {
      const response = await elektroappApi.backfillPnd(range);
      await loadStatus();
      setActionMessage(`Backfill '${range}' dokoncen, ulozeno cca ${response?.estimated_days ?? 0} dni.`);
    } catch (err) {
      setActionError(formatApiError(err, "Backfill PND selhal."));
    } finally {
      setActionLoading(false);
    }
  };

  const handleLoadData = async () => {
    setDataLoading(true);
    setDataError(null);
    try {
      const response = await elektroappApi.getPndData(rangeFrom, rangeTo);
      setDataPreview(response?.days || []);
    } catch (err) {
      setDataError(formatApiError(err, "Nepodarilo se nacist PND data."));
    } finally {
      setDataLoading(false);
    }
  };

  const handlePurgeCache = async () => {
    if (!window.confirm("Opravdu chcete smazat celou lokalni cache PND? Data budou muset byt stazena znovu.")) {
      return;
    }
    setActionLoading(true);
    setActionMessage(null);
    setActionError(null);
    try {
      const response = await elektroappApi.purgePndCache();
      await loadStatus();
      setActionMessage(`PND cache promazana (smazano ${response?.purged_files ?? 0} souboru).`);
      setDataPreview([]);
    } catch (err) {
      setActionError(formatApiError(err, "Nepodarilo se promazat PND cache."));
    } finally {
      setActionLoading(false);
    }
  };

  const [showStatus, setShowStatus] = useState(false);
  const [showFeed, setShowFeed] = useState(false);
  const [showConfig, setShowConfig] = useState(false);

  return (
    <section className="page-pnd">
      <DataCard title="Cache a data" className="card-spaced">
        <div className="pnd-status-grid">
          <div><strong>Cached from:</strong> {formatDate(status?.cached_from)}</div>
          <div><strong>Cached to:</strong> {formatDate(status?.cached_to)}</div>
          <div><strong>Pocet dni:</strong> {status?.days_count ?? 0}</div>
        </div>
        <div className="pnd-range-grid">
          <label className="pnd-field">
            <span>Od</span>
            <input type="date" value={rangeFrom} onChange={(e) => setRangeFrom(e.target.value)} />
          </label>
          <label className="pnd-field">
            <span>Do</span>
            <input type="date" value={rangeTo} onChange={(e) => setRangeTo(e.target.value)} />
          </label>
          <div className="config-actions">
            <button onClick={handleLoadData} disabled={dataLoading}>{dataLoading ? "Nacitam..." : "Nacist data"}</button>
            <button
              className="danger-button"
              onClick={handlePurgeCache}
              disabled={actionLoading}
              title="Smaze vsechny lokalni soubory v pnd-cache vcetne raw zaloh."
            >
              Smazat cache
            </button>
          </div>
        </div>
        {dataError ? <div className="alert error">{dataError}</div> : null}
        {dataPreview.length ? (
          <>
            <table className="data-table table-spaced" style={{ marginTop: "16px", borderCollapse: "collapse" }}>
              <thead>
                <tr style={{ borderBottom: "1px solid var(--border-soft)" }}>
                  <th rowSpan={2} style={{ verticalAlign: "middle" }}>Den</th>
                  <th colSpan={3} style={{ textAlign: "center", textTransform: "uppercase", fontSize: "0.75rem", letterSpacing: "0.05em", color: "var(--text-muted)", borderBottom: "1px solid var(--border-soft)" }}>
                    Nákup (kWh)
                  </th>
                  <th colSpan={3} style={{ textAlign: "center", textTransform: "uppercase", fontSize: "0.75rem", letterSpacing: "0.05em", color: "var(--text-muted)", borderBottom: "1px solid var(--border-soft)", borderLeft: "1px solid var(--border-soft)" }}>
                    Prodej (kWh)
                  </th>
                </tr>
                <tr>
                  <th style={{ textAlign: "right" }}>Solax</th>
                  <th style={{ textAlign: "right" }}>PND</th>
                  <th style={{ textAlign: "right" }}>Delta</th>
                  <th style={{ textAlign: "right", borderLeft: "1px solid var(--border-soft)" }}>Solax</th>
                  <th style={{ textAlign: "right" }}>PND</th>
                  <th style={{ textAlign: "right" }}>Delta</th>
                </tr>
              </thead>
              <tbody>
                {dataPreview.map((day) => {
                  const pndBuy = day.totals?.consumption_kwh ?? 0;
                  const localBuy = day.local_comparison?.consumption_kwh ?? 0;
                  const diffBuy = localBuy - pndBuy;

                  const pndSell = day.totals?.production_kwh ?? 0;
                  const localSell = day.local_comparison?.production_kwh ?? 0;
                  const diffSell = localSell - pndSell;

                  return (
                    <tr key={day.date} style={{ borderBottom: "1px solid var(--border-light)" }}>
                      <td style={{ color: "var(--text-muted)", fontSize: "0.9rem" }}>{formatDate(day.date)}</td>
                      <td style={{ textAlign: "right" }}>{localBuy.toFixed(2)}</td>
                      <td style={{ textAlign: "right" }}>{pndBuy.toFixed(2)}</td>
                      <td style={{ textAlign: "right", fontWeight: "500", color: Math.abs(diffBuy) > 0.05 ? "var(--error)" : "inherit" }}>
                        {diffBuy > 0 ? "+" : ""}{diffBuy.toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", borderLeft: "1px solid var(--border-soft)" }}>{localSell.toFixed(2)}</td>
                      <td style={{ textAlign: "right" }}>{pndSell.toFixed(2)}</td>
                      <td style={{ textAlign: "right", fontWeight: "500", color: Math.abs(diffSell) > 0.05 ? "var(--error)" : "inherit" }}>
                        {diffSell > 0 ? "+" : ""}{diffSell.toFixed(2)}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
              <tfoot style={{ fontWeight: "bold", borderTop: "2px solid var(--border-soft)", backgroundColor: "var(--bg-alt)" }}>
                {(() => {
                  const totals = dataPreview.reduce(
                    (acc, day) => {
                      acc.pndBuy += day.totals?.consumption_kwh ?? 0;
                      acc.localBuy += day.local_comparison?.consumption_kwh ?? 0;
                      acc.pndSell += day.totals?.production_kwh ?? 0;
                      acc.localSell += day.local_comparison?.production_kwh ?? 0;
                      return acc;
                    },
                    { pndBuy: 0, localBuy: 0, pndSell: 0, localSell: 0 }
                  );
                  const grandDiffBuy = totals.localBuy - totals.pndBuy;
                  const grandDiffSell = totals.localSell - totals.pndSell;

                  return (
                    <tr>
                      <td style={{ textTransform: "uppercase", fontSize: "0.8rem", color: "var(--text-muted)" }}>CELKEM</td>
                      <td style={{ textAlign: "right" }}>{totals.localBuy.toFixed(2)}</td>
                      <td style={{ textAlign: "right" }}>{totals.pndBuy.toFixed(2)}</td>
                      <td style={{ textAlign: "right", color: Math.abs(grandDiffBuy) > 1.0 ? "var(--error)" : "inherit" }}>
                        {grandDiffBuy > 0 ? "+" : ""}{grandDiffBuy.toFixed(2)}
                      </td>
                      <td style={{ textAlign: "right", borderLeft: "1px solid var(--border-soft)" }}>{totals.localSell.toFixed(2)}</td>
                      <td style={{ textAlign: "right" }}>{totals.pndSell.toFixed(2)}</td>
                      <td style={{ textAlign: "right", color: Math.abs(grandDiffSell) > 1.0 ? "var(--error)" : "inherit" }}>
                        {grandDiffSell > 0 ? "+" : ""}{grandDiffSell.toFixed(2)}
                      </td>
                    </tr>
                  );
                })()}
              </tfoot>
            </table>
            <div className="config-muted" style={{ marginTop: "8px" }}>
              * 'Solax' hodnoty jsou agregovány z lokálních entit Grid Import/Export v InfluxDB.
            </div>
          </>
        ) : (
          <div className="config-muted">Souhrn období a porovnání s lokálními daty se zobrazí po načtení.</div>
        )}
      </DataCard>

      <div className="toolbar" style={{ marginTop: "12px" }}>
        <button className="ghost-button" onClick={() => setShowStatus(!showStatus)}>{showStatus ? "Skrýt stav" : "Stav"}</button>
        <button className="ghost-button" onClick={() => setShowFeed(!showFeed)}>{showFeed ? "Skrýt Feed" : "Feed"}</button>
        <button className="ghost-button" onClick={() => setShowConfig(!showConfig)}>{showConfig ? "Skrýt konfiguraci" : "Konfigurace"}</button>
      </div>

      {showStatus && (
        <DataCard title="Stav a verify" loading={statusLoading} error={statusError} className="card-spaced">
          {statePresentation ? (
            <div className={`alert pnd-state-banner pnd-state-banner--${statePresentation.tone}`}>
              <strong>{statePresentation.title}</strong>
              <div>{statePresentation.description}</div>
            </div>
          ) : null}
          <div className="pnd-status-grid">
            <div><strong>Enabled:</strong> {status?.enabled ? "ano" : "ne"}</div>
            <div><strong>Configured:</strong> {status?.configured ? "ano" : "ne"}</div>
            <div><strong>Healthy:</strong> {status?.healthy ? "ano" : "ne"}</div>
            <div><strong>State:</strong> {status?.state || "-"}</div>
            <div><strong>Portal version:</strong> {status?.portal_version || "-"}</div>
            <div><strong>Posledni verify:</strong> {formatDateTime(status?.last_verify_at)}</div>
            <div><strong>Posledni sync:</strong> {formatDateTime(status?.last_sync_at)}</div>
          </div>
          {status?.last_error ? (
            <div className="alert error">
              <strong>{status.last_error.message}</strong>
              {status.last_error.code ? ` [${status.last_error.code}]` : ""}
              {diagnosticRows.length ? (
                <ul className="pnd-diagnostics-list">
                  {diagnosticRows.map((row) => (
                    <li key={row}>{row}</li>
                  ))}
                </ul>
              ) : null}
            </div>
          ) : (
            <div className="config-muted" style={{ marginTop: "8px" }}>Nebyla zaznamenána žádná chyba.</div>
          )}
          <div className="config-actions">
            <button onClick={handleVerify} disabled={actionLoading}>{actionLoading ? "Overuji..." : "Spustit verify"}</button>
          </div>
          {actionMessage ? <div className="config-muted">{actionMessage}</div> : null}
          {actionError ? <div className="alert error">{actionError}</div> : null}
        </DataCard>
      )}

      {showFeed && (
        <DataCard title="Feed a backfill" className="card-spaced">
          <div className="toolbar">
            <button onClick={() => handleBackfill("yesterday")} disabled={actionLoading}>Vcera</button>
            <button onClick={() => handleBackfill("week")} disabled={actionLoading}>7 dni</button>
            <button onClick={() => handleBackfill("month")} disabled={actionLoading}>Mesic</button>
            <button onClick={() => handleBackfill("year")} disabled={actionLoading}>Rok</button>
            <button onClick={() => handleBackfill("max")} disabled={actionLoading}>Maximum</button>
          </div>
          <div className="config-muted" style={{ marginTop: "8px" }}>
            Nocni sync zkousi stahnout vcerejsi data mezi {String(form.nightly_sync_window_start_hour).padStart(2, "0")}:00 a {String(form.nightly_sync_window_end_hour).padStart(2, "0")}:59, kazdou hodinu.
          </div>
          {actionMessage ? <div className="config-muted">{actionMessage}</div> : null}
          {actionError ? <div className="alert error">{actionError}</div> : null}
        </DataCard>
      )}

      {showConfig && (
        <DataCard title="PND konfigurace" className="card-spaced">
          <div className="pnd-form-grid">
            <label className="pnd-field">
              <span>Uzivatelske jmeno</span>
              <input value={form.username} onChange={(e) => handleField("username", e.target.value)} placeholder="email@domena.cz" />
            </label>
            <label className="pnd-field">
              <span>Heslo</span>
              <input type="password" value={form.password} onChange={(e) => handleField("password", e.target.value)} placeholder="heslo do PND" />
            </label>
            <label className="pnd-field">
              <span>Meter ID / ELM</span>
              <input value={form.meter_id} onChange={(e) => handleField("meter_id", e.target.value)} placeholder="3000012345" />
            </label>
          </div>
          <div className="pnd-toggle-grid">
            <label><input type="checkbox" checked={form.enabled} onChange={(e) => handleField("enabled", e.target.checked)} /> PND zapnuto</label>
            <label><input type="checkbox" checked={form.verify_on_startup} onChange={(e) => handleField("verify_on_startup", e.target.checked)} /> Verify pri startu</label>
            <label><input type="checkbox" checked={form.nightly_sync_enabled} onChange={(e) => handleField("nightly_sync_enabled", e.target.checked)} /> Nocni sync aktivni</label>
          </div>
          <div className="pnd-form-grid">
            <label className="pnd-field">
              <span>Start nocniho okna (hodina)</span>
              <input
                type="number"
                min={0}
                max={23}
                value={form.nightly_sync_window_start_hour}
                onChange={(e) => handleField("nightly_sync_window_start_hour", Number(e.target.value || 0))}
              />
            </label>
            <label className="pnd-field">
              <span>Konec nocniho okna (hodina)</span>
              <input
                type="number"
                min={form.nightly_sync_window_start_hour}
                max={23}
                value={form.nightly_sync_window_end_hour}
                onChange={(e) => handleField("nightly_sync_window_end_hour", Number(e.target.value || 0))}
              />
            </label>
          </div>
          <div className="config-actions">
            <button onClick={handleSave} disabled={saveLoading || !config}>{saveLoading ? "Ukladam..." : "Ulozit PND konfiguraci"}</button>
          </div>
          {saveMessage ? <div className="config-muted">{saveMessage}</div> : null}
          {saveError ? <div className="alert error">{saveError}</div> : null}
        </DataCard>
      )}
    </section>
  );
};

export default PndPage;
