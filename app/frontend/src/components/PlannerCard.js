import React from "react";
import { formatDate } from "../utils/formatters";

const PLANNER_PRESETS = ["30", "60", "90", "120", "180", "200", "240", "300"];

const PlannerCard = ({
  plannerDuration,
  setPlannerDuration,
  loadPlanner,
  plannerError,
  plannerLoading,
  plannerNote,
  plannerResults,
}) => {
  const [showCustomInput, setShowCustomInput] = React.useState(() => !PLANNER_PRESETS.includes(String(plannerDuration || "")));

  const formatOffset = (startStr) => {
    const start = new Date(startStr.replace(" ", "T"));
    const now = new Date();
    const diffMs = start - now;
    const diffMin = Math.max(0, Math.round(diffMs / 60000));
    if (diffMin < 60) return `za ${diffMin} min`;
    const hours = Math.floor(diffMin / 60);
    const minutes = diffMin % 60;
    return minutes ? `za ${hours} h ${minutes} min` : `za ${hours} h`;
  };

  return (
    <div className="card card-spaced">
      <div className="card-header">
        <h3>Planovac spotrebicu</h3>
      </div>
      <div className="planner-controls">
        <div className="planner-field">
          <label>Delka programu (min)</label>
          <div className="planner-toolbar-row">
            <div className="planner-presets" role="group" aria-label="Vyber delky programu">
              {PLANNER_PRESETS.map((preset) => {
                const isActive = !showCustomInput && String(plannerDuration) === preset;
                return (
                  <button
                    key={preset}
                    type="button"
                    className={`planner-preset${isActive ? " is-active" : ""}`}
                    onClick={() => {
                      setShowCustomInput(false);
                      setPlannerDuration(preset);
                      loadPlanner(preset);
                    }}
                  >
                    {preset}
                  </button>
                );
              })}
              <button
                type="button"
                className={`planner-preset${showCustomInput ? " is-active" : ""}`}
                onClick={() => setShowCustomInput(true)}
              >
                Vlastni
              </button>
            </div>
            {!showCustomInput && <div className="planner-selected-duration">Vybrano: {plannerDuration || "-"} min</div>}
          </div>
        </div>
        {showCustomInput && (
          <div className="planner-custom-row">
            <div className="planner-field planner-custom-field">
              <label htmlFor="planner-custom-duration">Vlastni delka (min)</label>
              <input
                id="planner-custom-duration"
                type="text"
                inputMode="numeric"
                pattern="\\d*"
                autoComplete="off"
                maxLength={3}
                value={plannerDuration}
                onChange={(e) => {
                  const cleaned = e.target.value.replace(/[^0-9]/g, "");
                  setPlannerDuration(cleaned);
                }}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    loadPlanner();
                  }
                }}
                placeholder="120"
              />
            </div>
            <div className="planner-actions planner-actions-inline">
              <button type="button" onClick={() => loadPlanner()}>
                Najit okna
              </button>
            </div>
          </div>
        )}
      </div>
      <div className="config-muted">Okna hledame v dostupnych datech (dnes + zitra, pokud jsou).</div>
      {plannerError && <div className="alert error">{plannerError}</div>}
      {plannerLoading && <div className="config-muted">Pocitam nejlepsi okna...</div>}
      {plannerNote && <div className="config-muted">{plannerNote}</div>}
      {!plannerLoading && !plannerNote && plannerResults.length === 0 && (
        <div className="config-muted">Zatim nemame doporucene okna.</div>
      )}
      {plannerResults.length > 0 && (
        <ul className="planner-list">
          {plannerResults.map((item, idx) => (
            <li key={`${item.start}-${idx}`}>
              {formatDate(new Date(item.start.replace(" ", "T")))}: {item.start.slice(11, 16)} -{" "}
              {item.end.slice(11, 16)} ({formatOffset(item.start)}) | prumer {item.avg_price?.toFixed(2) ?? "-"} Kc/kWh | odhad{" "}
              {item.total_cost?.toFixed(2) ?? "-"} Kc
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export default PlannerCard;
