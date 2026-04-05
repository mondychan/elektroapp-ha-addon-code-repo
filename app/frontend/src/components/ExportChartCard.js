import React, { useMemo } from "react";
import DateNavigator from "./DateNavigator";
import ComboTimeChart from "../charting/components/ComboTimeChart";
import { buildExportChartConfig, buildExportChartData } from "../charting/builders/costExportBuilder";

const ExportChartCard = ({
  selectedDate,
  setSelectedDate,
  maxDate,
  exportPoints,
  exportSummary,
  exportError,
  exportFromCache,
  exportCacheFallback,
  showAnnotations = false,
}) => {
  const exportChartData = useMemo(() => buildExportChartData(exportPoints), [exportPoints]);
  const chartConfig = useMemo(() => buildExportChartConfig(exportChartData, showAnnotations), [exportChartData, showAnnotations]);

  return (
    <div className="card-content-stack">
      <div className="toolbar toolbar-compact">
        <DateNavigator value={selectedDate} onChange={setSelectedDate} maxDate={maxDate} />
      </div>
      {exportError ? (
        <div className="alert error">{exportError}</div>
      ) : !exportChartData.length ? (
        <div className="muted-note">Data pro vybrany den nejsou k dispozici.</div>
      ) : (
        <>
          {exportCacheFallback && <div className="alert">Dotaz na InfluxDB selhal, zobrazuji data z cache.</div>}
          {!exportCacheFallback && exportFromCache && <div className="muted-note">Data jsou z cache exportu.</div>}
          {exportSummary && (
            <div className="summary">
              Celkem: {exportSummary.export_kwh_total?.toFixed(2)} kWh / {exportSummary.sell_total?.toFixed(2)},-Kc
            </div>
          )}
          <ComboTimeChart height={340} animationProfile="realtime" {...chartConfig} />
        </>
      )}
    </div>
  );
};

export default ExportChartCard;
