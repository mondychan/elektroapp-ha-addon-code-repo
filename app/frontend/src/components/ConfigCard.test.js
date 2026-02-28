import { fireEvent, render, screen } from "@testing-library/react";
import ConfigCard from "./ConfigCard";

describe("ConfigCard", () => {
  test("renders API refresh error and disabled refresh button", () => {
    const onRefreshPrices = jest.fn();

    render(
      <ConfigCard
        configRows={[]}
        cacheRows={[]}
        consumptionCacheRows={[]}
        cacheStatus={{ prices: null, consumption: null }}
        showFeesHistory={false}
        onToggleFeesHistory={() => {}}
        feesHistory={[]}
        feesHistoryLoading={false}
        feesHistoryError={null}
        onSaveFeesHistory={() => {}}
        defaultFeesValues={{}}
        priceProviderLabel="spotovaelektrina.cz"
        priceProviderUrl="https://spotovaelektrina.cz/"
        onRefreshPrices={onRefreshPrices}
        refreshingPrices={true}
        pricesRefreshMessage={null}
        pricesRefreshError="Obnoveni cen selhalo."
      />
    );

    expect(screen.getByText("Obnoveni cen selhalo.")).toBeInTheDocument();
    expect(screen.getByText("Cache cen nejsou k dispozici.")).toBeInTheDocument();
    expect(screen.getByText("Cache spotreby nejsou k dispozici.")).toBeInTheDocument();

    const refreshButton = screen.getByRole("button", { name: "Obnovuji..." });
    expect(refreshButton).toBeDisabled();
    fireEvent.click(refreshButton);
    expect(onRefreshPrices).not.toHaveBeenCalled();
  });
});
