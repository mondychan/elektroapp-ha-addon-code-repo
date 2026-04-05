import React, { useEffect, useMemo, useRef, useState } from "react";

const parseMonth = (value) => {
  if (!value || !/^\d{4}-\d{2}$/.test(value)) return null;
  const [year, month] = value.split("-").map(Number);
  if (!year || !month || month < 1 || month > 12) return null;
  return { year, month };
};

const toMonthValue = (year, month) => `${year}-${String(month).padStart(2, "0")}`;

const shiftMonth = (value, delta) => {
  const parsed = parseMonth(value);
  if (!parsed) return value;
  const dt = new Date(parsed.year, parsed.month - 1 + delta, 1);
  return toMonthValue(dt.getFullYear(), dt.getMonth() + 1);
};

const compareMonthValues = (left, right) => {
  if (!left && !right) return 0;
  if (!left) return -1;
  if (!right) return 1;
  return left.localeCompare(right);
};

const MONTH_LABELS = Array.from({ length: 12 }, (_, idx) =>
  new Date(2026, idx, 1).toLocaleDateString("cs-CZ", { month: "short" })
);

/**
 * @param {{
 *   value: string,
 *   onChange?: (nextValue: string) => void,
 *   className?: string,
 *   todayLabel?: string,
 *   maxMonth?: string | null,
 * }} props
 */
const MonthNavigator = ({ value, onChange, className = "", todayLabel = "Tento mesic", maxMonth = null }) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const parsed = useMemo(() => parseMonth(value), [value]);
  const [panelYear, setPanelYear] = useState(parsed?.year ?? new Date().getFullYear());
  const prevValue = useMemo(() => shiftMonth(value, -1), [value]);
  const nextValue = useMemo(() => shiftMonth(value, 1), [value]);

  useEffect(() => {
    if (parsed?.year) {
      setPanelYear(parsed.year);
    }
  }, [parsed?.year]);

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const applyValue = (nextValue) => {
    if (typeof onChange !== "function" || !nextValue) return;
    if (maxMonth && compareMonthValues(nextValue, maxMonth) > 0) return;
    if (typeof onChange === "function" && nextValue) {
      onChange(nextValue);
    }
  };

  const selectedLabel = parsed
    ? new Date(parsed.year, parsed.month - 1, 1).toLocaleDateString("cs-CZ", { month: "long", year: "numeric" })
    : "Vyber mesic";

  const today = new Date();
  const currentMonthValue = toMonthValue(today.getFullYear(), today.getMonth() + 1);
  const effectiveMaxMonth = maxMonth || null;
  const canGoNext = !effectiveMaxMonth || compareMonthValues(nextValue, effectiveMaxMonth) <= 0;
  const canJumpCurrent = !effectiveMaxMonth || compareMonthValues(currentMonthValue, effectiveMaxMonth) <= 0;
  const canShiftPanelYear = (delta) => {
    if (!effectiveMaxMonth) return true;
    const maxParsed = parseMonth(effectiveMaxMonth);
    if (!maxParsed) return true;
    return panelYear + delta <= maxParsed.year;
  };

  return (
    <div className={`date-nav ${className}`.trim()} ref={rootRef}>
      <button type="button" className="date-nav-btn" onClick={() => applyValue(prevValue)}>
        Prev
      </button>
      <button
        type="button"
        className="date-nav-trigger"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <span>{selectedLabel}</span>
        <span className="date-nav-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <rect x="3" y="4" width="18" height="17" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </span>
      </button>
      <button type="button" className="date-nav-btn" onClick={() => applyValue(nextValue)} disabled={!canGoNext}>
        Next
      </button>
      <button
        type="button"
        className="date-nav-btn date-nav-btn-today"
        onClick={() => applyValue(currentMonthValue)}
        disabled={!canJumpCurrent}
      >
        {todayLabel}
      </button>

      {open && (
        <div className="date-nav-popover" role="dialog" aria-label="Vyber mesic">
          <div className="date-nav-popover-header">
            <button type="button" className="date-nav-mini-btn" onClick={() => setPanelYear((prev) => prev - 1)}>
              Prev rok
            </button>
            <div className="date-nav-popover-title">{panelYear}</div>
            <button
              type="button"
              className="date-nav-mini-btn"
              onClick={() => setPanelYear((prev) => prev + 1)}
              disabled={!canShiftPanelYear(1)}
            >
              Next rok
            </button>
          </div>
          <div className="date-nav-grid date-nav-grid-months">
            {MONTH_LABELS.map((label, idx) => {
              const monthNum = idx + 1;
              const monthValue = toMonthValue(panelYear, monthNum);
              const isSelected = monthValue === value;
              const isDisabled = effectiveMaxMonth && compareMonthValues(monthValue, effectiveMaxMonth) > 0;
              return (
                <button
                  key={monthValue}
                  type="button"
                  className={`date-nav-grid-btn ${isSelected ? "is-active" : ""}`}
                  disabled={Boolean(isDisabled)}
                  onClick={() => {
                    applyValue(monthValue);
                    setOpen(false);
                  }}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default MonthNavigator;
