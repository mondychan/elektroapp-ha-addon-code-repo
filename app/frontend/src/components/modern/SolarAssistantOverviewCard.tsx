import React, { useMemo } from "react";
import ComboTimeChart from "../../charting/components/ComboTimeChart";
import {
  buildSolarOverviewForecastConfig,
  buildSolarOverviewEnergyConfig,
  weatherConditionIcon,
} from "../../charting/builders/solarOverviewBuilder";
import { SolarOverview } from "../../types/elektroapp";

const formatW = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  if (Math.abs(numeric) >= 1000) return `${(numeric / 1000).toFixed(2)} kW`;
  return `${Math.round(numeric)} W`;
};

const formatKwh = (value?: number | null, digits = 2) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return `${Number(value).toFixed(digits)} kWh`;
};

interface Props {
  solarOverview: SolarOverview | null;
  loading?: boolean;
}

const SolarAssistantOverviewCard: React.FC<Props> = ({ solarOverview, loading }) => {
  const forecastConfig = useMemo(() => {
    const points = solarOverview?.forecast_chart?.points;
    const now = solarOverview?.forecast_chart?.now;
    if (!points?.length) return null;
    return buildSolarOverviewForecastConfig({ points, now, theme: null });
  }, [solarOverview?.forecast_chart]);

  const energyConfig = useMemo(() => {
    const points = solarOverview?.overview_chart?.points;
    if (!points?.length) return null;
    return buildSolarOverviewEnergyConfig({ points, theme: null });
  }, [solarOverview?.overview_chart]);

  if (loading) {
    return <div className="modern-empty">Načítám solární přehled...</div>;
  }

  if (!solarOverview) {
    return <div className="modern-empty">Solární přehled není k dispozici.</div>;
  }

  if (solarOverview.error) {
    return (
      <div className="modern-empty modern-empty--error">
        <span>{solarOverview.error}</span>
      </div>
    );
  }

  const totals = solarOverview.totals;
  const forecastPoints = solarOverview.forecast_chart?.points || [];
  const sources = solarOverview.sources;

  const pctComplete = totals && totals.forecast_total_kwh && totals.generated_kwh != null
    ? Math.min(100, Math.max(0, (totals.generated_kwh / totals.forecast_total_kwh) * 100))
    : null;

  return (
    <div className="solar-overview-card">
      {totals && (
        <div className="solar-overview-progress">
          <div className="solar-overview-progress__bar" role="progressbar" aria-valuenow={pctComplete ?? 0} aria-valuemin={0} aria-valuemax={100}>
            <div
              className="solar-overview-progress__fill"
              style={{ width: `${pctComplete ?? 0}%` }}
            />
          </div>
          <div className="solar-overview-progress__stats">
            <span>Vyrobeno: <strong>{formatKwh(totals.generated_kwh)}</strong> {totals.forecast_total_kwh != null ? `z ${formatKwh(totals.forecast_total_kwh)}` : ""}</span>
            {totals.remaining_kwh != null && (
              <span>Zbývá: <strong>{formatKwh(totals.remaining_kwh)}</strong></span>
            )}
          </div>
        </div>
      )}

      {forecastConfig ? (
        <div className="solar-overview-section">
          <h3 className="solar-overview-section__title">PV Today</h3>
          <div className="solar-overview-chart">
            <ComboTimeChart height={340} animationProfile="soft" ariaLabel="Graf solární predikce a výroby" {...forecastConfig} />
          </div>
          {forecastPoints.length > 0 && (
            <div className="solar-overview-weather-strip" aria-label="Předpověď počasí">
              {forecastPoints.map((point, idx) => (
                <div key={idx} className="solar-overview-weather-strip__item" title={point.condition || "–"}>
                  <span className="solar-overview-weather-strip__icon">
                    {point.condition ? weatherConditionIcon(point.condition) : "·"}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="modern-empty">Data solární predikce nejsou k dispozici.</div>
      )}

      {energyConfig ? (
        <div className="solar-overview-section">
          <h3 className="solar-overview-section__title">Přehled</h3>
          <div className="solar-overview-chart">
            <ComboTimeChart height={260} animationProfile="soft" ariaLabel="Graf toku energie" {...energyConfig} />
          </div>
        </div>
      ) : sources?.energy?.available !== false ? (
        <div className="modern-empty">Energetická data nejsou k dispozici.</div>
      ) : null}

      {sources && (
        <div className="solar-overview-footer">
          <span className={`solar-overview-source ${sources.energy?.available ? "solar-overview-source--ok" : "solar-overview-source--missing"}`}>
            Energie {sources.energy?.available ? "✓" : "✗"}
          </span>
          <span className={`solar-overview-source ${sources.forecast?.available ? "solar-overview-source--ok" : "solar-overview-source--missing"}`}>
            Forecast {sources.forecast?.available ? "✓" : "✗"}
          </span>
          <span className={`solar-overview-source ${sources.weather?.available ? "solar-overview-source--ok" : "solar-overview-source--missing"}`}>
            Počasí {sources.weather?.available ? "✓" : sources.weather?.entity_id ? "✗" : "–"}
          </span>
        </div>
      )}
    </div>
  );
};

export default SolarAssistantOverviewCard;
