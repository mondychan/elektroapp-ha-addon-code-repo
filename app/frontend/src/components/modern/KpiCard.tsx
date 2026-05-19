import React, { useEffect, useRef, useState } from "react";

interface KpiCardProps {
  label: string;
  value: string;
  detail?: string | null;
  unit?: string | null;
  tone?: "price" | "green" | "amber" | "red" | "purple" | "cyan" | "neutral" | string;
  icon?: React.ReactNode;
}

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
    <span className={`modern-kpi__value-frame ${previous ? "is-animating" : ""}`.trim()} aria-live="polite" aria-atomic="true">
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

const KpiCard: React.FC<KpiCardProps> = ({ label, value, detail, unit, tone = "neutral", icon }) => (
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
  </article>
);

export default KpiCard;
