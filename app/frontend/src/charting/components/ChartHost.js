import React, { useEffect, useMemo, useRef, useState } from "react";
import { Chart } from "react-chartjs-2";
import { resolveAnimationProfile } from "../animationProfiles";
import { ensureChartJsRegistered } from "../chartjs/register";
import { applyChartDefaults, getChartTheme } from "../chartTheme";

const LONG_PRESS_MS = 550;

const mergePlugins = (plugins) => (plugins || []).filter(Boolean);

const resolveInteractionPayload = (chart, event, pointPayloads) => {
  if (!chart) {
    return null;
  }
  const nativeEvent = event?.nativeEvent || event;
  const elements = chart.getElementsAtEventForMode(nativeEvent, "nearest", { intersect: true }, true);
  if (!elements?.length) {
    return null;
  }
  const element = elements[0];
  const payload = pointPayloads?.[element.index] || null;
  return {
    ...payload,
    index: element.index,
    datasetIndex: element.datasetIndex,
  };
};

const ChartHost = ({
  type,
  data,
  options,
  plugins,
  className,
  height = 320,
  testId,
  animationProfile = "soft",
  pointPayloads,
  onLongPressPoint,
  onPointClick,
}) => {
  ensureChartJsRegistered();

  const [theme, setTheme] = useState(() => getChartTheme());
  const themeSignature = useMemo(() => Object.values(theme).join("|"), [theme]);
  const chartRef = useRef(null);
  const longPressTimeoutRef = useRef(null);

  useEffect(() => {
    if (typeof MutationObserver === "undefined" || typeof document === "undefined") {
      return undefined;
    }

    const refreshTheme = () => setTheme(getChartTheme());
    refreshTheme();

    const observer = new MutationObserver(refreshTheme);
    observer.observe(document.body, {
      attributes: true,
      attributeFilter: ["data-theme", "class", "style"],
    });

    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    applyChartDefaults(theme);
    chartRef.current?.update("none");
  }, [theme, themeSignature]);

  useEffect(
    () => () => {
      if (longPressTimeoutRef.current) {
        clearTimeout(longPressTimeoutRef.current);
      }
    },
    []
  );

  const chartOptions = useMemo(
    () => ({
      maintainAspectRatio: false,
      animation: resolveAnimationProfile(animationProfile),
      ...options,
    }),
    [animationProfile, options]
  );

  const clearLongPress = () => {
    if (!longPressTimeoutRef.current) {
      return;
    }
    clearTimeout(longPressTimeoutRef.current);
    longPressTimeoutRef.current = null;
  };

  const startLongPress = (event) => {
    if (typeof onLongPressPoint !== "function") {
      return;
    }
    const payload = resolveInteractionPayload(chartRef.current, event, pointPayloads);
    if (!payload) {
      return;
    }
    clearLongPress();
    longPressTimeoutRef.current = setTimeout(() => {
      onLongPressPoint(payload);
      longPressTimeoutRef.current = null;
    }, LONG_PRESS_MS);
  };

  const handleClick = (event) => {
    if (typeof onPointClick !== "function") {
      return;
    }
    const payload = resolveInteractionPayload(chartRef.current, event, pointPayloads);
    if (payload) {
      onPointClick(payload);
    }
  };

  return (
    <div className={`chart-host ${className || ""}`.trim()} style={{ height }} data-testid={testId}>
      <Chart
        key={`${type}-${themeSignature}`}
        ref={chartRef}
        type={type}
        data={data}
        options={chartOptions}
        plugins={mergePlugins(plugins)}
        onClick={handleClick}
        onMouseDown={startLongPress}
        onMouseUp={clearLongPress}
        onMouseLeave={clearLongPress}
        onTouchStart={startLongPress}
        onTouchEnd={clearLongPress}
        onTouchMove={clearLongPress}
      />
    </div>
  );
};

export default ChartHost;
