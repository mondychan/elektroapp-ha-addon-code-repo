import React, { useEffect, useRef, useState } from "react";

interface KpiCardProps {
  label: string;
  value: string;
  detail?: string | null;
  unit?: string | null;
  tone?: "price" | "green" | "amber" | "red" | "purple" | "cyan" | "neutral" | string;
  icon?: React.ReactNode;
}

// The live dashboard repaints battery tiles at 1 Hz; a polite announcement on
// every pixel change would read the whole KPI grid aloud once per second and
// drown out navigation.  Cross-fade the number visually, but only announce it
// when the value has settled for this long (a screen reader then hears one
// update per real change, not one per poll).
const ANNOUNCE_SETTLE_MS = 4200;

type AnimatedValueSnapshot = {
  value: string;
  unit?: string | null;
};

const AnimatedKpiValue = ({ value, unit }: { value: string; unit?: string | null }) => {
  const [current, setCurrent] = useState<AnimatedValueSnapshot>({ value, unit });
  const [previous, setPrevious] = useState<AnimatedValueSnapshot | null>(null);
  const [revision, setRevision] = useState(0);
  const currentRef = useRef<AnimatedValueSnapshot>({ value, unit });
  const cleanupTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const next = { value, unit };
    const prev = currentRef.current;
    if (prev.value === next.value && prev.unit === next.unit) return;

    currentRef.current = next;
    setPrevious(prev);
    setCurrent(next);
    setRevision((value) => value + 1);

    if (cleanupTimerRef.current != null) {
      window.clearTimeout(cleanupTimerRef.current);
    }
    cleanupTimerRef.current = window.setTimeout(() => {
      setPrevious(null);
      cleanupTimerRef.current = null;
    }, 260);
  }, [value, unit]);

  useEffect(
    () => () => {
      if (cleanupTimerRef.current != null) {
        window.clearTimeout(cleanupTimerRef.current);
      }
    },
    []
  );

  const renderLine = (snapshot: AnimatedValueSnapshot) => (
    <>
      <span className="modern-kpi__value-text">{snapshot.value}</span>
      {snapshot.unit ? <span className="modern-kpi__unit">{snapshot.unit}</span> : null}
    </>
  );

  return (
    <span className={`modern-kpi__value-frame ${previous ? "is-animating" : ""}`.trim()}>
      {previous ? (
        <span key={`prev-${revision}`} className="modern-kpi__value-layer modern-kpi__value-layer--previous" aria-hidden="true">
          {renderLine(previous)}
        </span>
      ) : null}
      <span key={`cur-${revision}`} className="modern-kpi__value-layer modern-kpi__value-layer--current">
        {renderLine(current)}
      </span>
    </span>
  );
};

const KpiCard: React.FC<KpiCardProps> = ({ label, value, detail, unit, tone = "neutral", icon }) => {
  const [announcedValue, setAnnouncedValue] = useState(value);
  const announceTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (announcedValue === value) return undefined;
    if (announceTimerRef.current != null) {
      window.clearTimeout(announceTimerRef.current);
    }
    announceTimerRef.current = window.setTimeout(() => {
      setAnnouncedValue(value);
      announceTimerRef.current = null;
    }, ANNOUNCE_SETTLE_MS);
    return () => {
      if (announceTimerRef.current != null) {
        window.clearTimeout(announceTimerRef.current);
        announceTimerRef.current = null;
      }
    };
  }, [value, announcedValue]);

  return (
    <article className={`modern-kpi modern-kpi--${tone}`.trim()}>
      <div className="modern-kpi__top">
        <span className="modern-kpi__label">{label}</span>
        {icon ? <span className="modern-kpi__icon" aria-hidden="true">{icon}</span> : null}
      </div>
      <div className="modern-kpi__value-row">
        <strong className="modern-kpi__value">
          <AnimatedKpiValue value={value} unit={unit} />
        </strong>
      </div>
      {detail ? <div className="modern-kpi__detail">{detail}</div> : null}
      <span className="sr-only" aria-live="polite" aria-atomic="true">
        {`${label}: ${announcedValue}${unit ? ` ${unit}` : ""}`}
      </span>
    </article>
  );
};

export default KpiCard;
