import React from "react";

interface KPIItem {
  key: string;
  label: string;
  value: string;
  detail?: string | null;
  secondaryMetrics?: Array<{
    key: string;
    label: string;
    value: string;
  }>;
  tone?: "price" | "neutral" | "buy" | "sell" | "battery" | string;
  onClick?: () => void;
}

interface KPIScreenProps {
  items: KPIItem[];
  layout?: "default" | "compact";
}

const KPIScreen: React.FC<KPIScreenProps> = ({ items, layout = "default" }) => {
  return (
    <section className={`kpi-strip ${layout === "compact" ? "kpi-strip--compact" : ""}`.trim()} aria-label="Dnesni KPI">
      {items.map((item) => (
        <div
          key={item.key}
          className={`kpi-tile ${item.tone ? `kpi-tile--${item.tone}` : ""}`}
          onClick={item.onClick}
          style={item.onClick ? { cursor: "pointer" } : undefined}
          title={item.onClick ? `Zobrazit detail ${item.label}` : undefined}
        >
          <div className="kpi-tile-label">{item.label}</div>
          <div className="kpi-tile-value">{item.value}</div>
          {item.secondaryMetrics?.length ? (
            <div className="kpi-tile-secondary">
              {item.secondaryMetrics.map((metric) => (
                <div key={metric.key} className="kpi-tile-secondary-item">
                  <span className="kpi-tile-secondary-label">{metric.label}</span>
                  <span className="kpi-tile-secondary-value">{metric.value}</span>
                </div>
              ))}
            </div>
          ) : null}
          {item.detail ? <div className="kpi-tile-detail">{item.detail}</div> : null}
        </div>
      ))}
    </section>
  );
};

export default KPIScreen;
