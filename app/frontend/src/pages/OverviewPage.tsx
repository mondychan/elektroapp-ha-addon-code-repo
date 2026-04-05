import React from "react";
import { motion } from "framer-motion";
import PriceChartCard from "../components/PriceChartCard";
import CostChartCard from "../components/CostChartCard";
import ExportChartCard from "../components/ExportChartCard";
import MonthlySummaryCard from "../components/MonthlySummaryCard";
import BillingCard from "../components/BillingCard";
import BatteryProjectionCard from "../components/BatteryProjectionCard";
import PlannerCard from "../components/PlannerCard";
import ConfigCard from "../components/ConfigCard";
import EnergyBalanceCard from "../components/EnergyBalanceCard";
import DataCard from "../components/common/DataCard";
import AlertBanner from "../components/common/AlertBanner";
import ComparisonCard from "../components/ComparisonCard";
import SolarForecastCard from "../components/SolarForecastCard";
import { formatDate, formatSlotToTime } from "../utils/formatters";
import { normalizeEnergyBalanceAnchor, shiftEnergyBalanceAnchor } from "../hooks/useDashboardData";

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
  monthSwipeHandlers: any;
  selectedMonth: string;
  setSelectedMonth: (month: string) => void;
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
  showPlanner: boolean;
  handlePlannerToggle: () => void;
  plannerDuration: string;
  setPlannerDuration: (dur: string) => void;
  handleLoadPlanner: (dur?: string) => Promise<void>;
  finalPlannerError: any;
  plannerLoading: boolean;
  plannerNote: string | null;
  plannerResults: any;
  showConfig: boolean;
  setShowConfig: (show: boolean) => void;
  configRows: any[];
  cacheRows: any[];
  consumptionCacheRows: any[];
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
    monthSwipeHandlers,
    selectedMonth,
    setSelectedMonth,
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
    showPlanner,
    handlePlannerToggle,
    plannerDuration,
    setPlannerDuration,
    handleLoadPlanner,
    finalPlannerError,
    plannerLoading,
    plannerNote,
    plannerResults,
    showConfig,
    setShowConfig,
    configRows,
    cacheRows,
    consumptionCacheRows,
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

      <DataCard title="Srovnání výkonu" loading={comparisonLoading}>
        <ComparisonCard comparison={comparison} loading={comparisonLoading} />
      </DataCard>

      <section className="section">
        <div className="section-heading">
          <h2>Cena elektřiny (Kč/kWh)</h2>
          {Number.isInteger(pinnedSlot) && (
            <button onClick={() => setPinnedSlot(null)} className="ghost-button">
              Zrušit pin ({formatSlotToTime(pinnedSlot as number)})
            </button>
          )}
        </div>
        <div className="gesture-hint">Swipe v grafech mění den, stažení shora obnoví ceny, dlouhý stisk sloupce připne hodinu.</div>
        
        <DataCard loading={pricesLoading} title={`Dnes (${formatDate(today)})`}>
          <PriceChartCard
            chartData={todayData}
            title=""
            fallbackMessage="Načítám data..."
            vtPeriods={config?.tarif?.vt_periods}
            highlightSlot={effectiveHighlightSlot}
            pinnedSlot={pinnedSlot}
            onPinSlot={setPinnedSlot}
            className=""
            thresholds={alerts}
          />
        </DataCard>

        <DataCard loading={pricesLoading} title={`Zítra (${formatDate(tomorrow)})`} className="card-spaced">
          <PriceChartCard
            chartData={tomorrowData}
            title=""
            fallbackMessage="Data pro následující den zatím nebyla publikována"
            vtPeriods={config?.tarif?.vt_periods}
            highlightSlot={-1}
            pinnedSlot={null}
            onPinSlot={() => {}}
            className=""
            thresholds={alerts}
          />
        </DataCard>
      </section>

      <section className="section swipe-zone" {...dateSwipeHandlers}>
        <DataCard title="Dnešní náklady" loading={costsLoading} error={costsError}>
          <CostChartCard
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            costs={costs}
            costsSummary={costsSummary}
            costsError={costsError}
            costsFromCache={costsFromCache}
            costsCacheFallback={costsCacheFallback}
            showAnnotations={false}
          />
        </DataCard>
        
        <DataCard title="Dnešní export" loading={exportLoading} error={exportError}>
          <ExportChartCard
            selectedDate={selectedDate}
            setSelectedDate={setSelectedDate}
            exportPoints={exportPoints}
            exportSummary={exportSummary}
            exportError={exportError}
            exportFromCache={exportFromCache}
            exportCacheFallback={exportCacheFallback}
            showAnnotations={false}
          />
        </DataCard>
      </section>

      <button onClick={() => setShowMonthlySummary(!showMonthlySummary)} className="ghost-button">
        {showMonthlySummary ? "Skrýt souhrn" : "Zobrazit souhrn"}
      </button>

      {showMonthlySummary && (
        <section className="section swipe-zone" {...monthSwipeHandlers}>
          <DataCard title="Měsíční souhrn" loading={monthlyLoading} error={monthlyError}>
            <MonthlySummaryCard
              selectedMonth={selectedMonth}
              setSelectedMonth={setSelectedMonth}
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

      <section className="section">
        <DataCard title="Energetická bilance" loading={energyBalanceLoading} error={energyBalanceError}>
          <EnergyBalanceCard
            period={energyBalancePeriod}
            anchor={normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor)}
            onPrev={() =>
              setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, -1))
            }
            onNext={() =>
              setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, 1))
            }
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

      <button onClick={handlePlannerToggle} className="ghost-button">
        {showPlanner ? "Skrýt plánovač" : "Zobrazit plánovač"}
      </button>

      {showPlanner && (
        <DataCard title="Plánovač" loading={plannerLoading}>
          <PlannerCard
            plannerDuration={plannerDuration}
            setPlannerDuration={setPlannerDuration}
            loadPlanner={handleLoadPlanner}
            plannerError={finalPlannerError}
            plannerLoading={plannerLoading}
            plannerNote={plannerNote}
            plannerResults={plannerResults}
          />
        </DataCard>
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
    </motion.div>
  );
};

export default OverviewPage;
