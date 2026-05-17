import React from "react";
import { IconBattery, IconExport, IconGridTower, IconHome, IconSun } from "./icons";

type FlowTone = "solar" | "battery" | "import" | "export";

export type EnergyFlow = {
  id: FlowTone;
  active: boolean;
  direction: "source-to-home" | "home-to-target" | "target-to-home" | "home-to-battery";
  watts: number | null;
};

type FlowInput = {
  pvPower?: number | null;
  batteryPower?: number | null;
  gridImport?: number | null;
  gridExport?: number | null;
};

const toNumberOrNull = (value: unknown) => {
  const numeric = Number(value);
  return Number.isFinite(numeric) ? numeric : null;
};

export const deriveEnergyFlows = ({ pvPower, batteryPower, gridImport, gridExport }: FlowInput): EnergyFlow[] => {
  const pv = toNumberOrNull(pvPower);
  const battery = toNumberOrNull(batteryPower);
  const imported = toNumberOrNull(gridImport);
  const exported = toNumberOrNull(gridExport);

  return [
    { id: "solar", active: (pv ?? 0) > 20, direction: "source-to-home", watts: pv },
    {
      id: "battery",
      active: Math.abs(battery ?? 0) > 20,
      direction: (battery ?? 0) > 0 ? "home-to-battery" : "source-to-home",
      watts: battery == null ? null : Math.abs(battery),
    },
    { id: "import", active: (imported ?? 0) > 20, direction: "target-to-home", watts: imported },
    { id: "export", active: (exported ?? 0) > 20, direction: "home-to-target", watts: exported },
  ];
};

const formatPower = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  if (Math.abs(numeric) >= 1000) return `${(numeric / 1000).toFixed(2)} kW`;
  return `${Math.round(numeric)} W`;
};

const formatSignedPower = (value?: number | null) => {
  if (value == null || Number.isNaN(Number(value))) return "-";
  const numeric = Number(value);
  const sign = numeric > 0 ? "+" : numeric < 0 ? "-" : "";
  return `${sign}${formatPower(Math.abs(numeric))}`;
};

const flowPathById: Record<FlowTone, { path: string; reversePath?: string }> = {
  solar: { path: "M 175 82 C 250 82 258 138 340 138" },
  battery: {
    path: "M 175 226 C 250 226 258 172 340 172",
    reversePath: "M 340 184 C 258 184 250 238 175 238",
  },
  import: { path: "M 585 82 C 510 82 502 138 420 138" },
  export: { path: "M 420 184 C 502 184 510 226 585 226" },
};

const getFlowPath = (flow: EnergyFlow) =>
  flow.id === "battery" && flow.direction === "home-to-battery"
    ? flowPathById.battery.reversePath || flowPathById.battery.path
    : flowPathById[flow.id].path;

const flowWidth = (watts: number | null) => {
  if (watts == null) return 2.25;
  return Math.max(2.25, Math.min(6.5, Math.abs(watts) / 950));
};

const FlowNode = ({
  id,
  label,
  value,
  detail,
  icon,
}: {
  id: "solar" | "battery" | "home" | "import" | "export";
  label: string;
  value: string;
  detail?: string | null;
  icon: React.ReactNode;
}) => (
  <div className={`energy-flow-node energy-flow-node--${id}`}>
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
  const flows = deriveEnergyFlows({ pvPower, batteryPower, gridImport, gridExport });

  return (
    <div className="energy-flow" aria-label="Aktuální energetické toky">
      <svg className="energy-flow__svg" viewBox="0 0 760 310" role="img" aria-hidden="true">
        <defs>
          {["solar", "battery", "import", "export"].map((tone) => (
            <marker
              key={tone}
              id={`flow-arrow-${tone}`}
              markerWidth="10"
              markerHeight="10"
              refX="8"
              refY="5"
              orient="auto"
              markerUnits="strokeWidth"
            >
              <path className={`energy-flow__marker energy-flow__marker--${tone}`} d="M 0 0 L 10 5 L 0 10 z" />
            </marker>
          ))}
        </defs>
        {flows.map((flow) => (
          <path
            key={flow.id}
            className={`energy-flow__path energy-flow__path--${flow.id} ${flow.active ? "is-active" : "is-idle"}`.trim()}
            d={getFlowPath(flow)}
            markerEnd={`url(#flow-arrow-${flow.id})`}
            style={{ "--flow-width": flowWidth(flow.watts) } as React.CSSProperties}
          />
        ))}
      </svg>

      <div className="energy-flow__nodes">
        <FlowNode id="solar" label="Soláry" value={formatPower(pvPower)} icon={<IconSun size={31} />} />
        <FlowNode
          id="battery"
          label="Baterie"
          value={formatSignedPower(batteryPower)}
          detail={batterySoc != null ? `${Number(batterySoc).toFixed(0)} %` : null}
          icon={<IconBattery size={29} />}
        />
        <FlowNode
          id="home"
          label="Dům"
          value={formatPower(houseLoad)}
          detail="aktuální zátěž"
          icon={<IconHome size={34} />}
        />
        <FlowNode id="import" label="Síť import" value={formatPower(gridImport)} icon={<IconGridTower size={32} />} />
        <FlowNode id="export" label="Export" value={formatPower(gridExport)} icon={<IconExport size={34} />} />
      </div>
    </div>
  );
};

export default EnergyFlowCard;
