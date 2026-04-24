import React from "react";
import { motion } from "framer-motion";
import PriceChartCard from "../components/PriceChartCard";
import CostChartCard from "../components/CostChartCard";
import ExportChartCard from "../components/ExportChartCard";
import MonthlySummaryCard from "../components/MonthlySummaryCard";
import BillingCard from "../components/BillingCard";
import BatteryProjectionCard from "../components/BatteryProjectionCard";
import ConfigCard from "../components/ConfigCard";
import EnergyBalanceCard from "../components/EnergyBalanceCard";
import DataCard from "../components/common/DataCard";
import AlertBanner from "../components/common/AlertBanner";
import ComparisonCard from "../components/ComparisonCard";
import SolarForecastCard from "../components/SolarForecastCard";
import { formatDate, formatSlotToTime } from "../utils/formatters";
import {
  getMaxEnergyBalanceAnchor,
  normalizeEnergyBalanceAnchor,
  shiftEnergyBalanceAnchor,
} from "../hooks/useDashboardData";

interface OverviewPageProps {
  today: Date;
  tomorrow: Date;
  todayData: any[];
  tomorrowData: any[];
  config: any;
  pinnedSlot: number | null;
  setPinnedSlot: (slot: number | null) => void;
  effectiveHighlightSlot: number;
  dateSwipeHandlers: any;
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  maxDate: string;
  costs: any;
  costsSummary: any;
  costsError: any;
  costsLoading?: boolean;
  costsFromCache: boolean;
  costsCacheFallback: boolean;
  exportPoints: any;
  exportSummary: any;
  exportError: any;
  exportLoading?: boolean;
  exportFromCache: boolean;
  exportCacheFallback: boolean;
  showMonthlySummary: boolean;
  setShowMonthlySummary: (show: boolean) => void;
  selectedMonth: string;
  setSelectedMonth: (month: string) => void;
  maxMonth: string;
  monthlySummary: any;
  monthlyTotals: any;
  monthlyError: any;
  monthlyLoading?: boolean;
  showBilling: boolean;
  setShowBilling: (show: boolean) => void;
  billingMode: "month" | "year";
  setBillingMode: (mode: "month" | "year") => void;
  billingMonth: string;
  setBillingMonth: (month: string) => void;
  billingYear: string;
  setBillingYear: (year: string) => void;
  maxBillingMonth: string;
  maxBillingYear: string;
  billingData: any;
  billingLoading: boolean;
  billingError: any;
  showBatteryPanel: boolean;
  setShowBatteryPanel: (show: boolean) => void;
  batteryData: any;
  batteryLoading: boolean;
  batteryError: any;
  refreshBattery: () => void;
  energyBalancePeriod: string;
  energyBalanceAnchor: string;
  setEnergyBalanceAnchor: React.Dispatch<React.SetStateAction<string>>;
  setEnergyBalancePeriod: (period: "week" | "month" | "year") => void;
  energyBalanceData: any;
  energyBalanceLoading: boolean;
  energyBalanceError: any;
  showConfig: boolean;
  setShowConfig: (show: boolean) => void;
  configRows: any[];
  cacheRows: any[];
  consumptionCacheRows: any[];
  exportCacheRows: any[];
  cacheStatus: any;
  showFeesHistory: boolean;
  setShowFeesHistory: React.Dispatch<React.SetStateAction<boolean>>;
  feesHistory: any;
  feesHistoryLoading: boolean;
  feesHistoryError: any;
  saveFeesHistory: (history: any) => void;
  priceProviderLabel: string;
  priceProviderUrl: string;
  refreshPrices: () => void;
  pricesRefreshLoading: boolean;
  pricesRefreshMessage: string | null;
  pricesRefreshError: string | null;
  pricesLoading?: boolean;
  alerts: any;
  comparison: any;
  comparisonLoading: boolean;
  solarForecast: any;
  solarForecastLoading: boolean;
  defaultFeesValues: any;
  thresholds: any;
}

const OverviewPage: React.FC<OverviewPageProps> = (props) => {
  const {
    today,
    tomorrow,
    todayData,
    tomorrowData,
    config,
    pinnedSlot,
    setPinnedSlot,
    effectiveHighlightSlot,
    dateSwipeHandlers,
    selectedDate,
    setSelectedDate,
    maxDate,
    costs,
    costsSummary,
    costsError,
    costsLoading,
    costsFromCache,
    costsCacheFallback,
    exportPoints,
    exportSummary,
    exportError,
    exportLoading,
    exportFromCache,
    exportCacheFallback,
    showMonthlySummary,
    setShowMonthlySummary,
    selectedMonth,
    setSelectedMonth,
    maxMonth,
    monthlySummary,
    monthlyTotals,
    monthlyError,
    monthlyLoading,
    showBilling,
    setShowBilling,
    billingMode,
    setBillingMode,
    billingMonth,
    setBillingMonth,
    billingYear,
    setBillingYear,
    maxBillingMonth,
    maxBillingYear,
    billingData,
    billingLoading,
    billingError,
    showBatteryPanel,
    setShowBatteryPanel,
    batteryData,
    batteryLoading,
    batteryError,
    refreshBattery,
    energyBalancePeriod,
    energyBalanceAnchor,
    setEnergyBalanceAnchor,
    setEnergyBalancePeriod,
    energyBalanceData,
    energyBalanceLoading,
    energyBalanceError,
    showConfig,
    setShowConfig,
    configRows,
    cacheRows,
    consumptionCacheRows,
    exportCacheRows,
    cacheStatus,
    showFeesHistory,
    setShowFeesHistory,
    feesHistory,
    feesHistoryLoading,
    feesHistoryError,
    saveFeesHistory,
    priceProviderLabel,
    priceProviderUrl,
    refreshPrices,
    pricesRefreshLoading,
    pricesRefreshMessage,
    pricesRefreshError,
    pricesLoading,
    alerts,
    comparison,
    comparisonLoading,
    solarForecast,
    solarForecastLoading,
  } = props;

  const selectedDateLabel = formatDate(new Date(`${selectedDate}T00:00:00`));
  const currentEnergyBalanceAnchor = normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor);
  const maxEnergyBalanceAnchor = getMaxEnergyBalanceAnchor(energyBalancePeriod);

  const [showStats, setShowStats] = React.useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 20 }}
      transition={{ duration: 0.3 }}
    >
      <AlertBanner alerts={alerts} />

      {solarForecast?.enabled && (
        <DataCard title="Solární předpověď" loading={solarForecastLoading}>
          <SolarForecastCard solarForecast={solarForecast} loading={solarForecastLoading} />
        </DataCard>
      )}

      <section className="section">
        <DataCard
          loading={pricesLoading}
          title={`Cena elektřiny (Kč/kWh) | Dnes (${formatDate(today)})`}
          headerActions={
            Number.isInteger(pinnedSlot) ? (
              <button onClick={() => setPinnedSlot(null)} className="ghost-button">
                Zrušit pin ({formatSlotToTime(pinnedSlot as number)})
              </button>
            ) : undefined
          }
        >
          <PriceChartCard
            chartData={todayData}
            fallbackMessage="Načítám data..."
            vtPeriods={config?.tarif?.vt_periods}
            highlightSlot={effectiveHighlightSlot}
            pinnedSlot={pinnedSlot}
            onPinSlot={setPinnedSlot}
            className=""
            thresholds={alerts}
          />
        </DataCard>

        {tomorrowData?.length > 0 && (
          <DataCard
            loading={pricesLoading}
            title={`Cena elektřiny (Kč/kWh) | Zítra (${formatDate(tomorrow)})`}
          >
            <PriceChartCard
              chartData={tomorrowData}
              fallbackMessage="Data pro zítřek zatím nejsou k dispozici."
              vtPeriods={config?.tarif?.vt_periods}
              highlightSlot={-1}
              pinnedSlot={null}
              onPinSlot={() => {}}
              className=""
              thresholds={alerts}
            />
          </DataCard>
        )}
      </section>

      <section className="section swipe-zone" {...dateSwipeHandlers}>
        <DataCard title={`Spotřeba a náklady | ${selectedDateLabel}`} loading={costsLoading} error={costsError}>
          <CostChartCard
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            maxDate={maxDate}
            costs={costs}
            costsSummary={costsSummary}
            costsError={costsError}
            costsFromCache={costsFromCache}
            costsCacheFallback={costsCacheFallback}
            showAnnotations={false}
          />
        </DataCard>

        <DataCard title={`Prodej a export | ${selectedDateLabel}`} loading={exportLoading} error={exportError}>
          <ExportChartCard
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            maxDate={maxDate}
            exportPoints={exportPoints}
            exportSummary={exportSummary}
            exportError={exportError}
            exportFromCache={exportFromCache}
            exportCacheFallback={exportCacheFallback}
            showAnnotations={false}
          />
        </DataCard>
      </section>

      <div style={{ display: "flex", flexDirection: "column", gap: "10px", marginTop: "12px" }}>
        <button onClick={() => setShowMonthlySummary(!showMonthlySummary)} className="ghost-button">
          {showMonthlySummary ? "Skrýt souhrn" : "Zobrazit souhrn"}
        </button>

        {showMonthlySummary && (
          <section className="section">
            <DataCard title="Měsíční souhrn" loading={monthlyLoading} error={monthlyError}>
              <MonthlySummaryCard
                selectedMonth={selectedMonth}
                setSelectedMonth={setSelectedMonth}
                maxMonth={maxMonth}
                monthlySummary={monthlySummary}
                monthlyTotals={monthlyTotals}
                monthlyError={monthlyError}
              />
            </DataCard>
          </section>
        )}

        <button onClick={() => setShowBilling(!showBilling)} className="ghost-button">
          {showBilling ? "Skrýt vyúčtování" : "Odhad vyúčtování"}
        </button>

        {showBilling && (
          <DataCard title="Odhad vyúčtování" loading={billingLoading} error={billingError}>
            <BillingCard
              billingMode={billingMode}
              setBillingMode={setBillingMode}
              billingMonth={billingMonth}
              setBillingMonth={setBillingMonth}
              billingYear={billingYear}
              setBillingYear={setBillingYear}
              maxMonth={maxBillingMonth}
              maxYear={maxBillingYear}
              billingData={billingData}
              billingLoading={billingLoading}
              billingError={billingError}
            />
          </DataCard>
        )}

        <button onClick={() => setShowBatteryPanel(!showBatteryPanel)} className="ghost-button">
          {showBatteryPanel ? "Skrýt baterii a projekci" : "Baterie a projekce"}
        </button>

        {showBatteryPanel && (
          <DataCard title="Baterie a projekce" loading={batteryLoading} error={batteryError}>
            <BatteryProjectionCard
              batteryData={batteryData}
              batteryLoading={batteryLoading}
              batteryError={batteryError}
              onRefresh={refreshBattery}
            />
          </DataCard>
        )}

        <button onClick={() => setShowStats(!showStats)} className="ghost-button">
          {showStats ? "Skrýt statistiky" : "Zobrazit statistiky"}
        </button>

        {showStats && (
          <section className="section">
            <DataCard title="Srovnání výkonu" loading={comparisonLoading}>
              <ComparisonCard comparison={comparison} loading={comparisonLoading} />
            </DataCard>

            <DataCard title="Energetická bilance" loading={energyBalanceLoading} error={energyBalanceError}>
              <EnergyBalanceCard
                period={energyBalancePeriod}
                anchor={currentEnergyBalanceAnchor}
                onPrev={() =>
                  setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, -1))
                }
                onNext={() =>
                  setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, 1))
                }
                disableNext={currentEnergyBalanceAnchor === maxEnergyBalanceAnchor}
                onPeriodChange={(value: any) => {
                  setEnergyBalancePeriod(value as any);
                  setEnergyBalanceAnchor((prev: string) => normalizeEnergyBalanceAnchor(value, prev));
                }}
                data={energyBalanceData}
                loading={energyBalanceLoading}
                error={energyBalanceError}
              />
            </DataCard>
          </section>
        )}

        <button onClick={() => setShowConfig(!showConfig)} className="ghost-button">
          {showConfig ? "Skrýt konfiguraci" : "Zobrazit konfiguraci"}
        </button>

        {showConfig && (
          <DataCard title="Konfigurace systému">
            <ConfigCard
              configRows={configRows}
              cacheRows={cacheRows}
              consumptionCacheRows={consumptionCacheRows}
              exportCacheRows={exportCacheRows}
              cacheStatus={cacheStatus}
              showFeesHistory={showFeesHistory}
              onToggleFeesHistory={() => setShowFeesHistory((prev: boolean) => !prev)}
              feesHistory={feesHistory}
              feesHistoryLoading={feesHistoryLoading}
              feesHistoryError={feesHistoryError}
              onSaveFeesHistory={saveFeesHistory}
              defaultFeesValues={props.defaultFeesValues}
              priceProviderLabel={priceProviderLabel}
              priceProviderUrl={priceProviderUrl}
              onRefreshPrices={refreshPrices}
              refreshingPrices={pricesRefreshLoading}
              pricesRefreshMessage={pricesRefreshMessage}
              pricesRefreshError={pricesRefreshError}
            />
          </DataCard>
        )}
      </div>
    </motion.div>
  );
};

export default OverviewPage;
