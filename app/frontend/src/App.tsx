import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence } from "framer-motion";
import AppHeader, { PageMode } from "./components/layout/AppHeader";
import BottomNav from "./components/layout/BottomNav";
import KPIScreen from "./components/layout/KPIScreen";
import OverviewPage from "./pages/OverviewPage";
import DetailPage from "./pages/DetailPage";

import { formatSlotToTime, formatSlotRange, formatCurrency } from "./utils/formatters";
import { useLocalStorageState } from "./hooks/useLocalStorageState";
import { usePageVisibility } from "./hooks/usePageVisibility";
import { useCurrentSlot } from "./hooks/useCurrentSlot";
import { usePullToRefresh } from "./hooks/usePullToRefresh";
import { useSwipeGesture } from "./hooks/useSwipeGesture";
import { useDashboardData } from "./hooks/useDashboardData";
import { PriceItem } from "./types/elektroapp";

const formatEtaTime = (iso: string | null) => {
  if (!iso) return null;
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return null;
  return dt.toLocaleTimeString("cs-CZ", { hour: "2-digit", minute: "2-digit" });
};

const formatEtaDuration = (minutes: number | null) => {
  if (minutes == null || !Number.isFinite(minutes)) return null;
  if (minutes < 60) return `${minutes} min`;
  const h = Math.floor(minutes / 60);
  const m = minutes % 60;
  if (!m) return `${h} h`;
  return `${h} h ${m} min`;
};

const shiftDateValue = (value: string, dayDelta: number) => {
  const dt = new Date(`${value}T00:00:00`);
  if (Number.isNaN(dt.getTime())) return value;
  dt.setDate(dt.getDate() + dayDelta);
  const y = dt.getFullYear();
  const m = String(dt.getMonth() + 1).padStart(2, "0");
  const d = String(dt.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

const shiftMonthValue = (value: string, monthDelta: number) => {
  const [year, month] = (value || "").split("-").map(Number);
  if (!Number.isFinite(year) || !Number.isFinite(month)) return value;
  const dt = new Date(year, month - 1 + monthDelta, 1);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
};

const App: React.FC = () => {
  const [pageMode, setPageMode] = useState<PageMode>("overview");
  const [showConfig, setShowConfig] = useState(false);
  const [showMonthlySummary, setShowMonthlySummary] = useState(false);
  const [showPlanner, setShowPlanner] = useState(false);
  const [showBilling, setShowBilling] = useState(false);
  const [showFeesHistory, setShowFeesHistory] = useState(false);

  const [theme, setTheme] = useLocalStorageState<"light" | "dark" | "system">("theme", "light");
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

  const dashboard = useDashboardData({
    selectedDate,
    selectedMonth,
    showConfig,
    showFeesHistory,
    showBilling,
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

  const { config, batteryData, refreshPrices } = dashboard;

  const activePriceProvider = config?.price_provider === "ote" ? "ote" : "spotovaelektrina";
  const priceProviderLabel = activePriceProvider === "ote" ? "OTE (ote-cr.cz + CNB)" : "spotovaelektrina.cz";
  const priceProviderUrl = activePriceProvider === "ote" ? "https://www.ote-cr.cz/" : "https://spotovaelektrina.cz/";
  const effectiveHighlightSlot = Number.isInteger(pinnedSlot) ? pinnedSlot : currentSlot;

  const dateSwipeHandlers = useSwipeGesture({
    onSwipeLeft: () => setSelectedDate((prev) => shiftDateValue(prev, 1)),
    onSwipeRight: () => setSelectedDate((prev) => shiftDateValue(prev, -1)),
  });

  const monthSwipeHandlers = useSwipeGesture({
    enabled: showMonthlySummary,
    onSwipeLeft: () => setSelectedMonth((prev) => shiftMonthValue(prev, 1)),
    onSwipeRight: () => setSelectedMonth((prev) => shiftMonthValue(prev, -1)),
  });

  const { pullDistance, isRefreshing: pullRefreshing, isArmed: pullArmed, gestureHandlers: pullHandlers } = usePullToRefresh({
    enabled: true,
    onRefresh: refreshPrices,
  });

  const handleLoadPlanner = async (durationOverride: number | string = plannerDuration): Promise<void> => {
    const parsed = typeof durationOverride === "number" ? durationOverride : Number.parseInt(durationOverride, 10);
    if (!parsed || parsed <= 0 || parsed > 360) {
      setPlannerValidationError("Okna musí být 1-360 minut.");
      return;
    }
    setPlannerDuration(String(parsed));
    setPlannerValidationError(null);
    try {
      await (dashboard as any).loadPlanner(parsed);
    } catch {}
  };

  const handlePlannerToggle = () => {
    if (showPlanner) {
      setShowPlanner(false);
      return;
    }
    setShowPlanner(true);
    handleLoadPlanner();
  };

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

  const kpiItems = useMemo(() => {
    const currentPriceItem = Number.isInteger(currentSlot) && currentSlot! >= 0 && currentSlot! < todayData.length ? todayData[currentSlot!] : null;
    const finals = todayData.map((item: PriceItem) => item.final);
    const minFinal = finals.length ? Math.min(...finals) : null;
    const maxFinal = finals.length ? Math.max(...finals) : null;
    const minPriceItem = minFinal != null ? todayData.find((item: PriceItem) => item.final === minFinal) : null;
    const maxPriceItem = maxFinal != null ? todayData.find((item: PriceItem) => item.final === maxFinal) : null;
    const netTotal = dashboard.todayCostsKpi?.cost_total != null || dashboard.todayExportKpi?.sell_total != null 
      ? (dashboard.todayCostsKpi?.cost_total || 0) - (dashboard.todayExportKpi?.sell_total || 0) : null;
    
    const batterySoc = batteryData?.status?.soc_percent;
    const batteryPower = batteryData?.status?.battery_power_w;
    const batteryProjection = batteryData?.projection;

    let batteryEtaDetail = null;
    if (batteryData?.is_today) {
      if (batteryProjection?.state === "charging" && batteryProjection?.eta_to_full_at) {
        batteryEtaDetail = `plna v ${formatEtaTime(batteryProjection.eta_to_full_at)} (${formatEtaDuration(batteryProjection.eta_to_full_minutes ?? null)})`;
      } else if (batteryProjection?.state === "discharging" && batteryProjection?.eta_to_reserve_at) {
        batteryEtaDetail = `do rezervy v ${formatEtaTime(batteryProjection.eta_to_reserve_at)} (${formatEtaDuration(batteryProjection.eta_to_reserve_minutes ?? null)})`;
      }
    }

    return [
      { key: "price-now", label: "Cena teď", value: currentPriceItem ? formatCurrency(currentPriceItem.final) : "-", detail: currentPriceItem?.time, tone: "price" as const },
      { key: "price-min", label: "Dnes min", value: minFinal != null ? formatCurrency(minFinal) : "-", detail: minPriceItem ? formatSlotRange(minPriceItem.slot) : null, tone: "neutral" as const },
      { key: "price-max", label: "Dnes max", value: maxFinal != null ? formatCurrency(maxFinal) : "-", detail: maxPriceItem ? formatSlotRange(maxPriceItem.slot) : null, tone: "neutral" as const },
      { key: "cost-today", label: "Náklad dnes", value: formatCurrency(dashboard.todayCostsKpi?.cost_total), detail: dashboard.todayCostsKpi?.kwh_total ? `${dashboard.todayCostsKpi.kwh_total.toFixed(2)} kWh` : null, tone: "buy" as const },
      { key: "export-today", label: "Export dnes", value: formatCurrency(dashboard.todayExportKpi?.sell_total), detail: dashboard.todayExportKpi?.export_kwh_total ? `${dashboard.todayExportKpi.export_kwh_total.toFixed(2)} kWh` : null, tone: "sell" as const },
      { key: "net-today", label: "Netto dnes", value: formatCurrency(netTotal), tone: (netTotal != null && netTotal <= 0 ? "sell" : "buy") as "sell" | "buy" },
      { key: "battery", label: "Baterie", value: batterySoc != null ? `${batterySoc.toFixed(0)} %` : "-", detail: [batteryPower != null ? `${batteryPower >= 0 ? "+" : ""}${Math.round(batteryPower)} W` : null, batteryEtaDetail].filter(Boolean).join(" | "), tone: "battery" as const },
    ];
  }, [todayData, currentSlot, dashboard.todayCostsKpi, dashboard.todayExportKpi, batteryData]);

  const configRows = useMemo(() => {
    if (!config) return [];
    const f = (v: any) => v ?? "-";
    return [
      { label: "DPH", value: Number(config.dph ?? 0).toFixed(0), unit: "%" },
      { label: "Zdroj cen", value: priceProviderLabel },
      { label: "Služba obchodu", value: f(config.poplatky?.komodita_sluzba), unit: "Kč/kWh" },
      { label: "OZE", value: f(config.poplatky?.oze), unit: "Kč/kWh" },
      { label: "Daň", value: f(config.poplatky?.dan), unit: "Kč/kWh" },
      { label: "Systémové služby", value: f(config.poplatky?.systemove_sluzby), unit: "Kč/kWh" },
      { label: "Distribuce NT/VT", value: `${f(config.poplatky?.distribuce?.NT)} / ${f(config.poplatky?.distribuce?.VT)}`, unit: "Kč/kWh" },
      { label: "Stálý plat", value: f(config.fixni?.denni?.staly_plat), unit: "Kč/den" },
      { label: "Jistič", value: f(config.fixni?.mesicni?.jistic), unit: "Kč/měsíc" },
    ];
  }, [config, priceProviderLabel]);

  const today = new Date();
  const tomorrow = new Date(today);
  tomorrow.setDate(today.getDate() + 1);

  return (
    <div className={`app ${pageMode !== "overview" ? "app--detail" : ""}`.trim()} {...(pullHandlers as any)}>
      <div className={`pull-indicator ${pullArmed ? "is-armed" : ""} ${pullRefreshing ? "is-refreshing" : ""}`} style={{ height: pullRefreshing ? 42 : Math.min(42, pullDistance) }}>
        <span>{pullRefreshing ? "Obnovuji ceny..." : pullArmed ? "Uvolni pro obnovení" : "Stáhni pro obnovení"}</span>
      </div>

      <AppHeader pageMode={pageMode} setPageMode={setPageMode} theme={theme!} setTheme={setTheme} />
      <KPIScreen items={kpiItems as any} />
      
      <main className="app-main">
        <AnimatePresence mode="wait">
          {pageMode === "overview" && (
            <OverviewPage 
              key="overview"
              {...dashboard} {...{ today, tomorrow, todayData, tomorrowData, pinnedSlot: pinnedSlot as any, setPinnedSlot, effectiveHighlightSlot: effectiveHighlightSlot as any, dateSwipeHandlers, selectedDate, setSelectedDate, showMonthlySummary, setShowMonthlySummary, monthSwipeHandlers, selectedMonth, setSelectedMonth, showBilling, setShowBilling, billingMode, setBillingMode, billingMonth, setBillingMonth, billingYear, setBillingYear, showBatteryPanel: false, setShowBatteryPanel: () => {}, refreshPrices, refreshBattery: dashboard.refreshBattery, showPlanner, handlePlannerToggle, plannerDuration, setPlannerDuration: (d: string) => setPlannerDuration(d), handleLoadPlanner, finalPlannerError: (plannerValidationError || (dashboard as any).plannerError) as any, showConfig, setShowConfig, configRows, cacheRows: [], consumptionCacheRows: [], priceProviderLabel, priceProviderUrl, feesHistory: (dashboard as any).feesHistory, feesHistoryLoading: (dashboard as any).feesHistoryLoading, feesHistoryError: (dashboard as any).feesHistoryError, saveFeesHistory: (dashboard as any).saveFeesHistory, showFeesHistory, setShowFeesHistory, energyBalancePeriod, energyBalanceAnchor, setEnergyBalanceAnchor, setEnergyBalancePeriod: (p: any) => setEnergyBalancePeriod(p), defaultFeesValues: null, thresholds: (dashboard as any).alerts?.thresholds || [] }}
            />
          )}
          {pageMode === "costs" && (
            <DetailPage 
              key="costs"
              {...dashboard} {...{ selectedDate, setSelectedDate, selectedDateObj: new Date(`${selectedDate}T00:00:00`), selectedDatePriceData, selectedDatePricesLoading: dashboard.selectedDatePricesLoading, selectedDatePricesError: dashboard.selectedDatePricesError, effectiveHighlightSlot: effectiveHighlightSlot as any, pinnedSlot: pinnedSlot as any, setPinnedSlot, dateSwipeHandlers, showDetailAnnotations: true, energyBalancePeriod, energyBalanceAnchor, setEnergyBalanceAnchor, setEnergyBalancePeriod, refreshBattery: dashboard.refreshBattery, heatmapMonth, setHeatmapMonth, heatmapMetric, setHeatmapMetric, thresholds: dashboard.alerts?.thresholds || [] }}
            />
          )}
          {pageMode === "battery" && (
            <div key="battery" className="page-battery">
              {/* placeholder for Battery Page logic */}
              <OverviewPage 
                {...dashboard} {...{ today, tomorrow, todayData, tomorrowData, pinnedSlot: pinnedSlot as any, setPinnedSlot, effectiveHighlightSlot: effectiveHighlightSlot as any, dateSwipeHandlers, selectedDate, setSelectedDate, showMonthlySummary: false, setShowMonthlySummary: () => {}, monthSwipeHandlers, selectedMonth, setSelectedMonth, showBilling: false, setShowBilling: () => {}, billingMode, setBillingMode, billingMonth, setBillingMonth, billingYear, setBillingYear, showBatteryPanel: true, setShowBatteryPanel: () => {}, refreshPrices, refreshBattery: dashboard.refreshBattery, showPlanner: false, handlePlannerToggle: () => {}, plannerDuration, setPlannerDuration: () => {}, handleLoadPlanner: async () => {}, finalPlannerError: null, showConfig: false, setShowConfig: () => {}, configRows: [], cacheRows: [], consumptionCacheRows: [], priceProviderLabel, priceProviderUrl, feesHistory: null, feesHistoryLoading: false, feesHistoryError: null, saveFeesHistory: async () => {}, showFeesHistory: false, setShowFeesHistory: () => {}, energyBalancePeriod, energyBalanceAnchor, setEnergyBalanceAnchor, setEnergyBalancePeriod: (p: any) => setEnergyBalancePeriod(p), defaultFeesValues: null, thresholds: [] }}
              />
            </div>
          )}
          {pageMode === "settings" && (
             <div key="settings" className="page-settings p-4">
                <OverviewPage 
                  {...dashboard} {...{ today, tomorrow, todayData, tomorrowData, pinnedSlot: pinnedSlot as any, setPinnedSlot, effectiveHighlightSlot: effectiveHighlightSlot as any, dateSwipeHandlers, selectedDate, setSelectedDate, showMonthlySummary: false, setShowMonthlySummary: () => {}, monthSwipeHandlers, selectedMonth, setSelectedMonth, showBilling: false, setShowBilling: () => {}, billingMode, setBillingMode, billingMonth, setBillingMonth, billingYear, setBillingYear, showBatteryPanel: false, setShowBatteryPanel: () => {}, refreshPrices, refreshBattery: dashboard.refreshBattery, showPlanner: false, handlePlannerToggle: () => {}, plannerDuration, setPlannerDuration: () => {}, handleLoadPlanner: async () => {}, finalPlannerError: null, showConfig: true, setShowConfig: () => {}, configRows, cacheRows: [], consumptionCacheRows: [], priceProviderLabel, priceProviderUrl, feesHistory: (dashboard as any).feesHistory, feesHistoryLoading: (dashboard as any).feesHistoryLoading, feesHistoryError: (dashboard as any).feesHistoryError, saveFeesHistory: (dashboard as any).saveFeesHistory as any, showFeesHistory: true, setShowFeesHistory, energyBalancePeriod, energyBalanceAnchor, setEnergyBalanceAnchor, setEnergyBalancePeriod: (p: any) => setEnergyBalancePeriod(p), defaultFeesValues: null, thresholds: [] }}
                />
             </div>
          )}
        </AnimatePresence>
      </main>

      <footer className="footer">
        <div>(c) {new Date().getFullYear()} mondychan <a href="https://github.com/mondychan" target="_blank" rel="noopener noreferrer">github</a></div>
        <div className="version-tag">Verze doplňku: {dashboard.version || "-"}</div>
      </footer>

      <BottomNav pageMode={pageMode} setPageMode={setPageMode} />
    </div>
  );
}

export default App;
