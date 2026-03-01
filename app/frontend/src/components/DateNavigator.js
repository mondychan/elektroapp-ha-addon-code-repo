import React, { useEffect, useMemo, useRef, useState } from "react";
import { DayPicker } from "react-day-picker";
import { cs } from "react-day-picker/locale";
import "react-day-picker/src/style.css";

const parseDate = (value) => {
  if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const dt = new Date(`${value}T00:00:00`);
  return Number.isNaN(dt.getTime()) ? null : dt;
};

const toDateValue = (dt) => {
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const shiftDateValue = (value, deltaDays) => {
  const dt = parseDate(value);
  if (!dt) return value;
  dt.setDate(dt.getDate() + deltaDays);
  return toDateValue(dt);
};

const DateNavigator = ({
  value,
  onChange,
  className = "",
  compact = false,
  todayLabel = "Dnes",
  showShortcuts = !compact,
  minDate = null,
  maxDate = null,
}) => {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  const selectedDate = useMemo(() => parseDate(value), [value]);
  const minDateObj = useMemo(() => parseDate(minDate), [minDate]);
  const maxDateObj = useMemo(() => parseDate(maxDate), [maxDate]);

  const selectedLabel = selectedDate
    ? selectedDate.toLocaleDateString("cs-CZ", compact ? { day: "2-digit", month: "2-digit", year: "numeric" } : { day: "numeric", month: "long", year: "numeric" })
    : "Vyber datum";

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (!rootRef.current) return;
      if (!rootRef.current.contains(event.target)) {
        setOpen(false);
      }
    };
    const handleEscape = (event) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);
    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, []);

  const applyValue = (nextValue) => {
    if (typeof onChange === "function" && nextValue) {
      onChange(nextValue);
    }
  };

  return (
    <div className={`date-nav ${compact ? "date-nav-compact" : ""} ${className}`.trim()} ref={rootRef}>
      {!compact && (
        <button type="button" className="date-nav-btn" onClick={() => applyValue(shiftDateValue(value, -1))}>
          Prev
        </button>
      )}
      <button
        type="button"
        className={`date-nav-trigger ${compact ? "date-nav-trigger-compact" : ""}`.trim()}
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
      {!compact && (
        <button type="button" className="date-nav-btn" onClick={() => applyValue(shiftDateValue(value, 1))}>
          Next
        </button>
      )}
      {!compact && (
        <button type="button" className="date-nav-btn date-nav-btn-today" onClick={() => applyValue(toDateValue(new Date()))}>
          {todayLabel}
        </button>
      )}

      {open && (
        <div className="date-nav-popover" role="dialog" aria-label="Vyber datum">
          <DayPicker
            mode="single"
            selected={selectedDate || undefined}
            fromDate={minDateObj || undefined}
            toDate={maxDateObj || undefined}
            onSelect={(nextDate) => {
              if (!nextDate) return;
              applyValue(toDateValue(nextDate));
              setOpen(false);
            }}
            locale={cs}
            showOutsideDays
            weekStartsOn={1}
          />
          {showShortcuts && (
            <div className="date-nav-shortcuts">
              <button type="button" onClick={() => applyValue(shiftDateValue(value, -1))}>
                Vcera
              </button>
              <button type="button" onClick={() => applyValue(toDateValue(new Date()))}>
                Dnes
              </button>
              <button type="button" onClick={() => applyValue(shiftDateValue(value, 1))}>
                Zitra
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DateNavigator;
