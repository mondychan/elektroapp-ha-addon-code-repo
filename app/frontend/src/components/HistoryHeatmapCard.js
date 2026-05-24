import React from "react";
import MonthNavigator from "./MonthNavigator";
import MatrixHeatmapChart from "../charting/components/MatrixHeatmapChart";
import { buildHeatmapChartConfig } from "../charting/builders/heatmapBuilder";

const HistoryHeatmapCard = ({
  month,
  setMonth,
  maxMonth,
  metric,
  setMetric,
  heatmapData,
  loading,
  error,
  onSelectDate,
}) => {
  const chartConfig = buildHeatmapChartConfig({ heatmapData, metric });
  const min = heatmapData?.stats?.min;
  const max = heatmapData?.stats?.max;

  return (
    <div className="card-content-stack">
      <div className="toolbar">
        <MonthNavigator value={month} onChange={setMonth} maxMonth={maxMonth} />
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
          <div className="heatmap-wrap" role="figure" aria-label="Heatmapa historie nákladů podle hodin" aria-details="heatmap-data-table">
            <MatrixHeatmapChart
              height={420}
              animationProfile="progressive"
              ariaLabel="Heatmapa historie"
              {...chartConfig}
              onPointClick={(payload) => onSelectDate?.(payload?.date)}
            />
          </div>
          <table id="heatmap-data-table" className="sr-only" aria-label="Data heatmapy v textové podobě">
            <caption>
              {metric === "buy" ? "Náklady" : metric === "export" ? "Export" : "Cena"} za měsíc {month}
            </caption>
            <thead>
              <tr>
                <th>Den</th>
                {Array.from({ length: 24 }, (_, h) => <th key={h}>{h}:00</th>)}
              </tr>
            </thead>
            <tbody>
              {(heatmapData?.days || []).map((dayRow) => (
                <tr key={dayRow.date}>
                  <td>{dayRow.day}</td>
                  {dayRow.values.map((value, hi) => (
                    <td key={hi}>{value == null ? "-" : metric === "price" ? value.toFixed(2) : value.toFixed(3)}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
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
