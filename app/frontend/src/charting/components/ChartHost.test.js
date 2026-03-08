import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import ChartHost from "./ChartHost";

const mockGetElementsAtEventForMode = jest.fn();
const mockUpdate = jest.fn();

jest.mock("react-chartjs-2", () => {
  const React = require("react");
  return {
    Chart: React.forwardRef((props, ref) => {
      React.useImperativeHandle(ref, () => ({
        getElementsAtEventForMode: mockGetElementsAtEventForMode,
        update: mockUpdate,
      }));
      return (
        <button
          type="button"
          data-testid="chart-canvas"
          onMouseDown={props.onMouseDown}
          onMouseUp={props.onMouseUp}
          onMouseLeave={props.onMouseLeave}
          onTouchStart={props.onTouchStart}
          onTouchEnd={props.onTouchEnd}
          onTouchMove={props.onTouchMove}
          onClick={props.onClick}
        >
          chart
        </button>
      );
    }),
  };
});

describe("ChartHost interactions", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    mockGetElementsAtEventForMode.mockReset();
    mockUpdate.mockReset();
    mockGetElementsAtEventForMode.mockReturnValue([{ index: 1, datasetIndex: 0 }]);
  });

  afterEach(() => {
    jest.runOnlyPendingTimers();
    jest.useRealTimers();
  });

  test("fires long press callback with resolved payload", () => {
    const onLongPressPoint = jest.fn();
    render(
      <ChartHost
        type="bar"
        data={{ datasets: [] }}
        options={{}}
        pointPayloads={[{ slot: 0 }, { slot: 5 }]}
        onLongPressPoint={onLongPressPoint}
      />
    );

    fireEvent.mouseDown(screen.getByTestId("chart-canvas"));
    jest.advanceTimersByTime(560);

    expect(onLongPressPoint).toHaveBeenCalledWith(expect.objectContaining({ slot: 5, index: 1, datasetIndex: 0 }));
  });

  test("cancels long press when interaction ends early", () => {
    const onLongPressPoint = jest.fn();
    render(
      <ChartHost
        type="bar"
        data={{ datasets: [] }}
        options={{}}
        pointPayloads={[{ slot: 0 }, { slot: 5 }]}
        onLongPressPoint={onLongPressPoint}
      />
    );

    fireEvent.mouseDown(screen.getByTestId("chart-canvas"));
    jest.advanceTimersByTime(200);
    fireEvent.mouseUp(screen.getByTestId("chart-canvas"));
    jest.advanceTimersByTime(400);

    expect(onLongPressPoint).not.toHaveBeenCalled();
  });

  test("fires point click callback with resolved payload", () => {
    const onPointClick = jest.fn();
    render(
      <ChartHost
        type="matrix"
        data={{ datasets: [] }}
        options={{}}
        pointPayloads={[{ date: "2026-03-08" }, { date: "2026-03-09" }]}
        onPointClick={onPointClick}
      />
    );

    fireEvent.click(screen.getByTestId("chart-canvas"));

    expect(onPointClick).toHaveBeenCalledWith(expect.objectContaining({ date: "2026-03-09", index: 1 }));
  });
});
