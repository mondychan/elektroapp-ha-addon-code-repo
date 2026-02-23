import React, { useMemo, useState } from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

const formatKwh = (value) => (value == null || Number.isNaN(value) ? "-" : `${Number(value).toFixed(2)} kWh`);

const ENERGY_SERIES = [
  { key: "grid_export_kwh", name: "Export grid", color: "#ff7a59" },
  { key: "grid_import_kwh", name: "Import grid", color: "#f0b44d" },
  { key: "pv_kwh", name: "PV vyroba", color: "#39b56a" },
  { key: "house_load_kwh", name: "Spotreba domu", color: "#7cc4ff" },
];

const SERIES_ORDER = ENERGY_SERIES.reduce((acc, series, index) => {
  acc[series.key] = index;
  return acc;
}, {});

const EnergyBalanceTooltip = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;

  const rows = [...payload].sort((a, b) => {
    const aIdx = SERIES_ORDER[a?.dataKey] ?? Number.MAX_SAFE_INTEGER;
    const bIdx = SERIES_ORDER[b?.dataKey] ?? Number.MAX_SAFE_INTEGER;
    return aIdx - bIdx;
  });

  return (
    <div
      style={{
        background: "var(--panel)",
        border: "1px solid var(--border)",
        color: "var(--text)",
        padding: "10px 12px",
        minWidth: 160,
      }}
    >
      <div style={{ fontWeight: 600, marginBottom: 8 }}>{label || "-"}</div>
      {rows.map((entry) => (
        <div
          key={entry.dataKey}
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            gap: 12,
            marginTop: 4,
            borderLeft: `3px solid ${entry.color || "var(--border)"}`,
            paddingLeft: 8,
          }}
        >
          <span style={{ color: entry.color || "var(--text)", whiteSpace: "nowrap" }}>{entry.name}</span>
          <span style={{ whiteSpace: "nowrap" }}>{formatKwh(entry.value)}</span>
        </div>
      ))}
    </div>
  );
};

const EnergyBalanceCard = ({
  period,
  anchor,
  onPrev,
  onNext,
  onPeriodChange,
  data,
  loading,
  error,
}) => {
  const points = data?.points || [];
  const totals = data?.totals || {};
  const [chartType, setChartType] = useState("line");

  const labelTick = useMemo(() => ({ fill: "var(--text-muted)" }), []);

  return (
    <div className="card">
      <div className="card-header">
        <h3>Vyroba vs spotreba</h3>
      </div>
      <div className="toolbar">
        <button onClick={onPrev}>Prev</button>
        <div className="toolbar-label">{anchor || "-"}</div>
        <button onClick={onNext}>Next</button>
        <select value={period} onChange={(e) => onPeriodChange(e.target.value)}>
          <option value="week">Tyden</option>
          <option value="month">Mesic</option>
          <option value="year">Rok</option>
        </select>
        <div className="view-mode-toggle" aria-label="Typ grafu">
          <button
            type="button"
            className={`view-mode-btn ${chartType === "line" ? "is-active" : ""}`}
            onClick={() => setChartType("line")}
          >
            Linky
          </button>
          <button
            type="button"
            className={`view-mode-btn ${chartType === "bar" ? "is-active" : ""}`}
            onClick={() => setChartType("bar")}
          >
            Sloupce
          </button>
        </div>
      </div>

      {loading ? (
        <div className="muted-note">Nacitam energeticky prehled...</div>
      ) : error ? (
        <div className="alert error">{error}</div>
      ) : !points.length ? (
        <div className="muted-note">Data nejsou k dispozici.</div>
      ) : (
        <>
          <div className="energy-balance-totals">
            <span>PV: {formatKwh(totals.pv_kwh)}</span>
            <span>Spotreba: {formatKwh(totals.house_load_kwh)}</span>
            <span>Import: {formatKwh(totals.grid_import_kwh)}</span>
            <span>Export: {formatKwh(totals.grid_export_kwh)}</span>
          </div>
          <ResponsiveContainer width="100%" height={320}>
            {chartType === "line" ? (
              <LineChart data={points} margin={{ top: 10, right: 20, left: 30, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={labelTick} />
                <YAxis tick={labelTick} label={{ value: "kWh", angle: -90, position: "insideLeft" }} />
                <Tooltip content={<EnergyBalanceTooltip />} />
                <Legend />
                {ENERGY_SERIES.map((series) => (
                  <Line
                    key={series.key}
                    type="monotone"
                    dataKey={series.key}
                    name={series.name}
                    stroke={series.color}
                    dot={false}
                    strokeWidth={2}
                  />
                ))}
              </LineChart>
            ) : (
              <BarChart data={points} margin={{ top: 10, right: 20, left: 30, bottom: 10 }} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="label" tick={labelTick} />
                <YAxis tick={labelTick} label={{ value: "kWh", angle: -90, position: "insideLeft" }} />
                <Tooltip content={<EnergyBalanceTooltip />} />
                <Legend />
                {ENERGY_SERIES.map((series) => (
                  <Bar key={series.key} dataKey={series.key} name={series.name} fill={series.color} />
                ))}
              </BarChart>
            )}
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
};

export default EnergyBalanceCard;
