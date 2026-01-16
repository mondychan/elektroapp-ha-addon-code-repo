import React from "react";
import InfoTable from "./InfoTable";

const ConfigCard = ({ configRows, cacheRows, cacheStatus }) => (
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
  </div>
);

export default ConfigCard;
