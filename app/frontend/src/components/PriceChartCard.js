import React, { useMemo } from "react";
import BarTimeChart from "../charting/components/BarTimeChart";
import { buildPriceChartConfig } from "../charting/builders/priceChartBuilder";
import { formatSlotToTime } from "../utils/formatters";

const PriceChartCard = ({
  chartData,
  title,
  fallbackMessage,
  vtPeriods,
  className,
  highlightSlot,
  pinnedSlot,
  onPinSlot,
}) => {
  const chartConfig = useMemo(
    () =>
      buildPriceChartConfig({
        chartData,
        title,
        vtPeriods,
        highlightSlot,
        pinnedSlot,
        fallbackMessage,
      }),
    [chartData, title, vtPeriods, highlightSlot, pinnedSlot, fallbackMessage]
  );

  if (!chartData.length && !fallbackMessage) {
    return null;
  }

  return (
    <div className={`card ${className || ""}`.trim()}>
      <div className="card-header">
        <h3>{title}</h3>
        {Number.isInteger(pinnedSlot) && <div className="chart-pin-note">Pin: {formatSlotToTime(pinnedSlot)}</div>}
      </div>
      {!chartData.length ? (
        <div className="config-muted">{fallbackMessage}</div>
      ) : (
        <BarTimeChart
          height={400}
          animationProfile="progressive"
          {...chartConfig}
          onLongPressPoint={(payload) => {
            if (typeof onPinSlot === "function" && Number.isInteger(payload?.slot)) {
              onPinSlot(payload.slot);
            }
          }}
        />
      )}
    </div>
  );
};

export default PriceChartCard;
