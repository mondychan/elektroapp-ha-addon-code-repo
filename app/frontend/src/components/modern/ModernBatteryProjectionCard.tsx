import React, { useMemo } from "react";
import BarTimeChart from "../../charting/components/BarTimeChart";
import ForecastLineChart from "../../charting/components/ForecastLineChart";
import {
  buildBatteryChartData,
  buildBatteryPowerChartConfig,
  buildBatterySocChartConfig,
} from "../../charting/builders/batteryChartBuilder";

const formatNumber = (value?: number | null, digits = 0) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(digits);
};

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

const formatEta = (iso?: string | null) => {
  if (!iso) return null;
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

const buildEtaMessage = (batteryData: any) => {
  const status = batteryData?.status;
  const projection = batteryData?.projection;
  if (!batteryData?.is_today || !status) return null;

  if (projection?.state === "charging") {
    const fullAt = formatEta(projection.eta_to_full_at);
    if (fullAt) return `Plná v ${fullAt}`;
    const peakAt = formatEta(projection.peak_soc_at);
    if (peakAt && projection.peak_soc_percent != null) return `Maximum ${formatNumber(projection.peak_soc_percent)} % v ${peakAt}`;
    return "Nabíjí se";
  }

  if (projection?.state === "discharging") {
    const reserveAt = formatEta(projection.eta_to_reserve_at);
    if (reserveAt) return `Do rezervy cca v ${reserveAt}`;
    return "Vybíjí se";
  }

  if (status.battery_state === "idle") return "Stabilní stav";
  return null;
};

const ModernBatteryProjectionCard = ({
  batteryData,
  batteryLoading,
  batteryError,
  onRefresh,
}: {
  batteryData: any;
  batteryLoading?: boolean;
  batteryError?: string | null;
  onRefresh?: () => void;
}) => {
  const chartData = useMemo(() => buildBatteryChartData(batteryData), [batteryData]);
  const socChartConfig = useMemo(() => buildBatterySocChartConfig(chartData), [chartData]);
  const powerChartConfig = useMemo(() => buildBatteryPowerChartConfig(chartData), [chartData]);

  if (batteryError) {
    return (
      <div className="modern-empty modern-empty--error">
        <span>{batteryError}</span>
        <button type="button" className="ghost-button" onClick={onRefresh} disabled={batteryLoading}>
          Obnovit
        </button>
      </div>
    );
  }

  if (!batteryData) {
    return <div className="modern-empty">{batteryLoading ? "Načítám baterii..." : "Data baterie zatím nejsou načtena."}</div>;
  }

  if (!batteryData.enabled || !batteryData.configured) {
    return <div className="modern-empty">{batteryData.detail || "Funkce baterie není nakonfigurovaná."}</div>;
  }

  const status = batteryData.status || {};
  const currentEnergy = batteryData.current_energy || {};
  const soc = Number.isFinite(Number(status.soc_percent)) ? Number(status.soc_percent) : null;
  const etaMessage = buildEtaMessage(batteryData);

  return (
    <div className="modern-battery">
      <div className="modern-battery__state">
        <div
          className="modern-battery-donut"
          style={{ "--battery-soc": `${Math.max(0, Math.min(100, soc ?? 0))}%` } as React.CSSProperties}
          aria-label={`Stav baterie ${soc == null ? "-" : `${formatNumber(soc)} %`}`}
        >
          <span>{soc == null ? "-" : `${formatNumber(soc)} %`}</span>
        </div>
        <div className="modern-battery__copy">
          <span>Stav baterie</span>
          <strong>{formatKwh(status.stored_kwh)}</strong>
          <small>{etaMessage || `${status.battery_state || "Stav"} · ${formatW(status.battery_power_w)}`}</small>
        </div>
      </div>

      <div className="modern-battery__chart">
        <div className="modern-battery__chart-header">
          <strong>Projekce stavu baterie</strong>
          <button type="button" className="ghost-button" onClick={onRefresh} disabled={batteryLoading}>
            Obnovit
          </button>
        </div>
        {!chartData.length ? (
          <div className="modern-empty">Historie baterie není k dispozici.</div>
        ) : (
          <div className="modern-battery__chart-stack">
            <ForecastLineChart height={180} animationProfile="progressive" ariaLabel="Projekce SoC baterie" {...socChartConfig} />
            <BarTimeChart height={92} animationProfile="soft" ariaLabel="Tok výkonu baterie" {...powerChartConfig} />
          </div>
        )}
      </div>

      <div className="modern-detail-grid modern-detail-grid--battery">
        <div>
          <span>Tok baterie</span>
          <strong>{formatW(status.battery_power_w)}</strong>
        </div>
        <div>
          <span>Do rezervy</span>
          <strong>{formatKwh(status.available_to_reserve_kwh)}</strong>
        </div>
        <div>
          <span>Do plna</span>
          <strong>{formatKwh(status.remaining_to_full_kwh)}</strong>
        </div>
        <div>
          <span>Dům</span>
          <strong>{formatW(currentEnergy.house_load_w)}</strong>
        </div>
      </div>
    </div>
  );
};

export default ModernBatteryProjectionCard;
