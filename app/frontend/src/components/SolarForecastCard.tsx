import React from "react";
import { formatCurrency } from "../utils/formatters";

interface SolarForecastCardProps {
  solarForecast: {
    enabled: boolean;
    status: {
      power_now?: number;
      energy_current_hour?: number;
      energy_next_hour?: number;
      production_today?: number;
      production_today_remaining?: number;
      production_tomorrow?: number;
      peak_today?: string;
      peak_tomorrow?: string;
    };
  } | null;
  loading?: boolean;
}

const SolarForecastCard: React.FC<SolarForecastCardProps> = ({ solarForecast, loading }) => {
  if (loading || !solarForecast || !solarForecast.enabled) return null;

  const { status } = solarForecast;
  
  const items = [
    { label: "Aktuální výkon", value: status.power_now, unit: "W", icon: "☀️" },
    { label: "Produkce tuto hodinu", value: status.energy_current_hour, unit: "kWh", icon: "🕒" },
    { label: "Produkce příští hodinu", value: status.energy_next_hour, unit: "kWh", icon: "⏭️" },
    { label: "Odhad dnes celkem", value: status.production_today, unit: "kWh", icon: "📊" },
    { label: "Zbývá vyrobit dnes", value: status.production_today_remaining, unit: "kWh", icon: "⏳" },
    { label: "Odhad zítra celkem", value: status.production_tomorrow, unit: "kWh", icon: "📅" },
  ];

  return (
    <div className="solar-forecast-grid">
      <div className="solar-main-stats">
        {items.map((item, idx) => (
          <div key={idx} className="solar-stat-card">
            <div className="solar-stat-icon">{item.icon}</div>
            <div className="solar-stat-info">
              <div className="solar-stat-label">{item.label}</div>
              <div className="solar-stat-value">
                {item.value != null ? `${item.value.toFixed(2)} ${item.unit}` : "-"}
              </div>
            </div>
          </div>
        ))}
      </div>
      
      {(status.peak_today || status.peak_tomorrow) && (
        <div className="solar-peaks">
          {status.peak_today && (
            <div className="solar-peak-item">
              <span className="muted">Dnešní špička:</span> <strong>{new Date(status.peak_today).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" })}</strong>
            </div>
          )}
          {status.peak_tomorrow && (
            <div className="solar-peak-item">
              <span className="muted">Zítřejší špička:</span> <strong>{new Date(status.peak_tomorrow).toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" })}</strong>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default SolarForecastCard;
