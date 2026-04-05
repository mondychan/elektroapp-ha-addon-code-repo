import React from "react";
import { SolarForecast } from "../types/elektroapp";

interface SolarForecastCardProps {
  solarForecast: SolarForecast | null;
  loading?: boolean;
}

const formatW = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return "-";
  const numeric = Number(value);
  if (Math.abs(numeric) >= 1000) return `${(numeric / 1000).toFixed(2)} kW`;
  return `${Math.round(numeric)} W`;
};

const formatKwh = (value?: number | null, digits = 2) => {
  if (value == null || Number.isNaN(value)) return "-";
  return `${Number(value).toFixed(digits)} kWh`;
};

const formatRatio = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return "-";
  return `${(Number(value) * 100).toFixed(0)} %`;
};

const formatSignedKwh = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return "-";
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)} kWh`;
};

const formatSignedW = (value?: number | null) => {
  if (value == null || Number.isNaN(value)) return "-";
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : "";
  if (Math.abs(numeric) >= 1000) return `${sign}${(numeric / 1000).toFixed(2)} kW`;
  return `${sign}${Math.round(numeric)} W`;
};

const SolarForecastCard: React.FC<SolarForecastCardProps> = ({ solarForecast, loading }) => {
  if (loading || !solarForecast || !solarForecast.enabled) return null;

  const status = solarForecast.status || {};
  const actual = solarForecast.actual || {};
  const comparison = solarForecast.comparison || {};
  const history = solarForecast.history || {};

  const forecastPowerNow = status.power_now ?? status.power_now_w ?? null;
  const actualPowerNow = actual.power_now_w ?? null;
  const actualToday = actual.production_today_kwh ?? null;
  const forecastToday = status.production_today ?? status.energy_production_today_kwh ?? null;
  const forecastRemaining =
    status.production_today_remaining ?? status.energy_production_today_remaining_kwh ?? null;
  const adjustedProjection = comparison.adjusted_projection_today_kwh ?? null;
  const projectionGap = comparison.projection_delta_to_forecast_kwh ?? null;
  const forecastSoFar = comparison.forecast_so_far_kwh ?? null;

  const topItems = [
    { label: "Aktualni vykon panelu", value: formatW(actualPowerNow) },
    { label: "Forecast vykon ted", value: formatW(forecastPowerNow) },
    { label: "Rozdil ted", value: formatSignedW(comparison.power_delta_w) },
    { label: "Vyrobeno dnes realne", value: formatKwh(actualToday) },
    { label: "Forecast do ted", value: formatKwh(forecastSoFar) },
    { label: "Rozdil do ted", value: formatSignedKwh(comparison.delta_so_far_kwh) },
    { label: "Forecast dnes celkem", value: formatKwh(forecastToday) },
    { label: "Forecast zbyva dnes", value: formatKwh(forecastRemaining) },
    { label: "Systemovy odhad dnes", value: formatKwh(adjustedProjection) },
  ];

  const calibrationItems = [
    { label: "Dnesni pace ratio", value: formatRatio(comparison.live_ratio) },
    { label: "Historicky bias", value: formatRatio(comparison.historical_bias_ratio) },
    { label: "Pouzita korekce", value: formatRatio(comparison.effective_bias_ratio) },
    { label: "Odchylka od forecast dne", value: formatSignedKwh(projectionGap) },
    { label: "Historickych dni v cache", value: String(history.days_tracked ?? 0) },
    { label: "Posledni dokonceny den", value: history.last_completed_date || "-" },
  ];

  return (
    <div className="solar-forecast-grid">
      <div className="summary">
        Karta kombinuje Forecast.Solar s realnou PV vyrobou z InfluxDB. Systemovy odhad upravuje zbytek dnesniho
        forecastu podle dnesniho prubehu a historicke odchylky vaseho systemu.
      </div>

      {!actual.pv_power_entity_id && (
        <div className="muted-note">
          Chybi `energy.pv_power_total_entity_id`, proto lze zobrazit jen surovy forecast bez realne vyroby systemu.
        </div>
      )}

      <div className="solar-main-stats">
        {topItems.map((item) => (
          <div key={item.label} className="solar-stat-card">
            <div className="solar-stat-info">
              <div className="solar-stat-label">{item.label}</div>
              <div className="solar-stat-value">{item.value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="battery-meta-grid">
        <div className="battery-meta-block">
          <h4>Kalibrace systemu</h4>
          <div className="battery-meta-list">
            {calibrationItems.map((item) => (
              <div key={item.label}>
                {item.label}: {item.value}
              </div>
            ))}
          </div>
        </div>

        <div className="battery-meta-block">
          <h4>Forecast detail</h4>
          <div className="battery-meta-list">
            <div>Tato hodina: {formatKwh(status.energy_current_hour ?? status.energy_current_hour_kwh ?? null)}</div>
            <div>Pristi hodina: {formatKwh(status.energy_next_hour ?? status.energy_next_hour_kwh ?? null)}</div>
            <div>Zitra celkem: {formatKwh(status.production_tomorrow ?? status.energy_production_tomorrow_kwh ?? null)}</div>
            <div>Spicka dnes: {status.peak_time_today_hhmm || "-"}</div>
            <div>Spicka zitra: {status.peak_time_tomorrow_hhmm || "-"}</div>
            <div>Vzorku dnes: {actual.samples_today != null ? String(actual.samples_today) : "-"}</div>
          </div>
        </div>
      </div>

      {history.recent_days && history.recent_days.length > 0 && (
        <div className="battery-meta-block">
          <h4>Posledni dny v cache</h4>
          <div className="battery-meta-list">
            {history.recent_days.slice().reverse().map((day) => (
              <div key={day.date}>
                {day.date}: real {formatKwh(day.actual_total_kwh)} / forecast {formatKwh(day.forecast_total_kwh)} / ratio{" "}
                {formatRatio(day.ratio)}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default SolarForecastCard;
