import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DataCard from "../components/common/DataCard";
import DateNavigator from "../components/DateNavigator";
import MonthNavigator from "../components/MonthNavigator";
import YearNavigator from "../components/YearNavigator";
import LineTimeChart from "../charting/components/LineTimeChart";
import { buildTooltip } from "../charting/builders/common";
import { elektroappApi, formatApiError } from "../api/elektroappApi";
import {
  clampDateValue,
  clampMonthValue,
  clampYearValue,
  shiftEnergyBalanceAnchor,
} from "../hooks/dashboardUtils";
import {
  Config,
  HpChart,
  HpDataResponse,
  HpDurationStyle,
  HpEntityConfig,
  HpKpiItem,
  HpResolvedEntity,
  HpValueFormat,
} from "../types/elektroapp";

interface HpPageProps {
  config: Config | null;
  refreshConfig: () => Promise<any>;
  onKpisChange: (items: Array<{ key: string; label: string; value: string; detail?: string | null; tone?: string; secondaryMetrics?: any[]; onClick?: () => void }>) => void;
  maxDate: string;
}

type HpPeriod = "day" | "week" | "month" | "year";
type HpFormOverride = {
  entity_id: string;
  enabled?: boolean;
  label?: string;
  display_kind?: "numeric" | "state";
  source_kind?: "instant" | "counter" | "state";
  kpi_enabled?: boolean;
  chart_enabled?: boolean;
  kpi_mode?: "last" | "min" | "max" | "avg" | "sum" | "delta";
  unit?: string | null;
  measurement?: string | null;
  device_class?: string | null;
  state_class?: string | null;
  decimals?: number | string | null;
  value_format?: HpValueFormat | "" | null;
  duration_style?: HpDurationStyle | "" | null;
  duration_max_parts?: number | string | null;
};

const buildFormState = (config: Config | null) => ({
  enabled: Boolean(config?.hp?.enabled),
  source_mode: config?.hp?.source_mode || "manual",
  scan: {
    prefix: config?.hp?.scan?.prefix || "",
    regex: config?.hp?.scan?.regex || "",
    allowlist: (config?.hp?.scan?.allowlist || []).join(", "),
    blocklist: (config?.hp?.scan?.blocklist || []).join(", "),
    include_domains: (config?.hp?.scan?.include_domains || ["sensor", "binary_sensor"]).join(", "),
    exclude_unavailable: config?.hp?.scan?.exclude_unavailable ?? true,
  },
  defaults: {
    kpi_enabled: config?.hp?.defaults?.kpi_enabled ?? true,
    chart_enabled_numeric: config?.hp?.defaults?.chart_enabled_numeric ?? true,
    chart_enabled_state: config?.hp?.defaults?.chart_enabled_state ?? false,
    kpi_mode_numeric: config?.hp?.defaults?.kpi_mode_numeric || "last",
    kpi_mode_state: config?.hp?.defaults?.kpi_mode_state || "last",
    decimals: config?.hp?.defaults?.decimals ?? "",
  },
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
    value_format: entity.value_format || "",
    duration_style: entity.duration_style || "short",
    duration_max_parts: entity.duration_max_parts ?? 2,
  })),
  overrides: (config?.hp?.overrides || []).map((o) => ({
    ...o,
    decimals: o.decimals ?? "",
    value_format: o.value_format || "",
    duration_style: o.duration_style || "short",
    duration_max_parts: o.duration_max_parts ?? 2,
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
  value_format: "",
  duration_style: "short",
  duration_max_parts: 2,
});

const formatTime = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

const formatDateTime = (value?: string | null) => {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString("cs-CZ", {
    day: "2-digit",
    month: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
};

const pluralizeCzech = (count: number, forms: [string, string, string]) => {
  const abs = Math.abs(count);
  if (abs === 1) return forms[0];
  if (abs >= 2 && abs <= 4) return forms[1];
  return forms[2];
};

const formatDurationValue = (
  input: number,
  sourceFormat: HpValueFormat,
  style: HpDurationStyle = "short",
  maxParts = 2
) => {
  const factorMap: Record<Exclude<HpValueFormat, "default">, number> = {
    duration_seconds: 1,
    duration_minutes: 60,
    duration_hours: 3600,
  };
  const totalSeconds = Math.round(Math.abs(input) * factorMap[sourceFormat as Exclude<HpValueFormat, "default">]);
  const sign = input < 0 ? "-" : "";
  const safeMaxParts = Math.max(1, Math.min(6, maxParts || 2));
  const units = [
    { size: 365 * 24 * 60 * 60, short: "r", long: ["rok", "roky", "let"] as [string, string, string] },
    { size: 30 * 24 * 60 * 60, short: "mes", long: ["mesic", "mesice", "mesicu"] as [string, string, string] },
    { size: 7 * 24 * 60 * 60, short: "tyd", long: ["tyden", "tydny", "tydnu"] as [string, string, string] },
    { size: 24 * 60 * 60, short: "d", long: ["den", "dny", "dnu"] as [string, string, string] },
    { size: 60 * 60, short: "h", long: ["hodina", "hodiny", "hodin"] as [string, string, string] },
    { size: 60, short: "min", long: ["minuta", "minuty", "minut"] as [string, string, string] },
    { size: 1, short: "s", long: ["sekunda", "sekundy", "sekund"] as [string, string, string] },
  ];

  if (totalSeconds === 0) {
    return style === "long" ? "0 sekund" : "0 s";
  }

  let remainder = totalSeconds;
  const parts: string[] = [];
  for (const unit of units) {
    if (remainder < unit.size) continue;
    const count = Math.floor(remainder / unit.size);
    remainder -= count * unit.size;
    parts.push(
      style === "long"
        ? `${count} ${pluralizeCzech(count, unit.long)}`
        : `${count} ${unit.short}`
    );
    if (parts.length >= safeMaxParts) break;
  }

  return `${sign}${parts.join(" ")}`;
};

const formatAutoUnitValue = (value: number, originalUnit: string, decimals?: number | null) => {
  const absValue = Math.abs(value);
  const unit = (originalUnit || "").toLowerCase();
  const precision = decimals != null ? decimals : 2;

  if (unit === "w" || unit === "va") {
    if (absValue >= 1000) return `${(value / 1000).toFixed(precision)} kW`;
    return `${value.toFixed(decimals ?? 0)} ${originalUnit}`;
  }
  if (unit === "wh") {
    if (absValue >= 1000000) return `${(value / 1000000).toFixed(precision)} MWh`;
    if (absValue >= 1000) return `${(value / 1000).toFixed(precision)} kWh`;
    return `${value.toFixed(decimals ?? 0)} Wh`;
  }
  if (unit === "kwh") {
    if (absValue >= 1000) return `${(value / 1000).toFixed(precision)} MWh`;
    return `${value.toFixed(precision)} kWh`;
  }
  return `${value.toFixed(precision)} ${originalUnit}`;
};

const formatNumber = (
  value: number | null | undefined,
  decimals?: number | null,
  unit?: string | null,
  valueFormat?: HpValueFormat | null,
  durationStyle?: HpDurationStyle | null,
  durationMaxParts?: number | null
) => {
  if (value == null || Number.isNaN(value)) return "-";
  if (valueFormat === "auto_unit" && unit) {
    return formatAutoUnitValue(value, unit, decimals);
  }
  if (valueFormat && valueFormat !== "default" && valueFormat.startsWith("duration")) {
    return formatDurationValue(value, valueFormat, durationStyle || "short", durationMaxParts ?? 2);
  }
  const precision = decimals != null ? decimals : Math.abs(value) >= 100 ? 0 : 2;
  const formatted = value.toFixed(precision);
  return unit ? `${formatted} ${unit}` : formatted;
};

const convertAnchorForPeriod = (value: string, period: HpPeriod, maxDate: string, maxMonth: string, maxYear: string) => {
  if (period === "year") {
    return clampYearValue(String(value || "").slice(0, 4), maxYear);
  }
  if (period === "month") {
    const monthValue = /^\d{4}-\d{2}-\d{2}$/.test(value || "") ? String(value).slice(0, 7) : String(value || "").slice(0, 7);
    return clampMonthValue(monthValue, maxMonth);
  }
  if (/^\d{4}-\d{2}$/.test(value || "")) {
    return clampDateValue(`${value}-01`, maxDate);
  }
  if (/^\d{4}$/.test(value || "")) {
    return clampDateValue(`${value}-01-01`, maxDate);
  }
  return clampDateValue(value, maxDate);
};

const toScreenKpis = (kpis: HpKpiItem[], chartEntityIds: Set<string>, onChartFocus: (entityId: string) => void) =>
  kpis.map((item) => ({
    key: item.entity_id,
    label: item.label,
    value: formatNumber(item.value, item.decimals, item.unit, item.value_format, item.duration_style, item.duration_max_parts),
    secondaryMetrics: (item.secondary_metrics || []).map((metric) => ({
      key: metric.key,
      label: metric.label,
      value: formatNumber(metric.value, item.decimals, item.unit, item.value_format, item.duration_style, item.duration_max_parts),
    })),
    detail: null,
    tone: "neutral",
    onClick: chartEntityIds.has(item.entity_id) ? () => onChartFocus(item.entity_id) : undefined,
  }));

const formatChartLabel = (value: string, period: HpPeriod) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  if (period === "day") {
    return date.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
  }
  if (period === "year") {
    return date.toLocaleDateString("cs-CZ", { month: "short", year: "2-digit" });
  }
  return date.toLocaleDateString("cs-CZ", { day: "2-digit", month: "2-digit" });
};

const buildChartData = (chart: HpChart, period: HpPeriod) => ({
  labels: chart.points.map((point) => {
    return formatChartLabel(point.time, period);
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
      spanGaps: false,
      pointRadius: chart.points.some((point) => point.value == null) ? 2 : 1.25,
      pointHoverRadius: 4,
      pointHitRadius: 14,
    },
  ],
});

const buildChartOptions = (chart: HpChart, period: HpPeriod) => ({
  interaction: {
    mode: "index",
    intersect: false,
  },
  plugins: {
    legend: { display: false },
    tooltip: buildTooltip(({ points }: { points: Array<{ dataIndex: number; raw: number | null }> }) => {
      const point = points?.[0];
      if (!point) {
        return null;
      }
      const value = point.raw;
      const label = chart.points?.[point.dataIndex]?.time
        ? formatChartLabel(chart.points[point.dataIndex].time, period)
        : chart.label;
      return {
        title: label,
        sections: [
          {
            label: chart.label,
            value: formatNumber(value, chart.decimals, chart.unit, chart.value_format, chart.duration_style, chart.duration_max_parts),
            color: "#4d79ff",
          },
        ],
      };
    }),
  },
  scales: {
    x: {
      ticks: {
        maxRotation: 0,
        autoSkip: true,
        maxTicksLimit: period === "day" ? 12 : period === "week" ? 8 : period === "month" ? 12 : 12,
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
  const maxMonth = useMemo(() => maxDate.slice(0, 7), [maxDate]);
  const maxYear = useMemo(() => maxDate.slice(0, 4), [maxDate]);
  const [chartPeriod, setChartPeriod] = useState<HpPeriod>("day");
  const [chartAnchor, setChartAnchor] = useState(maxDate);
  const [form, setForm] = useState(() => buildFormState(config));
  const [data, setData] = useState<HpDataResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveMessage, setSaveMessage] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [resolveLoading, setResolveLoading] = useState<string | null>(null);
  const [resolveError, setResolveError] = useState<string | null>(null);
  const [configExpanded, setConfigExpanded] = useState(false);
  const chartRefs = useRef<Record<string, HTMLDivElement | null>>({});

  useEffect(() => {
    setForm(buildFormState(config));
  }, [config]);

  useEffect(() => {
    setChartAnchor((previous) => previous || maxDate);
  }, [maxDate]);

  const normalizedChartAnchor = useMemo(() => {
    if (chartPeriod === "year") return clampYearValue(chartAnchor, maxYear);
    if (chartPeriod === "month") return clampMonthValue(chartAnchor, maxMonth);
    if (chartPeriod === "week") return clampDateValue(chartAnchor, maxDate);
    return clampDateValue(chartAnchor, maxDate);
  }, [chartAnchor, chartPeriod, maxDate, maxMonth, maxYear]);

  const scrollToChart = useCallback((entityId: string) => {
    const target = chartRefs.current[entityId];
    if (!target) return;
    target.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);

  const loadData = useCallback(
    async (periodValue: HpPeriod, anchorValue: string) => {
      setLoading(true);
      setError(null);
      try {
        const payload = await elektroappApi.getHpData(periodValue, anchorValue);
        setData(payload);
        const chartEntityIds = new Set<string>((payload?.charts || []).map((chart: HpChart) => chart.entity_id));
        onKpisChange(toScreenKpis(payload?.kpis || [], chartEntityIds, scrollToChart));
      } catch (err) {
        setError(formatApiError(err, "Nepodarilo se nacist HP data."));
        onKpisChange([]);
      } finally {
        setLoading(false);
      }
    },
    [onKpisChange, scrollToChart]
  );

  useEffect(() => {
    loadData(chartPeriod, normalizedChartAnchor);
  }, [chartPeriod, loadData, normalizedChartAnchor]);

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
        value_format: entity.value_format || undefined,
        duration_style: entity.value_format ? entity.duration_style || "short" : undefined,
        duration_max_parts: entity.value_format ? Number(entity.duration_max_parts || 2) : undefined,
      }));
    const scan = {
      ...form.scan,
      allowlist: form.scan.allowlist.split(",").map((s: string) => s.trim()).filter(Boolean),
      blocklist: form.scan.blocklist.split(",").map((s: string) => s.trim()).filter(Boolean),
      include_domains: form.scan.include_domains.split(",").map((s: string) => s.trim()).filter(Boolean),
    };
    const defaults = {
      ...form.defaults,
      decimals: form.defaults.decimals === "" ? null : Number(form.defaults.decimals),
    };
    const overrides = form.overrides.map((o: any) => ({
      ...o,
      decimals: o.decimals === "" ? null : Number(o.decimals),
      value_format: o.value_format || null,
      duration_style: o.value_format ? o.duration_style || "short" : null,
      duration_max_parts: o.value_format ? Number(o.duration_max_parts || 2) : null,
    }));

    return {
      ...base,
      hp: {
        enabled: form.enabled,
        source_mode: form.source_mode,
        scan,
        defaults,
        entities,
        overrides,
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

  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewData, setPreviewData] = useState<any[] | null>(null);
  
  const handlePreviewDiscovery = async () => {
    setPreviewLoading(true);
    setResolveError(null);
    try {
      const response = await elektroappApi.previewHpDiscovery(mergedConfig.hp);
      setPreviewData(response.entities || []);
    } catch (err) {
      setResolveError(formatApiError(err, "Preview discovery failed."));
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleOverrideField = (entityId: string, key: string, value: any) => {
    setForm((prev: any) => {
      const overrides = [...prev.overrides];
      const existingIdx = overrides.findIndex((o: any) => o.entity_id === entityId);
      if (existingIdx >= 0) {
        overrides[existingIdx] = { ...overrides[existingIdx], [key]: value };
      } else {
        overrides.push({ entity_id: entityId, [key]: value });
      }
      return { ...prev, overrides };
    });
  };

  const getOverrideFor = (entityId: string): HpFormOverride => {
    return (form.overrides.find((o: any) => o.entity_id === entityId) as HpFormOverride | undefined) || {
      entity_id: entityId,
      enabled: true,
    };
  };

  const handleSave = async () => {
    setSaveLoading(true);
    setSaveMessage(null);
    setSaveError(null);
    try {
      const response = await elektroappApi.saveConfig(mergedConfig);
      await refreshConfig();
      await loadData(chartPeriod, normalizedChartAnchor);
      setSaveMessage(response?.message || "HP konfigurace ulozena.");
    } catch (err) {
      setSaveError(formatApiError(err, "Ulozeni HP konfigurace selhalo."));
    } finally {
      setSaveLoading(false);
    }
  };

  const chartHasStatusCards = Boolean(data?.status_cards?.length);
  const staleItems = useMemo(() => {
    const now = Date.now();
    const thresholdMs = 60 * 60 * 1000;
    const items = [
      ...(data?.kpis || []).map((item) => ({
        entity_id: item.entity_id,
        label: item.label,
        updated_at: item.updated_at,
      })),
      ...(data?.status_cards || []).map((item) => ({
        entity_id: item.entity_id,
        label: item.label,
        updated_at: item.updated_at,
      })),
    ];

    return items.filter((item) => {
      if (!item.updated_at) return false;
      const updatedAt = new Date(item.updated_at).getTime();
      if (Number.isNaN(updatedAt)) return false;
      return now - updatedAt > thresholdMs;
    });
  }, [data]);

  const shiftDayAnchor = (value: string, delta: number) => {
    const date = new Date(`${value}T00:00:00`);
    if (Number.isNaN(date.getTime())) return value;
    date.setDate(date.getDate() + delta);
    const next = `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, "0")}-${String(date.getDate()).padStart(2, "0")}`;
    return clampDateValue(next, maxDate);
  };

  const shiftHpAnchor = (delta: number) => {
    if (chartPeriod === "day") {
      setChartAnchor((prev) => shiftDayAnchor(normalizedChartAnchor || prev, delta));
      return;
    }
    setChartAnchor((prev) => shiftEnergyBalanceAnchor(chartPeriod as "week" | "month" | "year", prev, delta));
  };

  const handlePeriodChange = (nextPeriod: HpPeriod) => {
    setChartPeriod(nextPeriod);
    setChartAnchor((previous) => convertAnchorForPeriod(previous, nextPeriod, maxDate, maxMonth, maxYear));
  };

  const renderAnchorNavigator = () => {
    if (chartPeriod === "month") {
      return <MonthNavigator value={normalizedChartAnchor.slice(0, 7)} onChange={setChartAnchor} maxMonth={maxMonth} />;
    }
    if (chartPeriod === "year") {
      return <YearNavigator value={normalizedChartAnchor.slice(0, 4)} onChange={setChartAnchor} maxYear={maxYear} />;
    }
    return (
      <div className="hp-period-nav">
        <button type="button" className="date-nav-btn" onClick={() => shiftHpAnchor(-1)}>
          Prev
        </button>
        <DateNavigator
          value={normalizedChartAnchor}
          onChange={setChartAnchor}
          maxDate={maxDate}
          compact
        />
        <button
          type="button"
          className="date-nav-btn"
          onClick={() => shiftHpAnchor(1)}
          disabled={normalizedChartAnchor === maxDate}
        >
          Next
        </button>
        <button type="button" className="date-nav-btn date-nav-btn-today" onClick={() => setChartAnchor(maxDate)}>
          {chartPeriod === "week" ? "Tento tyden" : "Dnes"}
        </button>
      </div>
    );
  };

  return (
    <section className="page-hp">
      {staleItems.length ? (
        <div className="alert error hp-stale-alert">
          <strong>HP data mohou byt zastarala.</strong>
          <div>Nektere zobrazene hodnoty jsou starsi nez 60 minut:</div>
          <div className="hp-stale-list">
            {staleItems.map((item) => (
              <span key={item.entity_id}>
                {item.label}: {formatDateTime(item.updated_at)}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {chartHasStatusCards ? (
        <DataCard title="HP statusy" loading={loading} error={error}>
          <div className="hp-status-grid">
            {data?.status_cards?.map((card) => (
              <div key={card.entity_id} className="hp-status-card">
                <div className="hp-status-label">{card.label}</div>
                <div className="hp-status-value">
                  {card.raw_value != null && typeof card.raw_value !== "boolean" && !Number.isNaN(Number(card.raw_value)) && card.value_format && card.value_format !== "default"
                    ? formatNumber(Number(card.raw_value), null, card.unit, card.value_format as HpValueFormat, card.duration_style as HpDurationStyle, card.duration_max_parts as number)
                    : card.value}
                </div>
                <div className="hp-status-detail">{[card.unit, formatTime(card.updated_at)].filter(Boolean).join(" | ") || "\u00A0"}</div>
              </div>
            ))}
          </div>
        </DataCard>
      ) : null}

      <DataCard title="HP grafy" className="card-compact" loading={loading} error={error}>
        <div className="hp-chart-toolbar">
          <div className="view-mode-toggle" aria-label="HP perioda">
            <button type="button" className={`view-mode-btn ${chartPeriod === "day" ? "is-active" : ""}`} onClick={() => handlePeriodChange("day")}>
              Den
            </button>
            <button type="button" className={`view-mode-btn ${chartPeriod === "week" ? "is-active" : ""}`} onClick={() => handlePeriodChange("week")}>
              Tyden
            </button>
            <button type="button" className={`view-mode-btn ${chartPeriod === "month" ? "is-active" : ""}`} onClick={() => handlePeriodChange("month")}>
              Mesic
            </button>
            <button type="button" className={`view-mode-btn ${chartPeriod === "year" ? "is-active" : ""}`} onClick={() => handlePeriodChange("year")}>
              Rok
            </button>
          </div>
          {renderAnchorNavigator()}
        </div>
      </DataCard>

      <div className="hp-charts-grid">
        {data?.charts?.length ? (
          data.charts.map((chart) => (
            <div key={chart.entity_id} ref={(node) => { chartRefs.current[chart.entity_id] = node; }}>
              <DataCard
                title={chart.label}
                empty={!chart.points?.some((point) => point.value != null)}
                emptyMessage="Pro vybrane obdobi nejsou k dispozici zadna data."
              >
                {chart.points?.some((point) => point.value != null) ? <LineTimeChart data={buildChartData(chart, chartPeriod)} options={buildChartOptions(chart, chartPeriod)} height={260} /> : null}
              </DataCard>
            </div>
          ))
        ) : (
          <DataCard title="HP grafy">
            <div className="config-muted">Zadne grafy nejsou zapnute. U numerickych entit aktivuj volbu graf.</div>
          </DataCard>
        )}
      </div>

      <div className="card card-spaced collapsible-card">
        <button
          type="button"
          className={`collapsible-card-header ${configExpanded ? "is-open" : ""}`.trim()}
          onClick={() => setConfigExpanded((prev) => !prev)}
          aria-expanded={configExpanded}
        >
          <span>HP konfigurace</span>
          <span className={`collapsible-card-chevron ${configExpanded ? "is-open" : ""}`.trim()} aria-hidden="true">▾</span>
        </button>
        {configExpanded ? (
          <div className="card-body">
            <div className="card-content">
              <div className="pnd-toggle-grid">
                <label>
                  <input
                    type="checkbox"
                    checked={form.enabled}
                    onChange={(event) => setForm((prev: any) => ({ ...prev, enabled: event.target.checked }))}
                  />
                  HP zapnuto
                </label>
                <label className="pnd-field" style={{ flex: 1, minWidth: 200, maxWidth: 350 }}>
                  <select value={form.source_mode} onChange={(e) => setForm((prev: any) => ({ ...prev, source_mode: e.target.value }))}>
                    <option value="manual">Manualni nastaveni (vychozi)</option>
                    <option value="prefix">Hledat entity podle prefixu</option>
                    <option value="regex">Hledat entity podle regexu</option>
                  </select>
                </label>
              </div>

              {form.source_mode !== "manual" ? (
                <div className="hp-scan-config" style={{ marginTop: "1rem" }}>
                  <h4 style={{ margin: "0.5rem 0", color: "#b1b1b1" }}>Parametry vyhledavani entit</h4>
                  <div className="hp-entity-grid">
                  {form.source_mode === "prefix" ? (
                    <label className="pnd-field">
                      <span>Prefix entit</span>
                      <input value={form.scan.prefix} onChange={(e) => setForm((p: any) => ({...p, scan: {...p.scan, prefix: e.target.value}}))} placeholder="sensor.ebusd_ha_daemon_hmu_" />
                    </label>
                  ) : (
                    <label className="pnd-field">
                      <span>Regex (Regularni vyraz)</span>
                      <input value={form.scan.regex} onChange={(e) => setForm((p: any) => ({...p, scan: {...p.scan, regex: e.target.value}}))} placeholder="^sensor\.ebusd_ha_daemon_hmu_.*$" />
                    </label>
                  )}
                  <label className="pnd-field">
                    <span>Zahrnute domeny (oddelene carkou)</span>
                    <input value={form.scan.include_domains} onChange={(e) => setForm((p: any) => ({...p, scan: {...p.scan, include_domains: e.target.value}}))} placeholder="sensor, binary_sensor" />
                  </label>
                  <label className="pnd-field">
                    <span>Vyradit tyto entity (blocklist, carkou)</span>
                    <input value={form.scan.blocklist} onChange={(e) => setForm((p: any) => ({...p, scan: {...p.scan, blocklist: e.target.value}}))} placeholder="sensor.x, sensor.y" />
                  </label>
                  <label className="pnd-field">
                    <span>Povolit JEN tyto entity (allowlist, carkou)</span>
                    <input value={form.scan.allowlist} onChange={(e) => setForm((p: any) => ({...p, scan: {...p.scan, allowlist: e.target.value}}))} placeholder="Jen tyto entity..." />
                  </label>
                  </div>
                  <div className="pnd-toggle-grid" style={{ marginBottom: "1rem" }}>
                    <label><input type="checkbox" checked={form.scan.exclude_unavailable} onChange={(e) => setForm((p: any) => ({...p, scan: {...p.scan, exclude_unavailable: e.target.checked}}))} /> Ignorovat unavailable/unknown stavy</label>
                  </div>
                  
                  <h4 style={{ margin: "0.5rem 0", color: "#b1b1b1" }}>Vychozi chovani (Defaults)</h4>
                  <div className="pnd-toggle-grid" style={{ marginBottom: "0.5rem" }}>
                    <label><input type="checkbox" checked={form.defaults.kpi_enabled} onChange={(e) => setForm((p: any) => ({...p, defaults: {...p.defaults, kpi_enabled: e.target.checked}}))} /> Zobrazit v KPI</label>
                    <label><input type="checkbox" checked={form.defaults.chart_enabled_numeric} onChange={(e) => setForm((p: any) => ({...p, defaults: {...p.defaults, chart_enabled_numeric: e.target.checked}}))} /> Grafy zapnuty vychozi (Ciselne)</label>
                  </div>
                  <div className="hp-entity-grid" style={{ marginBottom: "1rem" }}>
                    <label className="pnd-field">
                      <span>Kpi Mode Numeric</span>
                      <select value={form.defaults.kpi_mode_numeric} onChange={(e) => setForm((p: any) => ({...p, defaults: {...p.defaults, kpi_mode_numeric: e.target.value}}))}>
                        <option value="last">last</option><option value="avg">avg</option><option value="min">min</option><option value="max">max</option><option value="sum">sum</option><option value="delta">delta</option>
                      </select>
                    </label>
                    <label className="pnd-field">
                      <span>Decimals (Vychozi des. mista)</span>
                      <input type="number" min={0} max={6} value={form.defaults.decimals} onChange={(e) => setForm((p: any) => ({...p, defaults: {...p.defaults, decimals: e.target.value}}))} placeholder="Auto" />
                    </label>
                  </div>
                  
                  <div className="fees-history-actions">
                    <button onClick={handlePreviewDiscovery} disabled={previewLoading}>
                      {previewLoading ? "Nacitam entity z HA..." : "Nacist preview z HA"}
                    </button>
                    <button onClick={handleSave} disabled={saveLoading || !config}>{saveLoading ? "Ukladam..." : "Ulozit HP konfiguraci"}</button>
                  </div>
                  
                  {previewData && (
                    <div className="hp-entity-list" style={{ marginTop: "1rem", opacity: previewLoading ? 0.5 : 1 }}>
                      {previewData.length === 0 ? <div className="config-muted" style={{ padding: "1rem" }}>Nenasly se zadne entity.</div> : null}
                      <span className="config-muted" style={{ display: "block", marginBottom: "0.5rem" }}>Nalezene entity ({previewData.length}) v Preview:</span>
                      {previewData.map((entity: any) => {
                        const override = getOverrideFor(entity.entity_id);
                        const isEnabled = override.enabled !== false;
                        return (
                          <div key={entity.entity_id} className={`hp-entity-card ${!isEnabled ? "is-disabled" : ""}`} style={{ opacity: !isEnabled ? 0.6 : 1 }}>
                            <div className="pnd-toggle-grid" style={{ borderBottom: "1px solid rgba(255,255,255,0.1)", paddingBottom: "0.5rem", marginBottom: "0.5rem" }}>
                              <label style={{ fontWeight: 'bold' }}>
                                <input type="checkbox" checked={isEnabled} onChange={(e) => handleOverrideField(entity.entity_id, "enabled", e.target.checked)} /> {entity.entity_id}
                              </label>
                            </div>
                            <div className="hp-entity-grid">
                               <label className="pnd-field">
                                 <span>Label override</span>
                                 <input value={override.label ?? ""} onChange={(e) => handleOverrideField(entity.entity_id, "label", e.target.value || null)} placeholder={entity.label} disabled={!isEnabled} />
                               </label>
                               <label className="pnd-field">
                                 <span>Decimals override</span>
                                 <input type="number" min={0} max={6} value={override.decimals ?? ""} onChange={(e) => handleOverrideField(entity.entity_id, "decimals", e.target.value || null)} placeholder={entity.decimals ?? "Auto"} disabled={!isEnabled} />
                               </label>
                               <label className="pnd-field">
                                 <span>Measurement</span>
                                 <input value={override.measurement ?? ""} onChange={(e) => handleOverrideField(entity.entity_id, "measurement", e.target.value || null)} placeholder={entity.measurement || "Influx Measurement..."} disabled={!isEnabled} />
                               </label>
                               <label className="pnd-field">
                                 <span>KPI Mode override</span>
                                 <select value={override.kpi_mode ?? ""} onChange={(e) => handleOverrideField(entity.entity_id, "kpi_mode", e.target.value || null)} disabled={!isEnabled}>
                                   <option value="">Vychozi ({entity.kpi_mode})</option>
                                   <option value="last">last</option><option value="avg">avg</option><option value="min">min</option><option value="max">max</option><option value="sum">sum</option><option value="delta">delta</option>
                                 </select>
                               </label>
                               <label className="pnd-field">
                                 <span>Graf override</span>
                                 <select value={override.chart_enabled === undefined ? "" : override.chart_enabled ? "true" : "false"} onChange={(e) => handleOverrideField(entity.entity_id, "chart_enabled", e.target.value ? e.target.value === "true" : null)} disabled={!isEnabled}>
                                   <option value="">Vychozi ({entity.chart_enabled ? "Ano" : "Ne"})</option>
                                   <option value="true">Zobrazit graf</option>
                                   <option value="false">Skryt graf</option>
                                 </select>
                               </label>
                               <label className="pnd-field">
                                 <span>Formát hodnoty</span>
                                 <select value={override.value_format ?? ""} onChange={(e) => handleOverrideField(entity.entity_id, "value_format", e.target.value || null)} disabled={!isEnabled}>
                                   <option value="">Vychozi ({entity.value_format || "default"})</option>
                                   <option value="default">default</option>
                                   <option value="duration_seconds">duration_seconds</option>
                                   <option value="duration_minutes">duration_minutes</option>
                                   <option value="duration_hours">duration_hours</option>
                                   <option value="auto_unit">auto_unit (W/Wh scaling)</option>
                                 </select>
                               </label>
                               {isEnabled && (override.value_format || entity.value_format)?.startsWith("duration") && (
                                 <>
                                   <label className="pnd-field">
                                     <span>Styl trvání</span>
                                     <select value={override.duration_style ?? ""} onChange={(e) => handleOverrideField(entity.entity_id, "duration_style", e.target.value || null)}>
                                       <option value="">Vychozi ({entity.duration_style || "short"})</option>
                                       <option value="short">Krátký (19 h 20 min)</option>
                                       <option value="long">Dlouhý (19 hodin 20 minut)</option>
                                     </select>
                                   </label>
                                   <label className="pnd-field">
                                     <span>Max částí</span>
                                     <input type="number" min={1} max={6} value={override.duration_max_parts ?? ""} onChange={(e) => handleOverrideField(entity.entity_id, "duration_max_parts", e.target.value || null)} placeholder={entity.duration_max_parts || "2"} />
                                   </label>
                                 </>
                               )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              ) : (
                <div className="hp-entities-edit" style={{ marginTop: "1rem" }}>
                  <span className="config-muted" style={{ display: "block", marginBottom: "0.5rem" }}>Rucne vybrane entity:</span>
                  {form.entities.map((entity: any, index: number) => (
                    <div key={index} className="hp-entity-card">
                      <div className="hp-entity-grid">
                        <label className="pnd-field">
                          <span>Entity ID</span>
                          <div style={{ display: "flex", gap: "0.5rem" }}>
                            <input value={entity.entity_id} onChange={(event) => handleEntityField(index, "entity_id", event.target.value)} placeholder="sensor.x" />
                            <button type="button" onClick={() => handleResolveEntity(index)} disabled={resolveLoading === entity.entity_id} style={{ padding: "0 0.75rem" }}>
                              {resolveLoading === entity.entity_id ? "..." : "Auto"}
                            </button>
                          </div>
                        </label>
                        <label className="pnd-field">
                          <span>Label</span>
                          <input value={entity.label} onChange={(event) => handleEntityField(index, "label", event.target.value)} placeholder="Muj senzor" />
                        </label>
                        <label className="pnd-field">
                          <span>Unit</span>
                          <input value={entity.unit} onChange={(event) => handleEntityField(index, "unit", event.target.value)} placeholder="kW" />
                        </label>
                        <label className="pnd-field">
                          <span>Measurement</span>
                          <input value={entity.measurement} onChange={(event) => handleEntityField(index, "measurement", event.target.value)} placeholder="Influx name..." />
                        </label>
                        <label className="pnd-field">
                          <span>Des. místa</span>
                          <input type="number" min={0} max={6} value={entity.decimals} onChange={(event) => handleEntityField(index, "decimals", event.target.value)} placeholder="Auto" />
                        </label>
                        <label className="pnd-field">
                          <span>Formátování</span>
                          <select value={entity.value_format} onChange={(event) => handleEntityField(index, "value_format", event.target.value)}>
                            <option value="">default</option>
                            <option value="duration_seconds">duration_seconds</option>
                            <option value="duration_minutes">duration_minutes</option>
                            <option value="duration_hours">duration_hours</option>
                            <option value="auto_unit">auto_unit (W/Wh scaling)</option>
                          </select>
                        </label>
                        {entity.value_format?.startsWith("duration") && (
                          <>
                            <label className="pnd-field">
                              <span>Styl trvání</span>
                              <select value={entity.duration_style} onChange={(event) => handleEntityField(index, "duration_style", event.target.value)}>
                                <option value="short">Krátký (19 h 20 min)</option>
                                <option value="long">Dlouhý (19 hodin 20 minut)</option>
                              </select>
                            </label>
                            <label className="pnd-field">
                              <span>Max částí</span>
                              <input type="number" min={1} max={6} value={entity.duration_max_parts} onChange={(event) => handleEntityField(index, "duration_max_parts", event.target.value)} placeholder="2" />
                            </label>
                          </>
                        )}
                        <label className="pnd-field">
                           <span>KPI mode</span>
                           <select value={entity.kpi_mode} onChange={(event) => handleEntityField(index, "kpi_mode", event.target.value)}>
                             <option value="last">last</option><option value="avg">avg</option><option value="min">min</option><option value="max">max</option><option value="sum">sum</option><option value="delta">delta</option>
                           </select>
                        </label>
                        <div className="pnd-toggle-grid">
                          <label><input type="checkbox" checked={entity.kpi_enabled} onChange={(event) => handleEntityField(index, "kpi_enabled", event.target.checked)} /> KPI</label>
                          <label><input type="checkbox" checked={entity.chart_enabled} onChange={(event) => handleEntityField(index, "chart_enabled", event.target.checked)} /> Graf</label>
                        </div>
                        <button type="button" className="btn-remove" onClick={() => setForm((p: any) => ({ ...p, entities: p.entities.filter((_: any, i: number) => i !== index) }))}>Odstranit</button>
                      </div>
                    </div>
                  ))}
                  <div className="fees-history-actions">
                    <button type="button" onClick={() => setForm((p: any) => ({ ...p, entities: [...p.entities, emptyEntityRow()] }))}>Pridat entitu</button>
                    <button onClick={handleSave} disabled={saveLoading || !config}>{saveLoading ? "Ukladam..." : "Ulozit HP konfiguraci"}</button>
                  </div>
                </div>
              )}

              {saveMessage && <div className="alert success" style={{ marginTop: "1rem" }}>{saveMessage}</div>}
              {saveError && <div className="alert error" style={{ marginTop: "1rem" }}>{saveError}</div>}
              {resolveError && <div className="alert error" style={{ marginTop: "1rem" }}>{resolveError}</div>}
            </div>
          </div>
        ) : null}
      </div>
    </section>
  );
};

export default HpPage;
