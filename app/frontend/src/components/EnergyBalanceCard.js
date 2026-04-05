import React, { useMemo, useState } from "react";
import LineTimeChart from "../charting/components/LineTimeChart";
import BarTimeChart from "../charting/components/BarTimeChart";
import {
  ENERGY_SERIES,
  buildEnergyBalanceBarConfig,
  buildEnergyBalanceLineConfig,
} from "../charting/builders/energyBalanceBuilder";

const formatKwh = (value) => (value == null || Number.isNaN(value) ? "-" : `${Number(value).toFixed(2)} kWh`);

const EnergyBalanceCard = ({
  period,
  anchor,
  onPrev,
  onNext,
  disableNext = false,
  onPeriodChange,
  data,
  loading,
  error,
}) => {
  const points = useMemo(() => data?.points || [], [data]);
  const totals = data?.totals || {};
  const [chartType, setChartType] = useState("line");

  const lineConfig = useMemo(() => buildEnergyBalanceLineConfig(points), [points]);
  const barConfig = useMemo(() => buildEnergyBalanceBarConfig(points), [points]);

  return (
    <div className="card-content-stack">
      <div className="toolbar">
        <button onClick={onPrev}>Prev</button>
        <div className="toolbar-label">{anchor || "-"}</div>
        <button onClick={onNext} disabled={disableNext}>Next</button>
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
            {ENERGY_SERIES.map((series) => (
              <span key={series.key}>
                {series.name}: {formatKwh(totals[series.key])}
              </span>
            ))}
          </div>
          {chartType === "line" ? (
            <LineTimeChart height={320} animationProfile="soft" {...lineConfig} />
          ) : (
            <BarTimeChart height={320} animationProfile="soft" {...barConfig} />
          )}
        </>
      )}
    </div>
  );
};

export default EnergyBalanceCard;
