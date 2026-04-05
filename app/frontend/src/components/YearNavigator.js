import React, { useEffect, useMemo, useRef, useState } from "react";

const parseYear = (value) => {
  const year = Number.parseInt(String(value), 10);
  if (!Number.isFinite(year)) return null;
  if (year < 1900 || year > 3000) return null;
  return year;
};

/**
 * @param {{
 *   value: string,
 *   onChange?: (nextYear: string) => void,
 *   className?: string,
 *   todayLabel?: string,
 *   maxYear?: string | null,
 * }} props
 */
const YearNavigator = ({ value, onChange, className = "", todayLabel = "Tento rok", maxYear = null }) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const parsedYear = useMemo(() => parseYear(value), [value]);
  const fallbackYear = new Date().getFullYear();
  const selectedYear = parsedYear ?? fallbackYear;
  const [windowStart, setWindowStart] = useState(selectedYear - 5);

  useEffect(() => {
    setWindowStart(selectedYear - 5);
  }, [selectedYear]);

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

  const applyValue = (nextYear) => {
    if (typeof onChange !== "function" || !Number.isFinite(nextYear)) return;
    if (maxYear && nextYear > Number.parseInt(maxYear, 10)) return;
    if (typeof onChange === "function" && Number.isFinite(nextYear)) {
      onChange(String(nextYear));
    }
  };

  const years = Array.from({ length: 12 }, (_, idx) => windowStart + idx);
  const effectiveMaxYear = Number.parseInt(maxYear, 10);
  const hasMaxYear = Number.isFinite(effectiveMaxYear);
  const canGoNext = !hasMaxYear || selectedYear < effectiveMaxYear;
  const canJumpCurrent = !hasMaxYear || fallbackYear <= effectiveMaxYear;
  const canShiftWindow = (delta) => !hasMaxYear || windowStart + delta <= effectiveMaxYear;

  return (
    <div className={`date-nav ${className}`.trim()} ref={rootRef}>
      <button type="button" className="date-nav-btn" onClick={() => applyValue(selectedYear - 1)}>
        Prev
      </button>
      <button
        type="button"
        className="date-nav-trigger"
        onClick={() => setOpen((prev) => !prev)}
        aria-expanded={open}
        aria-haspopup="dialog"
      >
        <span>{selectedYear}</span>
        <span className="date-nav-icon" aria-hidden="true">
          <svg viewBox="0 0 24 24">
            <rect x="3" y="4" width="18" height="17" rx="2" ry="2" />
            <line x1="16" y1="2" x2="16" y2="6" />
            <line x1="8" y1="2" x2="8" y2="6" />
            <line x1="3" y1="10" x2="21" y2="10" />
          </svg>
        </span>
      </button>
      <button type="button" className="date-nav-btn" onClick={() => applyValue(selectedYear + 1)} disabled={!canGoNext}>
        Next
      </button>
      <button type="button" className="date-nav-btn date-nav-btn-today" onClick={() => applyValue(fallbackYear)} disabled={!canJumpCurrent}>
        {todayLabel}
      </button>

      {open && (
        <div className="date-nav-popover" role="dialog" aria-label="Vyber rok">
          <div className="date-nav-popover-header">
            <button type="button" className="date-nav-mini-btn" onClick={() => setWindowStart((prev) => prev - 12)}>
              -12
            </button>
            <div className="date-nav-popover-title">
              {windowStart} - {windowStart + 11}
            </div>
            <button
              type="button"
              className="date-nav-mini-btn"
              onClick={() => setWindowStart((prev) => prev + 12)}
              disabled={!canShiftWindow(12)}
            >
              +12
            </button>
          </div>
          <div className="date-nav-grid date-nav-grid-years">
            {years.map((year) => {
              const isSelected = year === selectedYear;
              const isDisabled = hasMaxYear && year > effectiveMaxYear;
              return (
                <button
                  key={year}
                  type="button"
                  className={`date-nav-grid-btn ${isSelected ? "is-active" : ""}`}
                  disabled={Boolean(isDisabled)}
                  onClick={() => {
                    applyValue(year);
                    setOpen(false);
                  }}
                >
                  {year}
                </button>
              );
            })}
          </div>
        </div>
      )}
    </div>
  );
};

export default YearNavigator;
