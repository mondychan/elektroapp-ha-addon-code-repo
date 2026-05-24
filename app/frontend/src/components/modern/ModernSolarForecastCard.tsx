import React, { useState } from "react";
import { IconPie, IconSun, IconSunset, IconTrend } from "./icons";

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

const formatSignedKwh = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : "";
  return `${sign}${numeric.toFixed(2)} kWh`;
};

const formatRatio = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return `${(Number(value) * 100).toFixed(0)} %`;
};

const ModernSolarForecastCard = ({ solarForecast, loading }: { solarForecast: any; loading?: boolean }) => {
  const [showDetail, setShowDetail] = useState(false);

  if (loading) {
    return <div className="modern-empty">Načítám solární předpověď...</div>;
  }
  if (!solarForecast || !solarForecast.enabled) {
    return <div className="modern-empty">Solární forecast není k dispozici.</div>;
  }

  const status = solarForecast.status || {};
  const actual = solarForecast.actual || {};
  const comparison = solarForecast.comparison || {};

  const actualToday = actual.production_today_kwh ?? null;
  const forecastToday = status.production_today ?? status.energy_production_today_kwh ?? null;
  const forecastTomorrow = status.production_tomorrow ?? status.energy_production_tomorrow_kwh ?? null;
  const forecastRemaining = status.production_today_remaining ?? status.energy_production_today_remaining_kwh ?? null;

  const cards = [
    { label: "Dnes", value: formatKwh(actualToday), detail: "Výroba", icon: <IconSun size={34} />, tone: "solar" },
    { label: "Zítra", value: formatKwh(forecastTomorrow), detail: "Forecast", icon: <IconSunset size={34} />, tone: "amber" },
    { label: "Zbývá (dnes)", value: formatKwh(forecastRemaining), detail: "Forecast", icon: <IconPie size={34} />, tone: "blue" },
    { label: "Rozdíl do teď", value: formatSignedKwh(comparison.delta_so_far_kwh), detail: "vs. systémový odhad", icon: <IconTrend size={34} />, tone: "green" },
  ];

  return (
    <div className="modern-solar">
      {!actual.pv_power_entity_id ? (
        <div className="modern-inline-note">
          Chybí `energy.pv_power_total_entity_id`, proto se zobrazuje dostupný forecast bez reálné výroby systému.
        </div>
      ) : null}

      <div className="modern-solar__grid">
        {cards.map((item) => (
          <article key={item.label} className={`modern-solar-metric modern-solar-metric--${item.tone}`}>
            <span className="modern-solar-metric__icon">{item.icon}</span>
            <span>{item.label}</span>
            <strong>{item.value}</strong>
            <small>{item.detail}</small>
          </article>
        ))}
      </div>

      <div className="modern-card-footer">
        <span>
          Aktuální výkon: <strong>{formatW(actual.power_now_w ?? status.power_now_w ?? status.power_now)}</strong>
        </span>
        <button type="button" className="ghost-button" onClick={() => setShowDetail((value) => !value)}>
          {showDetail ? "Skrýt detail" : "Detail"}
        </button>
      </div>

      <div className={`modern-detail-grid modern-solar__details ${showDetail ? "is-open" : ""}`.trim()}>
          <div>
            <span>Forecast dnes</span>
            <strong>{formatKwh(forecastToday)}</strong>
          </div>
          <div>
            <span>Systémový odhad dnes</span>
            <strong>{formatKwh(comparison.adjusted_projection_today_kwh)}</strong>
          </div>
          <div>
            <span>Systémový odhad zítra</span>
            <strong>{formatKwh(comparison.adjusted_projection_tomorrow_kwh)}</strong>
          </div>
          <div>
            <span>Dnešní pace ratio</span>
            <strong>{formatRatio(comparison.live_ratio)}</strong>
          </div>
      </div>
    </div>
  );
};

export default ModernSolarForecastCard;
