import React, { useMemo } from "react";
import DateNavigator from "./DateNavigator";
import ComboTimeChart from "../charting/components/ComboTimeChart";
import { buildExportChartConfig, buildExportChartData } from "../charting/builders/costExportBuilder";
import { formatDate } from "../utils/formatters";

const ExportChartCard = ({
  selectedDate,
  setSelectedDate,
  exportPoints,
  exportSummary,
  exportError,
  exportFromCache,
  exportCacheFallback,
  showAnnotations = false,
}) => {
  const selectedDateObj = useMemo(() => new Date(`${selectedDate}T00:00:00`), [selectedDate]);
  const exportChartData = useMemo(() => buildExportChartData(exportPoints), [exportPoints]);
  const chartConfig = useMemo(() => buildExportChartConfig(exportChartData, showAnnotations), [exportChartData, showAnnotations]);

  return (
    <div className="card card-spaced-lg">
      <div className="card-header">
        <h3>Prodej a export - {formatDate(selectedDateObj)}</h3>
      </div>
      <DateNavigator value={selectedDate} onChange={setSelectedDate} />
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
