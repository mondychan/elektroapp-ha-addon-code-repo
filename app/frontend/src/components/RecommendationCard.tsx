import React from "react";
import { RecommendationsResponse } from "../types/elektroapp";

const formatWindow = (start?: string | null, end?: string | null) => {
  const toTime = (value?: string | null) => {
    if (!value) return null;
    if (value.includes(" ")) return value.split(" ", 2)[1]?.slice(0, 5);
    if (value.includes("T")) return value.split("T", 2)[1]?.slice(0, 5);
    return value.slice(0, 5);
  };
  const s = toTime(start);
  const e = toTime(end);
  if (s && e) return `${s}-${e}`;
  return s;
};

const RecommendationCard: React.FC<{ recommendations?: RecommendationsResponse | null }> = ({ recommendations }) => {
  const actions = recommendations?.actions || [];
  const metrics = recommendations?.metrics || [];

  if (!recommendations || (!actions.length && !metrics.length)) {
    return <div className="recommendation-empty">Doporuceni nejsou k dispozici.</div>;
  }

  return (
    <div className="recommendation-card">
      <div className="recommendation-metrics">
        {metrics.slice(0, 4).map((metric) => (
          <div className="recommendation-metric" key={metric.key}>
            <span>{metric.label}</span>
            <strong>
              {metric.value ?? "-"} {metric.unit || ""}
            </strong>
          </div>
        ))}
      </div>

      <div className="recommendation-actions">
        {actions.map((action, index) => (
          <div className="recommendation-action" key={`${action.type}-${index}`}>
            <div>
              <div className="recommendation-action-title">
                <strong>{action.title}</strong>
                {formatWindow(action.start, action.end) && <span>{formatWindow(action.start, action.end)}</span>}
              </div>
              <p>{action.reason}</p>
            </div>
            <span className="recommendation-confidence">{Math.round((action.confidence || 0) * 100)}%</span>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RecommendationCard;
