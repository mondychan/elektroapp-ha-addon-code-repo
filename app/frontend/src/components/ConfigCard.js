import React from "react";
import InfoTable from "./InfoTable";
import FeesHistorySection from "./FeesHistorySection";

const ConfigCard = ({
  configRows,
  cacheRows,
  consumptionCacheRows,
  cacheStatus,
  showFeesHistory,
  onToggleFeesHistory,
  feesHistory,
  feesHistoryLoading,
  feesHistoryError,
  onSaveFeesHistory,
  defaultFeesValues,
  priceProviderLabel,
  priceProviderUrl,
  onRefreshPrices,
  refreshingPrices,
  pricesRefreshMessage,
  pricesRefreshError,
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
        <h4>Cache cen</h4>
        {cacheStatus?.prices ? (
          <InfoTable rows={cacheRows} valueAlign="left" headerValueAlign="left" showUnit={false} showHeader={false} />
        ) : (
          <div className="config-muted">Cache cen nejsou k dispozici.</div>
        )}
        <h4 className="config-subtitle">Cache spotreby</h4>
        {cacheStatus?.consumption ? (
          <InfoTable
            rows={consumptionCacheRows}
            valueAlign="left"
            headerValueAlign="left"
            showUnit={false}
            showHeader={false}
          />
        ) : (
          <div className="config-muted">Cache spotreby nejsou k dispozici.</div>
        )}
        <h4 className="config-subtitle">Zdroj cen</h4>
        <div>
          <a href={priceProviderUrl} target="_blank" rel="noopener noreferrer">
            {priceProviderLabel}
          </a>
        </div>
        <div className="config-actions">
          <button onClick={onRefreshPrices} disabled={refreshingPrices}>
            {refreshingPrices ? "Obnovuji..." : "Obnovit data dnes/zitra"}
          </button>
        </div>
        {pricesRefreshMessage ? <div className="config-muted">{pricesRefreshMessage}</div> : null}
        {pricesRefreshError ? <div className="alert error">{pricesRefreshError}</div> : null}
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
