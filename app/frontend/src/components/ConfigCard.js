import React from "react";
import InfoTable from "./InfoTable";
import FeesHistorySection from "./FeesHistorySection";

const ConfigCard = ({
  configRows,
  cacheRows,
  cacheStatus,
  showFeesHistory,
  onToggleFeesHistory,
  feesHistory,
  feesHistoryLoading,
  feesHistoryError,
  onSaveFeesHistory,
  defaultFeesValues,
}) => (
  <div className="card card-top">
    <h3>Aktualni konfigurace</h3>
    <div className="config-grid">
      <div className="config-column">
        <h4>Nastaveni cen</h4>
        <div className="config-muted">Hodnoty jsou bez DPH.</div>
        <InfoTable rows={configRows} valueAlign="right" headerValueAlign="right" />
      </div>
      <div className="config-column">
        <h4>Cache</h4>
        {cacheStatus ? (
          <InfoTable rows={cacheRows} valueAlign="left" headerValueAlign="left" showUnit={false} showHeader={false} />
        ) : (
          <div className="config-muted">Cache data nejsou k dispozici.</div>
        )}
      </div>
    </div>
    <FeesHistorySection
      visible={showFeesHistory}
      onToggle={onToggleFeesHistory}
      history={feesHistory}
      loading={feesHistoryLoading}
      error={feesHistoryError}
      onSave={onSaveFeesHistory}
      defaultValues={defaultFeesValues}
    />
  </div>
);

export default ConfigCard;
