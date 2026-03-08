import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import PriceChartCard from "./PriceChartCard";

jest.mock("../charting/components/BarTimeChart", () => (props) => (
  <div>
    <button type="button" data-testid="bar-chart-long-press" onMouseDown={() => props.onLongPressPoint?.({ slot: 5 })}>
      long-press
    </button>
    <button type="button" data-testid="bar-chart-touch" onTouchStart={() => props.onLongPressPoint?.({ slot: 7 })}>
      touch
    </button>
  </div>
));

describe("PriceChartCard pin forwarding", () => {
  test("pins slot forwarded from the internal chart wrapper", () => {
    const onPinSlot = jest.fn();
    render(
      <PriceChartCard
        chartData={[
          { slot: 5, spot: 1.1, extra: 0.2, final: 1.3 },
          { slot: 6, spot: 1.2, extra: 0.2, final: 1.4 },
        ]}
        title="Test"
        vtPeriods={[]}
        onPinSlot={onPinSlot}
      />
    );

    fireEvent.mouseDown(screen.getByTestId("bar-chart-long-press"));
    expect(onPinSlot).toHaveBeenCalledWith(5);
  });

  test("supports touch forwarding from the internal chart wrapper", () => {
    const onPinSlot = jest.fn();
    render(
      <PriceChartCard
        chartData={[
          { slot: 7, spot: 1.1, extra: 0.2, final: 1.3 },
          { slot: 8, spot: 1.2, extra: 0.2, final: 1.4 },
        ]}
        title="Test"
        vtPeriods={[]}
        onPinSlot={onPinSlot}
      />
    );

    fireEvent.touchStart(screen.getByTestId("bar-chart-touch"));
    expect(onPinSlot).toHaveBeenCalledWith(7);
  });
});

