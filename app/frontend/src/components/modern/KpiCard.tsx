import React from "react";

interface KpiCardProps {
  label: string;
  value: string;
  detail?: string | null;
  unit?: string | null;
  tone?: "price" | "green" | "amber" | "red" | "purple" | "cyan" | "neutral" | string;
  icon?: React.ReactNode;
}

const KpiCard: React.FC<KpiCardProps> = ({ label, value, detail, unit, tone = "neutral", icon }) => (
  <article className={`modern-kpi modern-kpi--${tone}`.trim()}>
    <div className="modern-kpi__top">
      <span className="modern-kpi__label">{label}</span>
      {icon ? <span className="modern-kpi__icon" aria-hidden="true">{icon}</span> : null}
    </div>
    <div className="modern-kpi__value-row">
      <strong className="modern-kpi__value">{value}</strong>
      {unit ? <span className="modern-kpi__unit">{unit}</span> : null}
    </div>
    {detail ? <div className="modern-kpi__detail">{detail}</div> : null}
  </article>
);

export default KpiCard;
