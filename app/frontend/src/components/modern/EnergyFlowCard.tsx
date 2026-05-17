import React from "react";

const formatPower = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  if (Math.abs(numeric) >= 1000) return `${(numeric / 1000).toFixed(2)} kW`;
  return `${Math.round(numeric)} W`;
};

const FlowNode = ({
  label,
  value,
  detail,
  tone,
  icon,
}: {
  label: string;
  value: string;
  detail?: string | null;
  tone: string;
  icon: string;
}) => (
  <div className={`energy-flow-node energy-flow-node--${tone}`}>
    <span className="energy-flow-node__icon" aria-hidden="true">{icon}</span>
    <span className="energy-flow-node__label">{label}</span>
    <strong>{value}</strong>
    {detail ? <small>{detail}</small> : null}
  </div>
);

const EnergyFlowCard = ({ batteryData, solarForecast }: { batteryData: any; solarForecast: any }) => {
  const currentEnergy = batteryData?.current_energy || {};
  const batteryStatus = batteryData?.status || {};
  const actualSolar = solarForecast?.actual || {};
  const solarStatus = solarForecast?.status || {};

  const pvPower = currentEnergy.pv_power_total_w ?? actualSolar.power_now_w ?? solarStatus.power_now_w ?? solarStatus.power_now;
  const houseLoad = currentEnergy.house_load_w;
  const gridImport = currentEnergy.grid_import_w;
  const gridExport = currentEnergy.grid_export_w;
  const batteryPower = batteryStatus.battery_power_w;
  const batterySoc = batteryStatus.soc_percent;

  return (
    <div className="energy-flow">
      <div className="energy-flow__grid">
        <FlowNode label="Soláry" value={formatPower(pvPower)} tone="solar" icon="☀" />
        <div className="energy-flow__connector energy-flow__connector--solar" aria-hidden="true" />
        <FlowNode
          label="Dům"
          value={formatPower(houseLoad)}
          detail="aktuální zátěž"
          tone="home"
          icon="⌂"
        />
        <div className="energy-flow__connector energy-flow__connector--import" aria-hidden="true" />
        <FlowNode label="Síť import" value={formatPower(gridImport)} tone="import" icon="⌁" />

        <FlowNode
          label="Baterie"
          value={formatPower(batteryPower)}
          detail={batterySoc != null ? `${Number(batterySoc).toFixed(0)} %` : null}
          tone="battery"
          icon="▣"
        />
        <div className="energy-flow__connector energy-flow__connector--battery" aria-hidden="true" />
        <div className="energy-flow__spacer" />
        <div className="energy-flow__connector energy-flow__connector--export" aria-hidden="true" />
        <FlowNode label="Export" value={formatPower(gridExport)} tone="export" icon="→" />
      </div>
    </div>
  );
};

export default EnergyFlowCard;
