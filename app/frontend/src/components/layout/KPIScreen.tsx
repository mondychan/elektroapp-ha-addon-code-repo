import React from "react";

interface KPIItem {
  key: string;
  label: string;
  value: string;
  detail?: string | null;
  tone?: "price" | "neutral" | "buy" | "sell" | "battery" | string;
}

interface KPIScreenProps {
  items: KPIItem[];
}

const KPIScreen: React.FC<KPIScreenProps> = ({ items }) => {
  return (
    <section className="kpi-strip" aria-label="Dnesni KPI">
      {items.map((item) => (
        <div key={item.key} className={`kpi-tile ${item.tone ? `kpi-tile--${item.tone}` : ""}`}>
          <div className="kpi-tile-label">{item.label}</div>
          <div className="kpi-tile-value">{item.value}</div>
          <div className="kpi-tile-detail">{item.detail || ""}</div>
        </div>
      ))}
    </section>
  );
};

export default KPIScreen;
