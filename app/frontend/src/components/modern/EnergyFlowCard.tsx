import React, { useLayoutEffect, useMemo, useRef, useState } from "react";
import { IconBattery, IconExport, IconGridTower, IconHome, IconSun } from "./icons";

type FlowTone = "solar" | "battery" | "import" | "export";
type FlowNodeId = FlowTone | "home";

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

const flowMeta: Record<FlowTone, { label: string }> = {
  solar: {
    label: "Soláry do domu",
  },
  battery: {
    label: "Baterie do domu",
  },
  import: {
    label: "Import ze sítě",
  },
  export: {
    label: "Export do sítě",
  },
};

type AnimatedValueSnapshot = {
  value: string;
  detail?: string | null;
};

type Point = { x: number; y: number };
type MeasuredBox = Point & { width: number; height: number };

type FlowLayout = {
  width: number;
  height: number;
  paths: Partial<Record<FlowTone, string>>;
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

const flowWidth = (watts: number | null) => {
  if (watts == null) return 2.5;
  return Math.max(2.5, Math.min(6.2, Math.sqrt(Math.abs(watts)) / 16));
};

const centerOf = (box: MeasuredBox): Point => ({
  x: box.x + box.width / 2,
  y: box.y + box.height / 2,
});

const edgePointToward = (box: MeasuredBox, target: Point): Point => {
  const center = centerOf(box);
  const halfWidth = box.width / 2;
  const halfHeight = box.height / 2;
  const dx = target.x - center.x;
  const dy = target.y - center.y;

  if (dx === 0 && dy === 0) return center;

  const xScale = dx === 0 ? Number.POSITIVE_INFINITY : halfWidth / Math.abs(dx);
  const yScale = dy === 0 ? Number.POSITIVE_INFINITY : halfHeight / Math.abs(dy);
  const scale = Math.min(xScale, yScale);

  return {
    x: center.x + dx * scale,
    y: center.y + dy * scale,
  };
};

const buildFlowPath = (startBox: MeasuredBox, endBox: MeasuredBox) => {
  const start = edgePointToward(startBox, centerOf(endBox));
  const end = edgePointToward(endBox, centerOf(startBox));
  const dx = end.x - start.x;
  const dy = end.y - start.y;
  const horizontal = Math.abs(dx) >= Math.abs(dy);

  if (horizontal) {
    const direction = dx >= 0 ? 1 : -1;
    const tension = Math.max(34, Math.min(150, Math.abs(dx) * 0.48));
    return `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} C ${(start.x + tension * direction).toFixed(1)} ${start.y.toFixed(1)} ${(end.x - tension * direction).toFixed(1)} ${end.y.toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;
  }

  const direction = dy >= 0 ? 1 : -1;
  const tension = Math.max(30, Math.min(110, Math.abs(dy) * 0.5));
  return `M ${start.x.toFixed(1)} ${start.y.toFixed(1)} C ${start.x.toFixed(1)} ${(start.y + tension * direction).toFixed(1)} ${end.x.toFixed(1)} ${(end.y - tension * direction).toFixed(1)} ${end.x.toFixed(1)} ${end.y.toFixed(1)}`;
};

const FlowNode = ({
  id,
  label,
  value,
  detail,
  icon,
  nodeRef,
}: {
  id: FlowNodeId;
  label: string;
  value: string;
  detail?: string | null;
  icon: React.ReactNode;
  nodeRef?: (element: HTMLDivElement | null) => void;
}) => {
  const [current, setCurrent] = useState<AnimatedValueSnapshot>({ value, detail });
  const [previous, setPrevious] = useState<AnimatedValueSnapshot | null>(null);
  const [revision, setRevision] = useState(0);
  const currentRef = useRef<AnimatedValueSnapshot>({ value, detail });
  const cleanupTimerRef = useRef<number | null>(null);

  useLayoutEffect(() => {
    const next = { value, detail };
    const prev = currentRef.current;
    if (prev.value === next.value && prev.detail === next.detail) return;

    currentRef.current = next;
    setPrevious(prev);
    setCurrent(next);
    setRevision((counter) => counter + 1);

    if (cleanupTimerRef.current != null) {
      window.clearTimeout(cleanupTimerRef.current);
    }
    cleanupTimerRef.current = window.setTimeout(() => {
      setPrevious(null);
      cleanupTimerRef.current = null;
    }, 260);
  }, [value, detail]);

  useLayoutEffect(
    () => () => {
      if (cleanupTimerRef.current != null) {
        window.clearTimeout(cleanupTimerRef.current);
      }
    },
    []
  );

  const renderSnapshot = (snapshot: AnimatedValueSnapshot) => (
    <>
      <span className="energy-flow-node__value-text">{snapshot.value}</span>
      {snapshot.detail ? <span className="energy-flow-node__detail">{snapshot.detail}</span> : null}
    </>
  );

  return (
    <div ref={nodeRef} className={`energy-flow-node energy-flow-node--${id}`}>
      <span className="energy-flow-node__icon" aria-hidden="true">
        {icon}
      </span>
      <span className="energy-flow-node__label">{label}</span>
      <strong className="energy-flow-node__value energy-flow-node__value-frame" aria-live="polite" aria-atomic="true">
        {previous ? (
          <span key={`prev-${revision}`} className="energy-flow-node__value-layer energy-flow-node__value-layer--previous" aria-hidden="true">
            {renderSnapshot(previous)}
          </span>
        ) : null}
        <span key={`cur-${revision}`} className="energy-flow-node__value-layer energy-flow-node__value-layer--current">
          {renderSnapshot(current)}
        </span>
      </strong>
    </div>
  );
};

const FlowSvg = ({ flows, layout }: { flows: EnergyFlow[]; layout: FlowLayout | null }) => (
  <svg
    className="energy-flow__svg"
    viewBox={layout ? `0 0 ${layout.width} ${layout.height}` : "0 0 1 1"}
    preserveAspectRatio="none"
    role="img"
    aria-hidden="true"
  >
    <defs>
      <filter id="flow-soft-glow" x="-25%" y="-60%" width="150%" height="220%">
        <feGaussianBlur stdDeviation="3.2" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>

    {flows.map((flow) => {
      const meta = flowMeta[flow.id];
      const path = layout?.paths[flow.id];
      const width = flowWidth(flow.watts);
      if (!path) return null;

      return (
        <g key={flow.id} className={`energy-flow__route energy-flow__route--${flow.id} ${flow.active ? "is-active" : "is-idle"}`.trim()}>
          <path className="energy-flow__rail" d={path} />
          <path
            className="energy-flow__stream"
            d={path}
            style={{ "--flow-width": width } as React.CSSProperties}
          />
          {flow.active
            ? [0, 1].map((index) => (
                <circle
                  key={`${flow.id}-pulse-${index}`}
                  className="energy-flow__pulse"
                  r={width + 1.3}
                  style={{ "--pulse-delay": `${index * 0.82}s` } as React.CSSProperties}
                >
                  <animateMotion dur="2.25s" begin={`${index * 0.82}s`} repeatCount="indefinite" path={path} rotate="auto" />
                </circle>
              ))
            : null}
          <title>
            {meta.label}: {flow.watts == null ? "-" : formatPower(flow.watts)}
          </title>
        </g>
      );
    })}
  </svg>
);

const EnergyFlowCard = ({ batteryData, solarForecast }: { batteryData: any; solarForecast: any }) => {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const nodeRefs = useRef<Record<FlowNodeId, HTMLDivElement | null>>({
    solar: null,
    battery: null,
    home: null,
    import: null,
    export: null,
  });
  const [layout, setLayout] = useState<FlowLayout | null>(null);

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
  const flows = useMemo(
    () => deriveEnergyFlows({ pvPower, batteryPower, gridImport, gridExport }),
    [pvPower, batteryPower, gridImport, gridExport]
  );

  const nodeRefCallbacks = useMemo(
    () =>
      ({
        solar: (element: HTMLDivElement | null) => {
          nodeRefs.current.solar = element;
        },
        battery: (element: HTMLDivElement | null) => {
          nodeRefs.current.battery = element;
        },
        home: (element: HTMLDivElement | null) => {
          nodeRefs.current.home = element;
        },
        import: (element: HTMLDivElement | null) => {
          nodeRefs.current.import = element;
        },
        export: (element: HTMLDivElement | null) => {
          nodeRefs.current.export = element;
        },
      }) satisfies Record<FlowNodeId, (element: HTMLDivElement | null) => void>,
    []
  );

  useLayoutEffect(() => {
    const container = containerRef.current;
    if (!container) return undefined;

    let frameId = 0;

    const measure = () => {
      const containerRect = container.getBoundingClientRect();
      const nodes = nodeRefs.current;
      if (containerRect.width <= 0 || containerRect.height <= 0 || Object.values(nodes).some((node) => !node)) {
        return;
      }

      const boxes = Object.fromEntries(
        Object.entries(nodes).map(([id, node]) => {
          const rect = node!.getBoundingClientRect();
          return [
            id,
            {
              x: rect.left - containerRect.left,
              y: rect.top - containerRect.top,
              width: rect.width,
              height: rect.height,
            },
          ];
        })
      ) as Record<FlowNodeId, MeasuredBox>;

      const batteryFlow = flows.find((flow) => flow.id === "battery");
      const paths: Partial<Record<FlowTone, string>> = {
        solar: buildFlowPath(boxes.solar, boxes.home),
        battery:
          batteryFlow?.direction === "home-to-battery"
            ? buildFlowPath(boxes.home, boxes.battery)
            : buildFlowPath(boxes.battery, boxes.home),
        import: buildFlowPath(boxes.import, boxes.home),
        export: buildFlowPath(boxes.home, boxes.export),
      };

      setLayout((previous) => {
        const next = {
          width: Number(containerRect.width.toFixed(1)),
          height: Number(containerRect.height.toFixed(1)),
          paths,
        };
        if (
          previous &&
          previous.width === next.width &&
          previous.height === next.height &&
          (Object.keys(paths) as FlowTone[]).every((key) => previous.paths[key] === next.paths[key])
        ) {
          return previous;
        }
        return next;
      });
    };

    const scheduleMeasure = () => {
      window.cancelAnimationFrame(frameId);
      frameId = window.requestAnimationFrame(measure);
    };

    scheduleMeasure();

    const observedElements = [container, ...Object.values(nodeRefs.current).filter(Boolean)] as Element[];
    let resizeObserver: ResizeObserver | null = null;
    if ("ResizeObserver" in window) {
      resizeObserver = new ResizeObserver(scheduleMeasure);
      observedElements.forEach((element) => resizeObserver?.observe(element));
    }

    window.addEventListener("resize", scheduleMeasure);
    window.addEventListener("orientationchange", scheduleMeasure);

    return () => {
      window.cancelAnimationFrame(frameId);
      resizeObserver?.disconnect();
      window.removeEventListener("resize", scheduleMeasure);
      window.removeEventListener("orientationchange", scheduleMeasure);
    };
  }, [flows]);

  return (
    <div ref={containerRef} className="energy-flow" aria-label="Aktuální energetické toky">
      <FlowSvg flows={flows} layout={layout} />

      <div className="energy-flow__nodes">
        <FlowNode id="solar" label="Soláry" value={formatPower(pvPower)} icon={<IconSun size={31} />} nodeRef={nodeRefCallbacks.solar} />
        <FlowNode
          id="battery"
          label="Baterie"
          value={formatSignedPower(batteryPower)}
          detail={batterySoc != null ? `${Number(batterySoc).toFixed(0)} %` : null}
          icon={<IconBattery size={29} />}
          nodeRef={nodeRefCallbacks.battery}
        />
        <FlowNode
          id="home"
          label="Dům"
          value={formatPower(houseLoad)}
          detail="aktuální zátěž"
          icon={<IconHome size={34} />}
          nodeRef={nodeRefCallbacks.home}
        />
        <FlowNode
          id="import"
          label="Síť import"
          value={formatPower(gridImport)}
          icon={<IconGridTower size={32} />}
          nodeRef={nodeRefCallbacks.import}
        />
        <FlowNode
          id="export"
          label="Export"
          value={formatPower(gridExport)}
          icon={<IconExport size={34} />}
          nodeRef={nodeRefCallbacks.export}
        />
      </div>
    </div>
  );
};

export default EnergyFlowCard;
