import React from "react";
import MonthNavigator from "./MonthNavigator";
import MatrixHeatmapChart from "../charting/components/MatrixHeatmapChart";
import { buildHeatmapChartConfig } from "../charting/builders/heatmapBuilder";

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
  const chartConfig = buildHeatmapChartConfig({ heatmapData, metric });
  const min = heatmapData?.stats?.min;
  const max = heatmapData?.stats?.max;

  return (
    <div className="card">
      <div className="card-header">
        <h3>Heatmapa historie</h3>
      </div>
      <div className="toolbar">
        <MonthNavigator value={month} onChange={setMonth} />
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
            <MatrixHeatmapChart
              height={420}
              animationProfile="progressive"
              {...chartConfig}
              onPointClick={(payload) => onSelectDate?.(payload?.date)}
            />
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
