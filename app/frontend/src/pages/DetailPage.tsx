import React from "react";
import { motion } from "framer-motion";
import PriceChartCard from "../components/PriceChartCard";
import CostChartCard from "../components/CostChartCard";
import ExportChartCard from "../components/ExportChartCard";
import DateNavigator from "../components/DateNavigator";
import EnergyBalanceCard from "../components/EnergyBalanceCard";
import HistoryHeatmapCard from "../components/HistoryHeatmapCard";
import BatteryProjectionCard from "../components/BatteryProjectionCard";
import DataCard from "../components/common/DataCard";
import { formatDate, formatSlotToTime } from "../utils/formatters";
import {
  getMaxEnergyBalanceAnchor,
  normalizeEnergyBalanceAnchor,
  shiftEnergyBalanceAnchor,
} from "../hooks/useDashboardData";

interface DetailPageProps {
  selectedDate: string;
  setSelectedDate: (date: string) => void;
  maxDate: string;
  selectedDateObj: Date;
  selectedDatePriceData: any[];
  selectedDatePricesLoading: boolean;
  selectedDatePricesError: any;
  config: any;
  effectiveHighlightSlot: number;
  pinnedSlot: number | null;
  setPinnedSlot: (slot: number | null) => void;
  dateSwipeHandlers: any;
  costs: any;
  costsSummary: any;
  costsError: any;
  costsLoading?: boolean;
  costsFromCache: boolean;
  costsCacheFallback: boolean;
  showDetailAnnotations: boolean;
  exportPoints: any;
  exportSummary: any;
  exportError: any;
  exportLoading?: boolean;
  exportFromCache: boolean;
  exportCacheFallback: boolean;
  energyBalancePeriod: "week" | "month" | "year";
  energyBalanceAnchor: string;
  setEnergyBalanceAnchor: React.Dispatch<React.SetStateAction<string>>;
  setEnergyBalancePeriod: (period: "week" | "month" | "year") => void;
  energyBalanceData: any;
  energyBalanceLoading: boolean;
  energyBalanceError: any;
  heatmapMonth: string;
  setHeatmapMonth: (month: string) => void;
  maxMonth: string;
  heatmapMetric: "buy" | "sell";
  setHeatmapMetric: (metric: "buy" | "sell") => void;
  heatmapData: any;
  heatmapLoading: boolean;
  heatmapError: any;
  batteryData: any;
  batteryLoading: boolean;
  batteryError: any;
  refreshBattery: () => void;
  thresholds: any;
}

const DetailPage: React.FC<DetailPageProps> = (props) => {
  const {
    selectedDate,
    setSelectedDate,
    maxDate,
    selectedDateObj,
    selectedDatePriceData,
    selectedDatePricesLoading,
    selectedDatePricesError,
    config,
    effectiveHighlightSlot,
    pinnedSlot,
    setPinnedSlot,
    dateSwipeHandlers,
    costs,
    costsSummary,
    costsError,
    costsLoading,
    costsFromCache,
    costsCacheFallback,
    showDetailAnnotations,
    exportPoints,
    exportSummary,
    exportError,
    exportLoading,
    exportFromCache,
    exportCacheFallback,
    energyBalancePeriod,
    energyBalanceAnchor,
    setEnergyBalanceAnchor,
    setEnergyBalancePeriod,
    energyBalanceData,
    energyBalanceLoading,
    energyBalanceError,
    heatmapMonth,
    setHeatmapMonth,
    maxMonth,
    heatmapMetric,
    setHeatmapMetric,
    heatmapData,
    heatmapLoading,
    heatmapError,
    batteryData,
    batteryLoading,
    batteryError,
    refreshBattery,
  } = props;

  const currentEnergyBalanceAnchor = normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor);
  const maxEnergyBalanceAnchor = getMaxEnergyBalanceAnchor(energyBalancePeriod);
  const selectedDateLabel = formatDate(selectedDateObj);

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.3 }}
    >
      <section className="section">
        <DataCard
          loading={selectedDatePricesLoading}
          error={selectedDatePricesError}
          title={`Cena elektřiny (Kč/kWh) | ${selectedDateLabel}`}
          headerActions={
            Number.isInteger(pinnedSlot) ? (
              <button onClick={() => setPinnedSlot(null)} className="ghost-button">
                Zrušit pin ({formatSlotToTime(pinnedSlot as number)})
              </button>
            ) : undefined
          }
        >
          <div className="toolbar toolbar-compact">
            <DateNavigator value={selectedDate} onChange={setSelectedDate} maxDate={maxDate} />
          </div>
          <PriceChartCard
            chartData={selectedDatePriceData}
            fallbackMessage="Data nejsou k dispozici."
            vtPeriods={config?.tarif?.vt_periods}
            highlightSlot={effectiveHighlightSlot}
            pinnedSlot={pinnedSlot}
            onPinSlot={setPinnedSlot}
            thresholds={props.thresholds}
            className=""
          />
        </DataCard>
      </section>

      <section className="section detail-grid swipe-zone" {...dateSwipeHandlers}>
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
            showAnnotations={showDetailAnnotations}
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
            showAnnotations={showDetailAnnotations}
          />
        </DataCard>
      </section>

      <section className="section detail-grid">
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
              setEnergyBalanceAnchor((prev: string) => normalizeEnergyBalanceAnchor(value as any, prev));
            }}
            data={energyBalanceData}
            loading={energyBalanceLoading}
            error={energyBalanceError}
          />
        </DataCard>

        <DataCard title="Historie - Heatmapa" loading={heatmapLoading} error={heatmapError}>
          <HistoryHeatmapCard
            month={heatmapMonth}
            setMonth={setHeatmapMonth}
            maxMonth={maxMonth}
            metric={heatmapMetric}
            setMetric={setHeatmapMetric}
            heatmapData={heatmapData}
            loading={heatmapLoading}
            error={heatmapError}
            onSelectDate={(dateValue: string) => setSelectedDate(dateValue)}
          />
        </DataCard>
      </section>

      <section className="section">
        <DataCard title="Baterie a projekce" loading={batteryLoading} error={batteryError}>
          <BatteryProjectionCard
            batteryData={batteryData}
            batteryLoading={batteryLoading}
            batteryError={batteryError}
            onRefresh={refreshBattery}
          />
        </DataCard>
      </section>
    </motion.div>
  );
};

export default DetailPage;
