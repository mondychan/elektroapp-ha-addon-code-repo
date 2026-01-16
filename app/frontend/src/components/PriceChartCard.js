import React from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  CartesianGrid,
  ResponsiveContainer,
  Cell,
} from "recharts";
import * as d3 from "d3-scale";

const PriceChartCard = ({ chartData, title, fallbackMessage, vtPeriods, className }) => {
  if (!chartData.length && !fallbackMessage) {
    return null;
  }

  const minPrice = chartData.length ? Math.min(...chartData.map((d) => d.final)) : 0;
  const maxPrice = chartData.length ? Math.max(...chartData.map((d) => d.final)) : 0;
  const colorScale = d3.scaleLinear().domain([minPrice, maxPrice]).range(["#00FF00", "#FF0000"]);
  const vtPeriodsSafe = vtPeriods || [];

  const getVTStatus = (slot) => {
    return vtPeriodsSafe.some(([start, end]) => slot >= start * 4 && slot < end * 4) ? "VT" : "NT";
  };

  return (
    <div className={`card ${className || ""}`.trim()}>
      <div className="card-header">
        <h3>{title}</h3>
      </div>
      {!chartData.length ? (
        <div className="config-muted">{fallbackMessage}</div>
      ) : (
        <ResponsiveContainer width="100%" height={400}>
          <BarChart data={chartData} margin={{ top: 20, right: 20, left: 40, bottom: 20 }}>
            <CartesianGrid strokeDasharray="3 3" stroke="var(--border)" />
            <XAxis
              dataKey="time"
              tick={({ x, y, payload }) => {
                const time = payload.value;
                const [h, m] = time.split(":").map(Number);
                const slot = h * 4 + m / 15;
                const isVT = getVTStatus(slot) === "VT";
                return (
                  <text
                    x={x}
                    y={y + 10}
                    textAnchor="middle"
                    fill={isVT ? "#FF0000" : "#00AA00"}
                    fontSize={10}
                  >
                    {time} ({isVT ? "VT" : "NT"})
                  </text>
                );
              }}
            />
            <YAxis
              tick={{ fill: "var(--text-muted)" }}
              label={{ value: "Cena", angle: -90, position: "insideLeft" }}
              tickFormatter={(v) => `${v.toFixed(2)},-Kc`}
            />
            <Tooltip
              contentStyle={{ background: "var(--panel)", borderColor: "var(--border)", color: "var(--text)" }}
              itemStyle={{ color: "var(--text)" }}
              labelStyle={{ color: "var(--text)" }}
              formatter={(value, name, props) => {
                if (props.dataKey === "spot") return [`${value.toFixed(2)},-Kc`, "Spot"];
                if (props.dataKey === "extra") return [`${props.payload.final.toFixed(2)},-Kc`, "Konecna cena"];
                return [`${value.toFixed(2)},-Kc`, name];
              }}
              labelFormatter={(label, payload) => {
                if (!payload || !payload.length) return `Cas: ${label}`;
                const [h, m] = label.split(":").map(Number);
                const slot = h * 4 + m / 15;
                const vtStatus = getVTStatus(slot);
                return `Cas: ${label} (${vtStatus})`;
              }}
            />
            <Bar dataKey="spot" stackId="a">
              {chartData.map((entry, index) => (
                <Cell key={`cell-spot-${index}`} fill="#4D79FF" />
              ))}
            </Bar>
            <Bar dataKey="extra" stackId="a">
              {chartData.map((entry, index) => (
                <Cell key={`cell-extra-${index}`} fill={colorScale(entry.final)} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      )}
    </div>
  );
};

export default PriceChartCard;
