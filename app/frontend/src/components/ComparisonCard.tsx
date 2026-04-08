import React from "react";

interface ComparisonItemProps {
  label: string;
  current: number;
  previous: number;
  diff_pct: number;
  unit: string;
  prevLabel: string;
}

const ComparisonItem: React.FC<ComparisonItemProps> = ({ label, current, previous, diff_pct, unit, prevLabel }) => {
  const diffClass = diff_pct > 0 ? "text-buy" : (diff_pct < 0 ? "text-sell" : "");
  const icon = diff_pct > 0 ? "↗" : (diff_pct < 0 ? "↘" : "→");

  return (
    <div className="comparison-item">
      <div className="comparison-label">{label}</div>
      <div className="comparison-values">
        <div className="comparison-current">{current?.toFixed(2) ?? "-"} {unit}</div>
        <div className="comparison-previous">{prevLabel}: {previous?.toFixed(2) ?? "-"} {unit}</div>
      </div>
      <div className={`comparison-diff ${diffClass}`}>
        {diff_pct != null ? `${icon} ${Math.abs(diff_pct)}%` : "- %"}
      </div>
    </div>
  );
};

interface ComparisonCardProps {
  comparison: {
    today: { cost: number; kwh: number };
    yesterday: { cost: number; kwh: number; diff_cost_pct: number; diff_kwh_pct: number };
    last_week: { cost: number; kwh: number; diff_cost_pct: number; diff_kwh_pct: number };
  } | null;
  loading?: boolean;
}

const ComparisonCard: React.FC<ComparisonCardProps> = ({ comparison, loading }) => {
  if (loading || !comparison) return null;

  return (
    <div className="comparison-grid">
      <div className="comparison-group">
        <h4>Srovnání se včerejškem</h4>
        <ComparisonItem 
          label="Náklady" 
          current={comparison.today.cost} 
          previous={comparison.yesterday.cost} 
          diff_pct={comparison.yesterday.diff_cost_pct} 
          unit="Kč"
          prevLabel="Včera"
        />
        <ComparisonItem 
          label="Spotřeba" 
          current={comparison.today.kwh} 
          previous={comparison.yesterday.kwh} 
          diff_pct={comparison.yesterday.diff_kwh_pct} 
          unit="kWh" 
          prevLabel="Včera"
        />
      </div>
      
      <div className="comparison-group">
        <h4>Srovnání s minulým týdnem</h4>
        <ComparisonItem 
          label="Náklady" 
          current={comparison.today.cost} 
          previous={comparison.last_week.cost} 
          diff_pct={comparison.last_week.diff_cost_pct} 
          unit="Kč" 
          prevLabel="Minulý týden"
        />
        <ComparisonItem 
          label="Spotřeba" 
          current={comparison.today.kwh} 
          previous={comparison.last_week.kwh} 
          diff_pct={comparison.last_week.diff_kwh_pct} 
          unit="kWh" 
          prevLabel="Minulý týden"
        />
      </div>
    </div>
  );
};

export default ComparisonCard;
