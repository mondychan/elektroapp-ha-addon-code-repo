import React, { useMemo } from "react";
import DateNavigator from "./DateNavigator";
import ComboTimeChart from "../charting/components/ComboTimeChart";
import { buildCostChartConfig, buildCostChartData } from "../charting/builders/costExportBuilder";
import { formatDate } from "../utils/formatters";

const CostChartCard = ({
  selectedDate,
  setSelectedDate,
  costs,
  costsSummary,
  costsError,
  costsFromCache,
  costsCacheFallback,
  showAnnotations = false,
}) => {
  const selectedDateObj = useMemo(() => new Date(`${selectedDate}T00:00:00`), [selectedDate]);
  const costChartData = useMemo(() => buildCostChartData(costs), [costs]);
  const chartConfig = useMemo(() => buildCostChartConfig(costChartData, showAnnotations), [costChartData, showAnnotations]);

  return (
    <div className="card card-spaced-lg">
      <div className="card-header">
        <h3>Naklady a nakup - {formatDate(selectedDateObj)}</h3>
      </div>
      <DateNavigator value={selectedDate} onChange={setSelectedDate} />
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
