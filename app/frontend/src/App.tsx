import React, { Suspense, lazy, useCallback, useEffect, useMemo, useState } from "react";
import ModernOverviewPage from "./pages/ModernOverviewPage";
import AppShell, { PageMode } from "./components/modern/AppShell";
import SectionCard from "./components/modern/SectionCard";
import MonthlySummaryCard from "./components/MonthlySummaryCard";
import EnergyBalanceCard from "./components/EnergyBalanceCard";
import PriceChartCard from "./components/PriceChartCard";

import { formatSlotToTime, formatBytes } from "./utils/formatters";
import { useLocalStorageState } from "./hooks/useLocalStorageState";
import { usePageVisibility } from "./hooks/usePageVisibility";
import { useCurrentSlot } from "./hooks/useCurrentSlot";
import { usePullToRefresh } from "./hooks/usePullToRefresh";
import { useSwipeGesture } from "./hooks/useSwipeGesture";
import { useDashboardData } from "./hooks/useDashboardData";
import {
  clampDateValue,
  getCurrentMonthStr,
  getCurrentYearStr,
  getTodayDateStr,
} from "./hooks/dashboardUtils";
import { PriceItem } from "./types/elektroapp";
import {
  normalizeEnergyBalanceAnchor,
  shiftEnergyBalanceAnchor,
  getMaxEnergyBalanceAnchor,
} from "./hooks/useDashboardData";

const DetailPage = lazy(() => import("./pages/DetailPage"));
const RecommendationsPage = lazy(() => import("./pages/RecommendationsPage"));
const PndPage = lazy(() => import("./pages/PndPage"));
const HpPage = lazy(() => import("./pages/HpPage"));
const DataCard = lazy(() => import("./components/common/DataCard"));
const SolarForecastCard = lazy(() => import("./components/SolarForecastCard"));
const BillingCard = lazy(() => import("./components/BillingCard"));
const BatteryProjectionCard = lazy(() => import("./components/BatteryProjectionCard"));
const ComparisonCard = lazy(() => import("./components/ComparisonCard"));
const ConfigCard = lazy(() => import("./components/ConfigCard"));

const LazyPageFallback = () => (
  <div className="modern-lazy-fallback" role="status" aria-live="polite">
    Načítám sekci...
  </div>
);

const shiftDateValue = (value: string, dayDelta: number) => {
  const dt = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return value;
  dt.setDate(dt.getDate() + dayDelta);
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const App: React.FC = () => {
  const todayDateStr = getTodayDateStr();
  const tomorrowDateStr = shiftDateValue(todayDateStr, 1);
  const currentMonthStr = getCurrentMonthStr();
  const currentYearStr = getCurrentYearStr();
  const [pageMode, setPageMode] = useState<PageMode>("overview");
  const [showFeesHistory, setShowFeesHistory] = useState(false);

  const [theme, setTheme] = useLocalStorageState<"light" | "dark" | "system">("theme", "dark");
  const [plannerDuration, setPlannerDuration] = useLocalStorageState("plannerDuration", "120");

  const [plannerValidationError, setPlannerValidationError] = useState<string | null>(null);
  const [pinnedSlot, setPinnedSlot] = useState<number | null>(null);

  const [selectedDate, setSelectedDate] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  });
  const [selectedMonth, setSelectedMonth] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  });
  const [billingMode, setBillingMode] = useState<"month" | "year">("month");
  const [billingMonth, setBillingMonth] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  });
  const [billingYear, setBillingYear] = useState(() => String(new Date().getFullYear()));
  const [energyBalancePeriod, setEnergyBalancePeriod] = useState<"week" | "month" | "year">("week");
  const [energyBalanceAnchor, setEnergyBalanceAnchor] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    const d = String(today.getDate()).padStart(2, "0");
    return `${y}-${m}-${d}`;
  });
  const [heatmapMetric, setHeatmapMetric] = useState<"buy" | "sell">("buy");
  const [heatmapMonth, setHeatmapMonth] = useState(() => {
    const today = new Date();
    const y = today.getFullYear();
    const m = String(today.getMonth() + 1).padStart(2, "0");
    return `${y}-${m}`;
  });

  const isPageVisible = usePageVisibility();
  const currentSlot = useCurrentSlot();

  useEffect(() => {
    const mediaQuery = window.matchMedia("(prefers-color-scheme: dark)");
    const handleChange = () => {
      if (theme === "system" || !theme) {
        document.body.dataset.theme = mediaQuery.matches ? "dark" : "light";
      }
    };
    mediaQuery.addEventListener("change", handleChange);
    document.body.dataset.theme = theme === "system" || !theme ? (mediaQuery.matches ? "dark" : "light") : theme;
    return () => mediaQuery.removeEventListener("change", handleChange);
  }, [theme]);

  useEffect(() => {
    document.body.dataset.uiLayout = "modern";
  }, []);

  const dashboard = useDashboardData({
    selectedDate,
    selectedMonth,
    showConfig: pageMode === "settings",
    showFeesHistory: showFeesHistory || pageMode === "settings",
    showBilling: pageMode === "monthly",
    billingMode,
    billingMonth,
    billingYear,
    pageMode,
    energyBalancePeriod,
    energyBalanceAnchor,
    heatmapMonth,
    heatmapMetric,
    autoRefreshEnabled: true,
    isPageVisible,
  });

  const { config, batteryData, refreshPrices, refreshConfig } = dashboard;

  const activePriceProvider = config?.price_provider === "ote" ? "ote" : "spotovaelektrina";
  const priceProviderLabel = activePriceProvider === "ote" ? "OTE (ote-cr.cz + CNB)" : "spotovaelektrina.cz";
  const priceProviderUrl = activePriceProvider === "ote" ? "https://www.ote-cr.cz/" : "https://spotovaelektrina.cz/";
  const effectiveHighlightSlot = Number.isInteger(pinnedSlot) ? pinnedSlot : currentSlot;

  const dateSwipeHandlers = useSwipeGesture({
    onSwipeLeft: () => setSelectedDate((prev) => clampDateValue(shiftDateValue(prev, 1), todayDateStr)),
    onSwipeRight: () => setSelectedDate((prev) => shiftDateValue(prev, -1)),
  });

  const { pullDistance, isRefreshing: pullRefreshing, isArmed: pullArmed, gestureHandlers: pullHandlers } = usePullToRefresh({
    enabled: true,
    onRefresh: refreshPrices,
  });

  const handleLoadPlanner = useCallback(async (durationOverride: number | string = plannerDuration): Promise<void> => {
    const parsed = typeof durationOverride === "number" ? durationOverride : Number.parseInt(durationOverride, 10);
    if (!parsed || parsed <= 0 || parsed > 360) {
      setPlannerValidationError("Okna musi byt 1-360 minut.");
      return;
    }
    setPlannerDuration(String(parsed));
    setPlannerValidationError(null);
    try {
      await (dashboard as any).loadPlanner(parsed);
    } catch {}
  }, [dashboard, plannerDuration, setPlannerDuration]);

  const dphMultiplier = useMemo(() => {
    const dphVal = config?.dph != null ? Number(config.dph) : 21;
    return 1 + (Number.isNaN(dphVal) ? 21 : Math.max(0, dphVal)) / 100;
  }, [config?.dph]);

  const mapPrices = useCallback((arr: any[]): PriceItem[] => arr.map((p, i) => {
    const spotWithDph = p.spot * dphMultiplier;
    return { slot: i, time: formatSlotToTime(i), spot: spotWithDph, extra: p.final - spotWithDph, final: p.final, rawSpot: p.spot };
  }), [dphMultiplier]);

  const todayData = useMemo(() => mapPrices(dashboard.prices.slice(0, 96)), [dashboard.prices, mapPrices]);
  const tomorrowData = useMemo(() => mapPrices(dashboard.prices.slice(96, 192)), [dashboard.prices, mapPrices]);
  const selectedDatePriceData = useMemo(() => mapPrices(dashboard.selectedDatePrices), [dashboard.selectedDatePrices, mapPrices]);

  const configRows = useMemo(() => {
    if (!config) return [];
    const f = (v: any) => v ?? "-";
    const dphVal = config.dph ?? 0;
    const mDph = 1 + dphVal / 100;

    const row = (label: string, val: any, unit = "") => ({
      label,
      value: val != null && val !== "" ? `${val} (${(Number(val) * mDph).toFixed(2)} s DPH)` : "-",
      unit,
    });

    return [
      { label: "DPH", value: String(dphVal), unit: "%" },
      { label: "Zdroj cen", value: priceProviderLabel, unit: "" },
      row("Sluzba obchodu", config.poplatky?.komodita_sluzba, "Kc/kWh"),
      row("OZE", config.poplatky?.oze, "Kc/kWh"),
      row("Dan", config.poplatky?.dan, "Kc/kWh"),
      row("Systemove sluzby", config.poplatky?.systemove_sluzby, "Kc/kWh"),
      {
        label: "Distribuce NT/VT",
        value: `${f(config.poplatky?.distribuce?.NT)} / ${f(config.poplatky?.distribuce?.VT)}`,
        unit: "Kc/kWh",
      },
      row("Nesitova infrastruktura", config.fixni?.mesicni?.provoz_nesitove_infrastruktury, "Kc/mesic"),
      row("Staly plat", config.fixni?.denni?.staly_plat, "Kc/den"),
      row("Jistic", config.fixni?.mesicni?.jistic, "Kc/mesic"),
      row("Koeficient snizeni (prodej)", config.prodej?.koeficient_snizeni_ceny, "Kc/MWh"),
      { label: "Import entity_id", value: config.influxdb?.entity_id || "-", unit: "" },
      { label: "Export entity_id", value: config.influxdb?.export_entity_id || "-", unit: "" },
      { label: "Baterie (SoC entity_id)", value: config.battery?.soc_entity_id || "-", unit: "" },
      {
        label: "Baterie kapacita (usable)",
        value: config.battery?.usable_capacity_kwh ?? "-",
        unit: config.battery?.usable_capacity_kwh != null ? "kWh" : "",
      },
      {
        label: "Baterie rezerva",
        value: config.battery?.reserve_soc_percent ?? "-",
        unit: config.battery?.reserve_soc_percent != null ? "%" : "",
      },
      { label: "House load entity_id", value: config.energy?.house_load_power_entity_id || "-", unit: "" },
      { label: "Grid import entity_id", value: config.energy?.grid_import_power_entity_id || "-", unit: "" },
      { label: "Grid export entity_id", value: config.energy?.grid_export_power_entity_id || "-", unit: "" },
      { label: "PV total entity_id", value: config.energy?.pv_power_total_entity_id || "-", unit: "" },
      { label: "Forecast power_now entity_id", value: config.forecast_solar?.power_now_entity_id || "-", unit: "" },
    ];
  }, [config, priceProviderLabel]);

  const defaultFeesValues = useMemo(() => {
    if (!config) return null;
    return {
      dph: config.dph ?? "",
      poplatky: {
        komodita_sluzba: config.poplatky?.komodita_sluzba ?? "",
        oze: config.poplatky?.oze ?? "",
        dan: config.poplatky?.dan ?? "",
        systemove_sluzby: config.poplatky?.systemove_sluzby ?? "",
        distribuce: {
          NT: config.poplatky?.distribuce?.NT ?? "",
          VT: config.poplatky?.distribuce?.VT ?? "",
        },
      },
      fixni: {
        denni: {
          staly_plat: config.fixni?.denni?.staly_plat ?? "",
        },
        mesicni: {
          provoz_nesitove_infrastruktury: config.fixni?.mesicni?.provoz_nesitove_infrastruktury ?? "",
          jistic: config.fixni?.mesicni?.jistic ?? "",
        },
      },
      prodej: {
        koeficient_snizeni_ceny: config.prodej?.koeficient_snizeni_ceny ?? "",
      },
    };
  }, [config]);

  const buildCacheRows = useCallback((status: any) => {
    if (!status) return [];
    return [
      { label: "Cache dny", value: `${status.count ?? 0} dni` },
      { label: "Cache nejnovejsi", value: status.latest || "-" },
      { label: "Cache velikost", value: formatBytes(status.size_bytes) },
      { label: "Cache cesta", value: status.dir || "-", valueWrap: true },
    ];
  }, []);

  const cacheRows = useMemo(() => buildCacheRows(dashboard.cacheStatus?.prices), [buildCacheRows, dashboard.cacheStatus]);
  const consumptionCacheRows = useMemo(
    () => buildCacheRows(dashboard.cacheStatus?.consumption),
    [buildCacheRows, dashboard.cacheStatus]
  );
  const exportCacheRows = useMemo(
    () => buildCacheRows(dashboard.cacheStatus?.export),
    [buildCacheRows, dashboard.cacheStatus]
  );

  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  const currentEnergyBalanceAnchor = normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor);
  const maxEnergyBalanceAnchor = getMaxEnergyBalanceAnchor(energyBalancePeriod);

  const renderModernContent = () => {
    if (pageMode === "overview") {
      return (
        <ModernOverviewPage
          {...dashboard}
          today={today}
          tomorrow={tomorrow}
          todayData={todayData}
          tomorrowData={tomorrowData}
          pinnedSlot={pinnedSlot}
          setPinnedSlot={setPinnedSlot}
          effectiveHighlightSlot={effectiveHighlightSlot}
          selectedMonth={selectedMonth}
          setSelectedMonth={setSelectedMonth}
          maxMonth={currentMonthStr}
          energyBalancePeriod={energyBalancePeriod}
          energyBalanceAnchor={energyBalanceAnchor}
          setEnergyBalanceAnchor={setEnergyBalanceAnchor}
          setEnergyBalancePeriod={setEnergyBalancePeriod}
          refreshBattery={dashboard.refreshBattery}
          setPageMode={setPageMode}
        />
      );
    }

    if (pageMode === "costs") {
      return (
        <DetailPage
          {...dashboard}
          selectedDate={selectedDate}
          setSelectedDate={setSelectedDate}
          selectedDateObj={new Date(`${selectedDate}T00:00:00`)}
          selectedDatePriceData={selectedDatePriceData}
          selectedDatePricesLoading={dashboard.selectedDatePricesLoading}
          selectedDatePricesError={dashboard.selectedDatePricesError}
          maxDate={tomorrowDateStr}
          maxMonth={currentMonthStr}
          effectiveHighlightSlot={effectiveHighlightSlot as any}
          pinnedSlot={pinnedSlot as any}
          setPinnedSlot={setPinnedSlot}
          dateSwipeHandlers={dateSwipeHandlers}
          showDetailAnnotations={true}
          energyBalancePeriod={energyBalancePeriod}
          energyBalanceAnchor={energyBalanceAnchor}
          setEnergyBalanceAnchor={setEnergyBalanceAnchor}
          setEnergyBalancePeriod={setEnergyBalancePeriod}
          refreshBattery={dashboard.refreshBattery}
          heatmapMonth={heatmapMonth}
          setHeatmapMonth={setHeatmapMonth}
          heatmapMetric={heatmapMetric}
          setHeatmapMetric={setHeatmapMetric}
          thresholds={dashboard.alerts?.thresholds || []}
        />
      );
    }

    if (pageMode === "recommendations") {
      return (
        <RecommendationsPage
          recommendations={(dashboard as any).recommendations}
          plannerDuration={plannerDuration}
          setPlannerDuration={(d: string) => setPlannerDuration(d)}
          handleLoadPlanner={handleLoadPlanner}
          finalPlannerError={(plannerValidationError || (dashboard as any).plannerError) as any}
          plannerLoading={(dashboard as any).plannerLoading}
          plannerNote={(dashboard as any).plannerNote}
          plannerResults={(dashboard as any).plannerResults || []}
        />
      );
    }

    if (pageMode === "battery") {
      return (
        <SectionCard title="Baterie a projekce">
          <BatteryProjectionCard
            batteryData={batteryData}
            batteryLoading={dashboard.batteryLoading}
            batteryError={dashboard.batteryError}
            onRefresh={dashboard.refreshBattery}
          />
        </SectionCard>
      );
    }

    if (pageMode === "solar") {
      return (
        <div className="modern-dashboard-grid">
          <SectionCard title="Soláry / FV" className="modern-section-card--wide">
            <SolarForecastCard solarForecast={dashboard.solarForecast} loading={dashboard.solarForecastLoading} />
          </SectionCard>
          <SectionCard title="Cena elektřiny dnes" className="modern-section-card--wide">
            <PriceChartCard
              chartData={todayData}
              fallbackMessage="Načítám data..."
              vtPeriods={config?.tarif?.vt_periods}
              highlightSlot={effectiveHighlightSlot}
              pinnedSlot={pinnedSlot}
              onPinSlot={setPinnedSlot}
              thresholds={dashboard.alerts}
              className="modern-price-chart"
            />
          </SectionCard>
        </div>
      );
    }

    if (pageMode === "monthly") {
      return (
        <div className="modern-dashboard-grid">
          <SectionCard title="Měsíční přehled" className="modern-section-card--wide">
            <MonthlySummaryCard
              selectedMonth={selectedMonth}
              setSelectedMonth={setSelectedMonth}
              maxMonth={currentMonthStr}
              monthlySummary={dashboard.monthlySummary || []}
              monthlyTotals={dashboard.monthlyTotals}
              monthlyError={dashboard.monthlyError}
            />
          </SectionCard>
          <SectionCard title="Odhad vyúčtování" className="modern-section-card--wide">
            <BillingCard
              billingMode={billingMode}
              setBillingMode={setBillingMode}
              billingMonth={billingMonth}
              setBillingMonth={setBillingMonth}
              billingYear={billingYear}
              setBillingYear={setBillingYear}
              maxMonth={currentMonthStr}
              maxYear={currentYearStr}
              billingData={dashboard.billingData}
              billingLoading={dashboard.billingLoading}
              billingError={dashboard.billingError}
            />
          </SectionCard>
        </div>
      );
    }

    if (pageMode === "stats") {
      return (
        <div className="modern-dashboard-grid">
          <SectionCard title="Srovnání výkonu" className="modern-section-card--wide">
            <ComparisonCard comparison={dashboard.comparison} loading={dashboard.comparisonLoading} />
          </SectionCard>
          <SectionCard title="Energetická bilance" className="modern-section-card--wide">
            <EnergyBalanceCard
              period={energyBalancePeriod}
              anchor={currentEnergyBalanceAnchor}
              onPrev={() => setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, -1))}
              onNext={() => setEnergyBalanceAnchor((prev: string) => shiftEnergyBalanceAnchor(energyBalancePeriod, prev, 1))}
              disableNext={currentEnergyBalanceAnchor === maxEnergyBalanceAnchor}
              onPeriodChange={(value: any) => {
                setEnergyBalancePeriod(value as any);
                setEnergyBalanceAnchor((prev: string) => normalizeEnergyBalanceAnchor(value, prev));
              }}
              data={dashboard.energyBalanceData}
              loading={dashboard.energyBalanceLoading}
              error={dashboard.energyBalanceError}
            />
          </SectionCard>
        </div>
      );
    }

    if (pageMode === "pnd") {
      return <PndPage config={config} refreshConfig={refreshConfig} />;
    }

    if (pageMode === "hp") {
      return <HpPage config={config} refreshConfig={refreshConfig} onKpisChange={() => {}} maxDate={todayDateStr} />;
    }

    return (
      <div className="modern-settings-grid">
        <ConfigCard
          configRows={configRows}
          cacheRows={cacheRows}
          consumptionCacheRows={consumptionCacheRows}
          exportCacheRows={exportCacheRows}
          cacheStatus={dashboard.cacheStatus}
          showFeesHistory={true}
          onToggleFeesHistory={() => setShowFeesHistory((prev: boolean) => !prev)}
          feesHistory={(dashboard as any).feesHistory}
          feesHistoryLoading={(dashboard as any).feesHistoryLoading}
          feesHistoryError={(dashboard as any).feesHistoryError}
          onSaveFeesHistory={(dashboard as any).saveFeesHistory}
          defaultFeesValues={defaultFeesValues}
          priceProviderLabel={priceProviderLabel}
          priceProviderUrl={priceProviderUrl}
          onRefreshPrices={refreshPrices}
          refreshingPrices={dashboard.pricesRefreshLoading}
          pricesRefreshMessage={dashboard.pricesRefreshMessage}
          pricesRefreshError={dashboard.pricesRefreshError}
        />
        <DataCard title="PND">
          <PndPage config={config} refreshConfig={refreshConfig} />
        </DataCard>
      </div>
    );
  };

  return (
    <div {...(pullHandlers as any)}>
      <div className={`pull-indicator ${pullArmed ? "is-armed" : ""} ${pullRefreshing ? "is-refreshing" : ""}`} style={{ height: pullRefreshing ? 42 : Math.min(42, pullDistance) }}>
        <span>{pullRefreshing ? "Obnovuji ceny..." : pullArmed ? "Uvolni pro obnoveni" : "Stahni pro obnoveni"}</span>
      </div>
      <AppShell
        pageMode={pageMode}
        setPageMode={setPageMode}
        theme={theme!}
        setTheme={setTheme}
        selectedDate={selectedDate}
        setSelectedDate={setSelectedDate}
        lastUpdatedAt={(dashboard as any).lastUpdatedAt}
        refreshing={dashboard.pricesRefreshLoading}
        onRefresh={refreshPrices}
        version={dashboard.version}
      >
        <Suspense fallback={<LazyPageFallback />}>
          {renderModernContent()}
        </Suspense>
      </AppShell>
    </div>
  );
};

export default App;
