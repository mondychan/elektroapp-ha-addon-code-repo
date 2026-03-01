import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import PriceChartCard from "./PriceChartCard";

jest.mock("recharts", () => {
  const passthrough = (name) => ({ children }) => <div data-testid={name}>{children}</div>;

  const Bar = ({ dataKey, onMouseDown, onMouseUp, onMouseLeave, onTouchStart, onTouchEnd, onTouchMove, children }) => (
    <button
      type="button"
      data-testid={`bar-${dataKey}`}
      onMouseDown={() => onMouseDown?.({ payload: { slot: 5 }, slot: 5 })}
      onMouseUp={() => onMouseUp?.()}
      onMouseLeave={() => onMouseLeave?.()}
      onTouchStart={() => onTouchStart?.({ payload: { slot: 7 }, slot: 7 })}
      onTouchEnd={() => onTouchEnd?.()}
      onTouchMove={() => onTouchMove?.()}
    >
      {children}
    </button>
  );

  const Cell = () => <span data-testid="cell" />;

  return {
    Bar,
    Cell,
    BarChart: passthrough("BarChart"),
    XAxis: passthrough("XAxis"),
    YAxis: passthrough("YAxis"),
    Tooltip: passthrough("Tooltip"),
    CartesianGrid: passthrough("CartesianGrid"),
    ResponsiveContainer: passthrough("ResponsiveContainer"),
    ReferenceLine: passthrough("ReferenceLine"),
    ReferenceArea: passthrough("ReferenceArea"),
  };
});

jest.mock("d3-scale", () => ({
  scaleLinear: () => ({
    domain: () => ({
      range: () => () => "#ff0000",
    }),
  }),
}));

describe("PriceChartCard long-press pinning", () => {
  beforeEach(() => {
    jest.useFakeTimers();
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  test("pins slot on long mouse press", () => {
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

    fireEvent.mouseDown(screen.getByTestId("bar-spot"));
    jest.advanceTimersByTime(560);

    expect(onPinSlot).toHaveBeenCalledWith(5);
    expect(onPinSlot).toHaveBeenCalledTimes(1);
  });

  test("does not pin slot when press ends early", () => {
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

    fireEvent.mouseDown(screen.getByTestId("bar-extra"));
    jest.advanceTimersByTime(250);
    fireEvent.mouseUp(screen.getByTestId("bar-extra"));
    jest.advanceTimersByTime(400);

    expect(onPinSlot).not.toHaveBeenCalled();
  });
});
