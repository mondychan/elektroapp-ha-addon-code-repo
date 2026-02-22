import React from "react";

const toMonthInput = (date) => {
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, "0");
  return `${y}-${m}`;
};

const shiftMonth = (month, delta) => {
  const [y, m] = String(month).split("-").map(Number);
  if (!y || !m) return month;
  const dt = new Date(y, m - 1 + delta, 1);
  return toMonthInput(dt);
};

const interpolateColor = (ratio, metric) => {
  const r = Math.max(0, Math.min(1, ratio));
  if (metric === "price") {
    const hue = 120 - (120 * r); // green -> red
    return `hsla(${hue}, 75%, 52%, 0.68)`;
  }
  if (metric === "export") {
    return `hsla(145, 70%, ${35 + r * 25}%, ${0.18 + r * 0.55})`;
  }
  return `hsla(28, 88%, ${38 + r * 20}%, ${0.16 + r * 0.64})`; // buy
};

const formatCellValue = (value, metric) => {
  if (value == null) return "-";
  if (metric === "price") return `${Number(value).toFixed(2)} Kc/kWh`;
  return `${Number(value).toFixed(3)} kWh`;
};

const HistoryHeatmapCard = ({
  month,
  setMonth,
  metric,
  setMetric,
  heatmapData,
  loading,
  error,
  onSelectDate,
}) => {
  const min = heatmapData?.stats?.min;
  const max = heatmapData?.stats?.max;
  const denominator = max != null && min != null && max > min ? max - min : null;

  const days = heatmapData?.days || [];
  const hours = heatmapData?.hours || Array.from({ length: 24 }, (_, i) => i);

  return (
    <div className="card">
      <div className="card-header">
        <h3>Heatmapa historie</h3>
      </div>
      <div className="toolbar">
        <button onClick={() => setMonth((prev) => shiftMonth(prev, -1))}>Prev</button>
        <input type="month" value={month} onChange={(e) => setMonth(e.target.value)} />
        <button onClick={() => setMonth((prev) => shiftMonth(prev, 1))}>Next</button>
        <select value={metric} onChange={(e) => setMetric(e.target.value)}>
          <option value="buy">Nakup</option>
          <option value="export">Export</option>
          <option value="price">Cena</option>
        </select>
      </div>

      {loading ? (
        <div className="muted-note">Nacitam heatmapu...</div>
      ) : error ? (
        <div className="alert error">{error}</div>
      ) : (
        <>
          <div className="heatmap-wrap">
            <div className="heatmap-grid">
              <div className="heatmap-corner" />
              {hours.map((hour) => (
                <div key={`h-${hour}`} className="heatmap-hour">
                  {String(hour).padStart(2, "0")}
                </div>
              ))}
              {days.map((dayRow) => (
                <React.Fragment key={dayRow.date}>
                  <button
                    type="button"
                    className="heatmap-day-label"
                    onClick={() => onSelectDate?.(dayRow.date)}
                    title={`Otevrit den ${dayRow.date}`}
                  >
                    {dayRow.day}
                  </button>
                  {dayRow.values.map((value, hourIdx) => {
                    const ratio = value == null || denominator == null ? 0 : (value - min) / denominator;
                    const bg =
                      value == null
                        ? "var(--panel-2)"
                        : interpolateColor(denominator == null ? 1 : ratio, metric);
                    return (
                      <button
                        type="button"
                        key={`${dayRow.date}-${hourIdx}`}
                        className="heatmap-cell"
                        style={{ background: bg }}
                        title={`${dayRow.date} ${String(hourIdx).padStart(2, "0")}:00 - ${formatCellValue(value, metric)}`}
                        onClick={() => onSelectDate?.(dayRow.date)}
                      />
                    );
                  })}
                </React.Fragment>
              ))}
            </div>
          </div>
          <div className="heatmap-legend">
            <span>Min: {min == null ? "-" : metric === "price" ? `${min.toFixed(2)} Kc/kWh` : `${min.toFixed(3)} kWh`}</span>
            <span>Max: {max == null ? "-" : metric === "price" ? `${max.toFixed(2)} Kc/kWh` : `${max.toFixed(3)} kWh`}</span>
          </div>
        </>
      )}
    </div>
  );
};

export default HistoryHeatmapCard;
