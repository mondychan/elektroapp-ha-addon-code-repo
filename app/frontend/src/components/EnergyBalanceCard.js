import React from "react";
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  Legend,
} from "recharts";

const formatKwh = (value) => (value == null || Number.isNaN(value) ? "-" : `${Number(value).toFixed(2)} kWh`);

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
            <LineChart data={points} margin={{ top: 10, right: 20, left: 30, bottom: 10 }}>
              <CartesianGrid strokeDasharray="3 3" />
              <XAxis dataKey="label" tick={{ fill: "var(--text-muted)" }} />
              <YAxis tick={{ fill: "var(--text-muted)" }} label={{ value: "kWh", angle: -90, position: "insideLeft" }} />
              <Tooltip
                contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
                itemStyle={{ color: "var(--text)" }}
                labelStyle={{ color: "var(--text)" }}
                formatter={(value) => [formatKwh(value), ""]}
              />
              <Legend />
              <Line type="monotone" dataKey="pv_kwh" name="PV vyroba" stroke="#39b56a" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="house_load_kwh" name="Spotreba domu" stroke="#7cc4ff" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="grid_import_kwh" name="Import grid" stroke="#f0b44d" dot={false} strokeWidth={2} />
              <Line type="monotone" dataKey="grid_export_kwh" name="Export grid" stroke="#ff7a59" dot={false} strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </>
      )}
    </div>
  );
};

export default EnergyBalanceCard;
