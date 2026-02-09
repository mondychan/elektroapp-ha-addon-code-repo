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
  ReferenceLine,
} from "recharts";
import * as d3 from "d3-scale";
import { formatSlotToTime } from "../utils/formatters";

const PriceChartCard = ({ chartData, title, fallbackMessage, vtPeriods, className, highlightSlot }) => {
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

  const shouldHighlight = Number.isInteger(highlightSlot) && highlightSlot >= 0 && highlightSlot < 96;
  const highlightDash = "4 3";

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
            {shouldHighlight && (
              <ReferenceLine
                x={highlightSlot}
                stroke="rgba(77, 121, 255, 0.85)"
                strokeWidth={2}
                strokeDasharray={highlightDash}
                ifOverflow="discard"
              />
            )}
            <XAxis
              dataKey="slot"
              type="number"
              domain={[-0.5, 95.5]}
              tick={({ x, y, payload }) => {
                const slot = payload.value;
                if (!Number.isInteger(slot) || slot < 0 || slot > 95) return null;
                const time = formatSlotToTime(slot);
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
                if (!payload || !payload.length) return `Cas: -`;
                const slot = Number(label);
                if (!Number.isInteger(slot) || slot < 0 || slot > 95) return `Cas: -`;
                const time = formatSlotToTime(slot);
                const vtStatus = getVTStatus(slot);
                return `Cas: ${time} (${vtStatus})`;
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
