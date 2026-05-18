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

const flowMeta: Record<FlowTone, { label: string; gradient: string; path: string; reversePath?: string }> = {
  solar: {
    label: "Soláry do domu",
    gradient: "flow-gradient-solar",
    path: "M 178 90 C 252 90 288 137 344 152",
  },
  battery: {
    label: "Baterie do domu",
    gradient: "flow-gradient-battery",
    path: "M 178 240 C 252 240 288 190 344 176",
    reversePath: "M 344 192 C 288 222 252 252 178 252",
  },
  import: {
    label: "Import ze sítě",
    gradient: "flow-gradient-import",
    path: "M 582 90 C 508 90 472 137 416 152",
  },
  export: {
    label: "Export do sítě",
    gradient: "flow-gradient-export",
    path: "M 416 190 C 472 212 508 240 582 240",
  },
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

const getFlowPath = (flow: EnergyFlow) =>
  flow.id === "battery" && flow.direction === "home-to-battery"
    ? flowMeta.battery.reversePath || flowMeta.battery.path
    : flowMeta[flow.id].path;

const flowWidth = (watts: number | null) => {
  if (watts == null) return 2.5;
  return Math.max(2.5, Math.min(6.2, Math.sqrt(Math.abs(watts)) / 16));
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

const FlowSvg = ({ flows }: { flows: EnergyFlow[] }) => (
  <svg className="energy-flow__svg" viewBox="0 0 760 330" role="img" aria-hidden="true">
    <defs>
      <linearGradient id="flow-gradient-solar" x1="0%" x2="100%" y1="0%" y2="0%">
        <stop offset="0%" stopColor="var(--accent-amber)" stopOpacity="0.95" />
        <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0.9" />
      </linearGradient>
      <linearGradient id="flow-gradient-battery" x1="0%" x2="100%" y1="0%" y2="0%">
        <stop offset="0%" stopColor="var(--accent-green)" stopOpacity="0.95" />
        <stop offset="100%" stopColor="var(--accent-cyan)" stopOpacity="0.85" />
      </linearGradient>
      <linearGradient id="flow-gradient-import" x1="100%" x2="0%" y1="0%" y2="0%">
        <stop offset="0%" stopColor="var(--accent-red)" stopOpacity="0.95" />
        <stop offset="100%" stopColor="var(--accent-purple)" stopOpacity="0.78" />
      </linearGradient>
      <linearGradient id="flow-gradient-export" x1="0%" x2="100%" y1="0%" y2="0%">
        <stop offset="0%" stopColor="var(--accent-cyan)" stopOpacity="0.92" />
        <stop offset="100%" stopColor="var(--accent-green)" stopOpacity="0.9" />
      </linearGradient>
      <filter id="flow-soft-glow" x="-25%" y="-60%" width="150%" height="220%">
        <feGaussianBlur stdDeviation="3.2" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
      {Object.keys(flowMeta).map((tone) => (
        <marker
          key={tone}
          id={`flow-arrow-${tone}`}
          markerWidth="12"
          markerHeight="12"
          refX="10"
          refY="6"
          orient="auto"
          markerUnits="userSpaceOnUse"
        >
          <path className={`energy-flow__marker energy-flow__marker--${tone}`} d="M 1 1 L 11 6 L 1 11 z" />
        </marker>
      ))}
    </defs>

    {flows.map((flow) => {
      const meta = flowMeta[flow.id];
      const path = getFlowPath(flow);
      const width = flowWidth(flow.watts);
      return (
        <g key={flow.id} className={`energy-flow__route energy-flow__route--${flow.id} ${flow.active ? "is-active" : "is-idle"}`.trim()}>
          <path className="energy-flow__rail" d={path} />
          <path
            className="energy-flow__stream"
            d={path}
            markerEnd={flow.active ? `url(#flow-arrow-${flow.id})` : undefined}
            style={{ "--flow-width": width, "--flow-gradient": `url(#${meta.gradient})` } as React.CSSProperties}
          />
          {flow.active
            ? [0, 1].map((index) => (
                <circle
                  key={`${flow.id}-pulse-${index}`}
                  className="energy-flow__pulse"
                  r={width + 1.3}
                  style={{ "--pulse-delay": `${index * 0.82}s`, "--flow-gradient": `url(#${meta.gradient})` } as React.CSSProperties}
                >
                  <animateMotion dur="2.25s" begin={`${index * 0.82}s`} repeatCount="indefinite" path={path} rotate="auto" />
                </circle>
              ))
            : null}
          <title>{meta.label}: {flow.watts == null ? "-" : formatPower(flow.watts)}</title>
        </g>
      );
    })}
  </svg>
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
      <FlowSvg flows={flows} />

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
