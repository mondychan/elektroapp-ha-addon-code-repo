import React, { useMemo } from "react";
import DateNavigator from "./DateNavigator";
import ComboTimeChart from "../charting/components/ComboTimeChart";
import { buildCostChartConfig, buildCostChartData } from "../charting/builders/costExportBuilder";

const CostChartCard = ({
  selectedDate,
  setSelectedDate,
  maxDate,
  costs,
  costsSummary,
  costsError,
  costsFromCache,
  costsCacheFallback,
  showAnnotations = false,
}) => {
  const costChartData = useMemo(() => buildCostChartData(costs), [costs]);
  const chartConfig = useMemo(() => buildCostChartConfig(costChartData, showAnnotations), [costChartData, showAnnotations]);

  return (
    <div className="card-content-stack">
      <div className="toolbar toolbar-compact">
        <DateNavigator value={selectedDate} onChange={setSelectedDate} maxDate={maxDate} />
      </div>
      {costsError ? (
        <div className="alert error">{costsError}</div>
      ) : !costChartData.length ? (
        <div className="muted-note">Data pro vybrany den nejsou k dispozici.</div>
      ) : (
        <>
          {costsCacheFallback && <div className="alert">Dotaz na InfluxDB selhal, zobrazuji data z cache.</div>}
          {!costsCacheFallback && costsFromCache && <div className="muted-note">Data jsou z cache spotreby.</div>}
          {costsSummary && (
            <div className="summary">
              Celkem: {costsSummary.kwh_total?.toFixed(2)} kWh / {costsSummary.cost_total?.toFixed(2)},-Kc
            </div>
          )}
          <ComboTimeChart height={340} animationProfile="realtime" {...chartConfig} />
        </>
      )}
    </div>
  );
};

export default CostChartCard;
