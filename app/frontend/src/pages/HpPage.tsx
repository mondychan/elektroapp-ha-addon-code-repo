import React, { useCallback, useEffect, useMemo, useState } from "react";
import DataCard from "../components/common/DataCard";
import DateNavigator from "../components/DateNavigator";
import LineTimeChart from "../charting/components/LineTimeChart";
import { elektroappApi, formatApiError } from "../api/elektroappApi";
import {
  Config,
  HpChart,
  HpDataResponse,
  HpEntityConfig,
  HpKpiItem,
  HpResolvedEntity,
} from "../types/elektroapp";

interface HpPageProps {
  config: Config | null;
  refreshConfig: () => Promise<any>;
  onKpisChange: (items: Array<{ key: string; label: string; value: string; detail?: string | null; tone?: string }>) => void;
  maxDate: string;
}

const buildFormState = (config: Config | null) => ({
  enabled: Boolean(config?.hp?.enabled),
  entities: (config?.hp?.entities || []).map((entity) => ({
    entity_id: entity.entity_id || "",
    label: entity.label || "",
    display_kind: entity.display_kind || "numeric",
    source_kind: entity.source_kind || "instant",
    kpi_enabled: entity.kpi_enabled ?? true,
    chart_enabled: entity.chart_enabled ?? false,
    kpi_mode: entity.kpi_mode || "last",
    unit: entity.unit || "",
    measurement: entity.measurement || "",
    decimals: entity.decimals ?? "",
    device_class: entity.device_class || "",
    state_class: entity.state_class || "",
  })),
});

const emptyEntityRow = (): any => ({
  entity_id: "",
  label: "",
  display_kind: "numeric",
  source_kind: "instant",
  kpi_enabled: true,
  chart_enabled: true,
  kpi_mode: "last",
  unit: "",
  measurement: "",
  decimals: "",
  device_class: "",
  state_class: "",
});

const formatTime = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

const formatNumber = (value: number | null | undefined, decimals?: number | null, unit?: string | null) => {
  if (value == null || Number.isNaN(value)) return "-";
  const precision = decimals != null ? decimals : Math.abs(value) >= 100 ? 0 : 2;
  const formatted = value.toFixed(precision);
  return unit ? `${formatted} ${unit}` : formatted;
};

const toScreenKpis = (kpis: HpKpiItem[]) =>
  kpis.map((item) => ({
    key: item.entity_id,
    label: item.label,
    value: formatNumber(item.value, item.decimals, item.unit),
    detail: [item.kpi_mode ? `KPI: ${item.kpi_mode}` : null, formatTime(item.updated_at)].filter(Boolean).join(" | "),
    tone: "neutral",
  }));

const buildChartData = (chart: HpChart) => ({
  labels: chart.points.map((point) => {
    const value = new Date(point.time);
    return Number.isNaN(value.getTime()) ? point.time : value.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
  }),
  datasets: [
    {
      label: chart.label,
      data: chart.points.map((point) => point.value),
      borderColor: "#4d79ff",
      backgroundColor: "rgba(77, 121, 255, 0.16)",
      tension: 0.24,
      borderWidth: 2,
      fill: true,
      pointRadius: 0,
      pointHitRadius: 10,
    },
  ],
});

const buildChartOptions = (chart: HpChart) => ({
  plugins: {
    legend: { display: false },
  },
  scales: {
    x: {
      ticks: {
        maxRotation: 0,
        autoSkip: true,
        maxTicksLimit: 12,
      },
      grid: {
        display: false,
      },
    },
    y: {
      title: chart.unit
        ? {
            display: true,
            text: chart.unit,
          }
        : undefined,
    },
  },
});

const HpPage: React.FC<HpPageProps> = ({ config, refreshConfig, onKpisChange, maxDate }) => {
  const today = useMemo(() => new Date().toISOString().slice(0, 10), []);
  const [selectedDate, setSelectedDate] = useState(today);
  const [form, setForm] = useState(() => buildFormState(config));
  const [data, setData] = useState<HpDataResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [resolveLoading, setResolveLoading] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);

  useEffect(() => {
    setForm(buildFormState(config));
  }, [config]);

  const loadData = useCallback(
    async (dateValue: string) => {
      setLoading(true);
      setError(null);
      try {
        const payload = await elektroappApi.getHpData(dateValue);
        setData(payload);
        onKpisChange(toScreenKpis(payload?.kpis || []));
      } catch (err) {
        setError(formatApiError(err, "Nepodarilo se nacist HP data."));
        onKpisChange([]);
      } finally {
        setLoading(false);
      }
    },
    [onKpisChange]
  );

  useEffect(() => {
    loadData(selectedDate);
  }, [loadData, selectedDate]);

  useEffect(() => () => onKpisChange([]), [onKpisChange]);

  const mergedConfig = useMemo(() => {
    const base = config || ({} as Config);
    const entities: HpEntityConfig[] = form.entities
      .filter((entity: any) => entity.entity_id?.trim())
      .map((entity: any) => ({
        entity_id: entity.entity_id.trim(),
        label: entity.label?.trim() || undefined,
        display_kind: entity.display_kind,
        source_kind: entity.display_kind === "state" ? "state" : entity.source_kind,
        kpi_enabled: Boolean(entity.kpi_enabled),
        chart_enabled: entity.display_kind === "numeric" ? Boolean(entity.chart_enabled) : false,
        kpi_mode: entity.display_kind === "state" ? "last" : entity.kpi_mode,
        unit: entity.unit?.trim() || undefined,
        measurement: entity.measurement?.trim() || undefined,
        decimals: entity.decimals === "" ? undefined : Number(entity.decimals),
        device_class: entity.device_class?.trim() || undefined,
        state_class: entity.state_class?.trim() || undefined,
      }));
    return {
      ...base,
      hp: {
        enabled: form.enabled,
        entities,
      },
    };
  }, [config, form]);

  const handleEntityField = (index: number, key: string, value: any) => {
    setForm((prev: any) => {
      const entities = [...prev.entities];
      const next = { ...entities[index], [key]: value };
      if (key === "display_kind" && value === "state") {
        next.source_kind = "state";
        next.chart_enabled = false;
        next.kpi_mode = "last";
      }
      if (key === "source_kind" && value === "state") {
        next.display_kind = "state";
        next.chart_enabled = false;
        next.kpi_mode = "last";
      }
      if (key === "source_kind" && value === "counter" && !["delta", "sum", "last"].includes(next.kpi_mode)) {
        next.kpi_mode = "delta";
      }
      if (key === "source_kind" && value === "instant" && !["last", "min", "max", "avg"].includes(next.kpi_mode)) {
        next.kpi_mode = "last";
      }
      entities[index] = next;
      return { ...prev, entities };
    });
  };

  const handleResolveEntity = async (index: number) => {
    const target = form.entities[index];
    const entityId = target?.entity_id?.trim();
    if (!entityId) return;
    setResolveLoading(entityId);
    setResolveError(null);
    try {
      const resolved = (await elektroappApi.resolveHpEntity(entityId)) as HpResolvedEntity;
      setForm((prev: any) => {
        const entities = [...prev.entities];
        const next = { ...entities[index] };
        next.label = resolved.label || next.label;
        next.unit = resolved.unit || "";
        next.display_kind = resolved.display_kind || next.display_kind;
        next.source_kind = resolved.source_kind || next.source_kind;
        next.kpi_mode = resolved.kpi_mode || next.kpi_mode;
        next.device_class = resolved.device_class || "";
        next.state_class = resolved.state_class || "";
        if (resolved.display_kind === "state") {
          next.chart_enabled = false;
        }
        entities[index] = next;
        return { ...prev, entities };
      });
    } catch (err) {
      setResolveError(formatApiError(err, "Auto-fill HP entity selhal."));
    } finally {
      setResolveLoading(null);
    }
  };

  const handleSave = async () => {
    setSaveLoading(true);
    setSaveMessage(null);
    setSaveError(null);
    try {
      const response = await elektroappApi.saveConfig(mergedConfig);
      await refreshConfig();
      await loadData(selectedDate);
      setSaveMessage(response?.message || "HP konfigurace ulozena.");
    } catch (err) {
      setSaveError(formatApiError(err, "Ulozeni HP konfigurace selhalo."));
    } finally {
      setSaveLoading(false);
    }
  };

  return (
    <section className="page-hp">
      <DataCard title="HP statusy" loading={loading} error={error}>
        <div className="toolbar toolbar-compact">
          <DateNavigator value={selectedDate} onChange={setSelectedDate} maxDate={maxDate} />
        </div>
        {data?.status_cards?.length ? (
          <div className="hp-status-grid">
            {data.status_cards.map((card) => (
              <div key={card.entity_id} className="hp-status-card">
                <div className="hp-status-label">{card.label}</div>
                <div className="hp-status-value">{card.value}</div>
                <div className="hp-status-detail">{[card.unit, formatTime(card.updated_at)].filter(Boolean).join(" | ") || "\u00A0"}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="config-muted">Zadne stavove HP entity nejsou nakonfigurovane.</div>
        )}
      </DataCard>

      <div className="hp-charts-grid">
        {data?.charts?.length ? (
          data.charts.map((chart) => (
            <DataCard key={chart.entity_id} title={chart.label} empty={!chart.points?.length} emptyMessage="Pro vybrany den nejsou k dispozici zadna data.">
              {chart.points?.length ? <LineTimeChart data={buildChartData(chart)} options={buildChartOptions(chart)} height={260} /> : null}
            </DataCard>
          ))
        ) : (
          <DataCard title="HP grafy">
            <div className="config-muted">Zadne grafy nejsou zapnute. U numerickych entit aktivuj volbu graf.</div>
          </DataCard>
        )}
      </div>

      <DataCard title="HP konfigurace" className="card-spaced">
        <div className="pnd-toggle-grid">
          <label>
            <input
              type="checkbox"
              checked={form.enabled}
              onChange={(event) => setForm((prev: any) => ({ ...prev, enabled: event.target.checked }))}
            />
            HP zapnuto
          </label>
        </div>
        <div className="hp-entity-list">
          {form.entities.map((entity: any, index: number) => (
            <div key={`${entity.entity_id || "new"}-${index}`} className="hp-entity-card">
              <div className="hp-entity-grid">
                <label className="pnd-field">
                  <span>Entity ID</span>
                  <input value={entity.entity_id} onChange={(event) => handleEntityField(index, "entity_id", event.target.value)} placeholder="sensor.ebusd_ha_daemon_hmu_currentyieldpower" />
                </label>
                <label className="pnd-field">
                  <span>Label</span>
                  <input value={entity.label} onChange={(event) => handleEntityField(index, "label", event.target.value)} placeholder="Current yield power" />
                </label>
                <label className="pnd-field">
                  <span>Zobrazeni</span>
                  <select value={entity.display_kind} onChange={(event) => handleEntityField(index, "display_kind", event.target.value)}>
                    <option value="numeric">numeric</option>
                    <option value="state">state</option>
                  </select>
                </label>
                <label className="pnd-field">
                  <span>Source kind</span>
                  <select value={entity.source_kind} onChange={(event) => handleEntityField(index, "source_kind", event.target.value)}>
                    <option value="instant">instant</option>
                    <option value="counter">counter</option>
                    <option value="state">state</option>
                  </select>
                </label>
                <label className="pnd-field">
                  <span>KPI mode</span>
                  <select value={entity.kpi_mode} onChange={(event) => handleEntityField(index, "kpi_mode", event.target.value)} disabled={entity.display_kind === "state"}>
                    {entity.source_kind === "counter" ? (
                      <>
                        <option value="last">last</option>
                        <option value="delta">delta</option>
                        <option value="sum">sum</option>
                      </>
                    ) : entity.display_kind === "state" ? (
                      <option value="last">last</option>
                    ) : (
                      <>
                        <option value="last">last</option>
                        <option value="min">min</option>
                        <option value="max">max</option>
                        <option value="avg">avg</option>
                      </>
                    )}
                  </select>
                </label>
                <label className="pnd-field">
                  <span>Unit</span>
                  <input value={entity.unit} onChange={(event) => handleEntityField(index, "unit", event.target.value)} placeholder="kW" />
                </label>
                <label className="pnd-field">
                  <span>Measurement override</span>
                  <input value={entity.measurement} onChange={(event) => handleEntityField(index, "measurement", event.target.value)} placeholder="W" />
                </label>
                <label className="pnd-field">
                  <span>Decimals</span>
                  <input type="number" min={0} max={6} value={entity.decimals} onChange={(event) => handleEntityField(index, "decimals", event.target.value)} placeholder="2" />
                </label>
              </div>
              <div className="pnd-toggle-grid">
                <label><input type="checkbox" checked={entity.kpi_enabled} onChange={(event) => handleEntityField(index, "kpi_enabled", event.target.checked)} /> KPI</label>
                <label><input type="checkbox" checked={entity.chart_enabled} disabled={entity.display_kind === "state"} onChange={(event) => handleEntityField(index, "chart_enabled", event.target.checked)} /> Graf</label>
              </div>
              <div className="hp-entity-meta">
                <span>device_class: {entity.device_class || "-"}</span>
                <span>state_class: {entity.state_class || "-"}</span>
              </div>
              <div className="fees-history-actions">
                <button onClick={() => handleResolveEntity(index)} disabled={!entity.entity_id?.trim() || resolveLoading === entity.entity_id}>
                  {resolveLoading === entity.entity_id ? "Nacitam metadata..." : "Auto-fill z HA"}
                </button>
                <button className="danger-button" onClick={() => setForm((prev: any) => ({ ...prev, entities: prev.entities.filter((_: any, currentIndex: number) => currentIndex !== index) }))}>
                  Odebrat
                </button>
              </div>
            </div>
          ))}
        </div>
        <div className="fees-history-actions">
          <button onClick={() => setForm((prev: any) => ({ ...prev, entities: [...prev.entities, emptyEntityRow()] }))}>Pridat entitu</button>
          <button onClick={handleSave} disabled={saveLoading || !config}>{saveLoading ? "Ukladam..." : "Ulozit HP konfiguraci"}</button>
        </div>
        {resolveError ? <div className="alert error">{resolveError}</div> : null}
        {saveMessage ? <div className="config-muted">{saveMessage}</div> : null}
        {saveError ? <div className="alert error">{saveError}</div> : null}
      </DataCard>
    </section>
  );
};

export default HpPage;
