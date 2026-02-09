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

const CostChartCard = ({
  selectedDate,
  setSelectedDate,
  costs,
  costsSummary,
  costsError,
  costsFromCache,
  costsCacheFallback,
}) => {
  const selectedDateObj = useMemo(() => new Date(`${selectedDate}T00:00:00`), [selectedDate]);
  const formatIsoToTime = (iso) => {
    const dt = new Date(iso);
    const h = dt.getHours().toString().padStart(2, "0");
    const m = dt.getMinutes().toString().padStart(2, "0");
    return `${h}:${m}`;
  };
  const costChartData = useMemo(() => {
    if (!costs.length) return [];
    return costs.map((p) => ({
      time: formatIsoToTime(p.time),
      kwh: p.kwh,
      cost: p.cost,
    }));
  }, [costs]);

  return (
    <div className="card card-spaced-lg">
      <div className="card-header">
        <h3>Naklady a nakup - {formatDate(selectedDateObj)}</h3>
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
      {costsError ? (
        <div className="alert error">{costsError}</div>
      ) : !costChartData.length ? (
        <div className="muted-note">Data pro vybrany den nejsou k dispozici.</div>
      ) : (
        <>
          {costsCacheFallback && (
            <div className="alert">Dotaz na InfluxDB selhal, zobrazuji data z cache.</div>
          )}
          {!costsCacheFallback && costsFromCache && (
            <div className="muted-note">Data jsou z cache spotreby.</div>
          )}
          {costsSummary && (
            <div className="summary">
              Celkem: {costsSummary.kwh_total?.toFixed(2)} kWh / {costsSummary.cost_total?.toFixed(2)},-Kc
            </div>
          )}
          <div className="cost-stack">
            <ResponsiveContainer width="100%" height={220}>
              <LineChart data={costChartData} margin={{ top: 10, right: 20, left: 30, bottom: 0 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={false} />
                <YAxis tick={{ fill: "var(--text-muted)" }} label={{ value: "Kc", angle: -90, position: "insideLeft" }} />
                <Tooltip
                  contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
                  itemStyle={{ color: "var(--text)" }}
                  labelStyle={{ color: "var(--text)" }}
                  formatter={(value) => [`${value?.toFixed(2) ?? "-"},-Kc`, "Naklad"]}
                />
                <Line type="monotone" dataKey="cost" stroke="var(--accent-2)" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={costChartData} margin={{ top: 0, right: 20, left: 30, bottom: 10 }} barCategoryGap="20%">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="time" tick={{ fill: "var(--text-muted)" }} />
                <YAxis tick={{ fill: "var(--text-muted)" }} label={{ value: "kWh", angle: -90, position: "insideLeft" }} />
                <Tooltip
                  contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
                  itemStyle={{ color: "var(--text)" }}
                  labelStyle={{ color: "var(--text)" }}
                  formatter={(value) => [`${value?.toFixed(3) ?? "-"}`, "Nakup kWh"]}
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

export default CostChartCard;
