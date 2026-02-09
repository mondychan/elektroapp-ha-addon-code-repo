import React, { useMemo } from "react";
import {
  LineChart,
  Line,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
} from "recharts";
import { formatDate, toDateInputValue } from "../utils/formatters";

const ExportChartCard = ({
  selectedDate,
  setSelectedDate,
  exportPoints,
  exportSummary,
  exportError,
  exportFromCache,
  exportCacheFallback,
}) => {
  const selectedDateObj = useMemo(() => new Date(`${selectedDate}T00:00:00`), [selectedDate]);
  const formatIsoToTime = (iso) => {
    const dt = new Date(iso);
    const h = dt.getHours().toString().padStart(2, "0");
    const m = dt.getMinutes().toString().padStart(2, "0");
    return `${h}:${m}`;
  };
  const exportChartData = useMemo(() => {
    if (!exportPoints.length) return [];
    return exportPoints.map((p) => ({
      time: formatIsoToTime(p.time),
      kwh: p.kwh,
      sell: p.sell,
    }));
  }, [exportPoints]);

  return (
    <div className="card card-spaced-lg">
      <div className="card-header">
        <h3>Prodej a export - {formatDate(selectedDateObj)}</h3>
      </div>
      <div className="toolbar">
        <button
          onClick={() => {
            const prev = new Date(`${selectedDate}T00:00:00`);
            prev.setDate(prev.getDate() - 1);
            setSelectedDate(toDateInputValue(prev));
          }}
        >
          Prev
        </button>
        <div className="toolbar-label">{formatDate(selectedDateObj)}</div>
        <button
          onClick={() => {
            const next = new Date(`${selectedDate}T00:00:00`);
            next.setDate(next.getDate() + 1);
            setSelectedDate(toDateInputValue(next));
          }}
        >
          Next
        </button>
        <input type="date" value={selectedDate} onChange={(e) => setSelectedDate(e.target.value)} />
        <button
          onClick={() => {
            const today = new Date();
            setSelectedDate(toDateInputValue(today));
          }}
        >
          Dnes
        </button>
      </div>
      {exportError ? (
        <div className="alert error">{exportError}</div>
      ) : !exportChartData.length ? (
        <div className="muted-note">Data pro vybrany den nejsou k dispozici.</div>
      ) : (
        <>
          {exportCacheFallback && (
            <div className="alert">Dotaz na InfluxDB selhal, zobrazuji data z cache.</div>
          )}
          {!exportCacheFallback && exportFromCache && (
            <div className="muted-note">Data jsou z cache exportu.</div>
          )}
          {exportSummary && (
            <div className="summary">
              Celkem: {exportSummary.export_kwh_total?.toFixed(2)} kWh / {exportSummary.sell_total?.toFixed(2)},-Kc
            </div>
          )}
          <div className="cost-stack">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={exportChartData} margin={{ top: 10, right: 20, left: 30, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={false} />
                <YAxis tick={{ fill: "var(--text-muted)" }} label={{ value: "Kc", angle: -90, position: "insideLeft" }} />
                <Tooltip
                  contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
                  itemStyle={{ color: "var(--text)" }}
                  labelStyle={{ color: "var(--text)" }}
                  formatter={(value) => [`${value?.toFixed(2) ?? "-"},-Kc`, "Trzby"]}
                />
                <Line type="monotone" dataKey="sell" stroke="var(--accent-2)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={exportChartData} margin={{ top: 0, right: 20, left: 30, bottom: 10 }} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fill: "var(--text-muted)" }} />
                <YAxis tick={{ fill: "var(--text-muted)" }} label={{ value: "kWh", angle: -90, position: "insideLeft" }} />
                <Tooltip
                  contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
                  itemStyle={{ color: "var(--text)" }}
                  labelStyle={{ color: "var(--text)" }}
                  formatter={(value) => [`${value?.toFixed(3) ?? "-"}`, "Prodej kWh"]}
                />
                <Bar dataKey="kwh" fill="var(--accent)" barSize={6} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      )}
    </div>
  );
};

export default ExportChartCard;
