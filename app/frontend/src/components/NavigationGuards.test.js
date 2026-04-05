import React from "react";
import { fireEvent, render, screen } from "@testing-library/react";
import DateNavigator from "./DateNavigator";
import MonthNavigator from "./MonthNavigator";
import YearNavigator from "./YearNavigator";
import EnergyBalanceCard from "./EnergyBalanceCard";
import { getCurrentMonthStr, getCurrentYearStr, getTodayDateStr, shiftEnergyBalanceAnchor } from "../hooks/dashboardUtils";

describe("navigation guards", () => {
  beforeEach(() => {
    jest.useFakeTimers();
    jest.setSystemTime(new Date("2026-04-05T12:00:00+02:00"));
  });

  afterEach(() => {
    jest.useRealTimers();
  });

  test("DateNavigator disables moving to a future day", () => {
    const onChange = jest.fn();
    render(<DateNavigator value="2026-04-05" onChange={onChange} maxDate="2026-04-05" />);

    const nextButton = screen.getByRole("button", { name: "Next" });
    expect(nextButton).toBeDisabled();

    fireEvent.click(nextButton);
    expect(onChange).not.toHaveBeenCalled();
  });

  test("MonthNavigator disables moving to a future month", () => {
    const onChange = jest.fn();
    render(<MonthNavigator value="2026-04" onChange={onChange} maxMonth="2026-04" />);

    const nextButton = screen.getByRole("button", { name: "Next" });
    expect(nextButton).toBeDisabled();

    fireEvent.click(nextButton);
    expect(onChange).not.toHaveBeenCalled();
  });

  test("YearNavigator disables moving to a future year", () => {
    const onChange = jest.fn();
    render(<YearNavigator value="2026" onChange={onChange} maxYear="2026" />);

    const nextButton = screen.getByRole("button", { name: "Next" });
    expect(nextButton).toBeDisabled();

    fireEvent.click(nextButton);
    expect(onChange).not.toHaveBeenCalled();
  });

  test("EnergyBalanceCard disables the next button at the latest anchor", () => {
    render(
      <EnergyBalanceCard
        period="month"
        anchor="2026-04"
        onPrev={() => {}}
        onNext={() => {}}
        disableNext={true}
        onPeriodChange={() => {}}
        data={{ points: [] }}
        loading={false}
        error={null}
      />
    );

    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });

  test("energy balance helpers clamp future anchors to the current period", () => {
    expect(getTodayDateStr()).toBe("2026-04-05");
    expect(getCurrentMonthStr()).toBe("2026-04");
    expect(getCurrentYearStr()).toBe("2026");

    expect(shiftEnergyBalanceAnchor("week", "2026-04-05", 1)).toBe("2026-04-05");
    expect(shiftEnergyBalanceAnchor("month", "2026-04", 1)).toBe("2026-04");
    expect(shiftEnergyBalanceAnchor("year", "2026", 1)).toBe("2026");
  });
});
