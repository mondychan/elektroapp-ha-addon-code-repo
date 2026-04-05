import React, { useMemo } from "react";
import BarTimeChart from "../charting/components/BarTimeChart";
import { buildPriceChartConfig } from "../charting/builders/priceChartBuilder";
import { formatSlotToTime } from "../utils/formatters";

const PriceChartCard = ({
  chartData,
  fallbackMessage,
  vtPeriods,
  className,
  pinnedSlot,
  onPinSlot,
  thresholds,
  highlightSlot,
}) => {
  const chartConfig = useMemo(
    () =>
      buildPriceChartConfig({
        chartData,
        title: "",
        vtPeriods,
        highlightSlot,
        pinnedSlot,
        fallbackMessage,
        thresholds,
      }),
    [chartData, vtPeriods, highlightSlot, pinnedSlot, fallbackMessage, thresholds]
  );

  if (!chartData.length && !fallbackMessage) {
    return null;
  }

  return (
    <div className={className || ""}>
      {Number.isInteger(pinnedSlot) && <div className="chart-pin-note">Pin: {formatSlotToTime(pinnedSlot)}</div>}
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
