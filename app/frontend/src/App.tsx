import React, { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence } from "framer-motion";
import AppHeader, { PageMode } from "./components/layout/AppHeader";
import BottomNav from "./components/layout/BottomNav";
import KPIScreen from "./components/layout/KPIScreen";
import OverviewPage from "./pages/OverviewPage";
import DetailPage from "./pages/DetailPage";
import PndPage from "./pages/PndPage";

import { formatSlotToTime, formatSlotRange, formatCurrency, formatBytes } from "./utils/formatters";
import { useLocalStorageState } from "./hooks/useLocalStorageState";
import { usePageVisibility } from "./hooks/usePageVisibility";
import { useCurrentSlot } from "./hooks/useCurrentSlot";
import { usePullToRefresh } from "./hooks/usePullToRefresh";
import { useSwipeGesture } from "./hooks/useSwipeGesture";
import { useDashboardData } from "./hooks/useDashboardData";
import {
  clampDateValue,
  clampMonthValue,
  getCurrentMonthStr,
  getCurrentYearStr,
  getTodayDateStr,
} from "./hooks/dashboardUtils";
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
  const todayDateStr = getTodayDateStr();
  const currentMonthStr = getCurrentMonthStr();
  const currentYearStr = getCurrentYearStr();
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

  const { config, batteryData, refreshPrices, refreshConfig } = dashboard;

  const activePriceProvider = config?.price_provider === "ote" ? "ote" : "spotovaelektrina";
  const priceProviderLabel = activePriceProvider === "ote" ? "OTE (ote-cr.cz + CNB)" : "spotovaelektrina.cz";
  const priceProviderUrl = activePriceProvider === "ote" ? "https://www.ote-cr.cz/" : "https://spotovaelektrina.cz/";
  const effectiveHighlightSlot = Number.isInteger(pinnedSlot) ? pinnedSlot : currentSlot;

  const dateSwipeHandlers = useSwipeGesture({
    onSwipeLeft: () => setSelectedDate((prev) => clampDateValue(shiftDateValue(prev, 1), todayDateStr)),
    onSwipeRight: () => setSelectedDate((prev) => shiftDateValue(prev, -1)),
  });

  const monthSwipeHandlers = useSwipeGesture({
    enabled: showMonthlySummary,
    onSwipeLeft: () => setSelectedMonth((prev) => clampMonthValue(shiftMonthValue(prev, 1), currentMonthStr)),
    onSwipeRight: () => setSelectedMonth((prev) => shiftMonthValue(prev, -1)),
  });

  const { pullDistance, isRefreshing: pullRefreshing, isArmed: pullArmed, gestureHandlers: pullHandlers } = usePullToRefresh({
    enabled: true,
    onRefresh: refreshPrices,
  });

  const handleLoadPlanner = async (durationOverride: number | string = plannerDuration): Promise<void> => {
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
    const currentSlotIndex = Number.isInteger(currentSlot) ? Number(currentSlot) : null;
    const currentPriceItem = currentSlotIndex != null && currentSlotIndex >= 0 && currentSlotIndex < todayData.length
      ? todayData[currentSlotIndex]
      : null;
    const finals = todayData.map((item: PriceItem) => item.final);
    const minFinal = finals.length ? Math.min(...finals) : null;
    const maxFinal = finals.length ? Math.max(...finals) : null;
    const minPriceItem = minFinal != null ? todayData.find((item: PriceItem) => item.final === minFinal) : null;
    const maxPriceItem = maxFinal != null ? todayData.find((item: PriceItem) => item.final === maxFinal) : null;
    const netTotal = dashboard.todayCostsKpi?.cost_total != null || dashboard.todayExportKpi?.sell_total != null
      ? (dashboard.todayCostsKpi?.cost_total || 0) - (dashboard.todayExportKpi?.sell_total || 0)
      : null;

    const batterySoc = batteryData?.status?.soc_percent;
    const batteryPower = batteryData?.status?.battery_power_w;
    const batteryProjection = batteryData?.projection;

    let batteryEtaDetail = null;
    if (batteryData?.is_today) {
      if (batteryProjection?.state === "charging" && batteryProjection?.eta_to_full_at) {
        batteryEtaDetail = `plna v ${formatEtaTime(batteryProjection.eta_to_full_at)} (${formatEtaDuration(batteryProjection.eta_to_full_minutes ?? null)})`;
      } else if (batteryProjection?.state === "charging" && batteryProjection?.peak_soc_at && batteryProjection?.peak_soc_percent != null) {
        batteryEtaDetail = `max ${batteryProjection.peak_soc_percent.toFixed(0)} % v ${formatEtaTime(batteryProjection.peak_soc_at)}`;
      } else if (batteryProjection?.state === "discharging" && batteryProjection?.eta_to_reserve_at) {
        batteryEtaDetail = `do rezervy v ${formatEtaTime(batteryProjection.eta_to_reserve_at)} (${formatEtaDuration(batteryProjection.eta_to_reserve_minutes ?? null)})`;
      }
    }

    return [
      { key: "price-now", label: "Cena ted", value: currentPriceItem ? formatCurrency(currentPriceItem.final) : "-", detail: currentPriceItem?.time, tone: "price" as const },
      { key: "price-min", label: "Dnes min", value: minFinal != null ? formatCurrency(minFinal) : "-", detail: minPriceItem ? formatSlotRange(minPriceItem.slot) : null, tone: "neutral" as const },
      { key: "price-max", label: "Dnes max", value: maxFinal != null ? formatCurrency(maxFinal) : "-", detail: maxPriceItem ? formatSlotRange(maxPriceItem.slot) : null, tone: "neutral" as const },
      { key: "cost-today", label: "Naklad dnes", value: formatCurrency(dashboard.todayCostsKpi?.cost_total), detail: dashboard.todayCostsKpi?.kwh_total ? `${dashboard.todayCostsKpi.kwh_total.toFixed(2)} kWh` : null, tone: "buy" as const },
      { key: "export-today", label: "Export dnes", value: formatCurrency(dashboard.todayExportKpi?.sell_total), detail: dashboard.todayExportKpi?.export_kwh_total ? `${dashboard.todayExportKpi.export_kwh_total.toFixed(2)} kWh` : null, tone: "sell" as const },
      { key: "net-today", label: "Netto dnes", value: formatCurrency(netTotal), tone: (netTotal != null && netTotal <= 0 ? "sell" : "buy") as "sell" | "buy" },
      { key: "battery", label: "Baterie", value: batterySoc != null ? `${batterySoc.toFixed(0)} %` : "-", detail: [batteryPower != null ? `${batteryPower >= 0 ? "+" : ""}${Math.round(batteryPower)} W` : null, batteryEtaDetail].filter(Boolean).join(" | "), tone: "battery" as const },
    ];
  }, [todayData, currentSlot, dashboard.todayCostsKpi, dashboard.todayExportKpi, batteryData]);

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

  return (
    <div className={`app ${pageMode !== "overview" ? "app--detail" : ""}`.trim()} {...(pullHandlers as any)}>
      <div className={`pull-indicator ${pullArmed ? "is-armed" : ""} ${pullRefreshing ? "is-refreshing" : ""}`} style={{ height: pullRefreshing ? 42 : Math.min(42, pullDistance) }}>
        <span>{pullRefreshing ? "Obnovuji ceny..." : pullArmed ? "Uvolni pro obnoveni" : "Stahni pro obnoveni"}</span>
      </div>

      <AppHeader pageMode={pageMode} setPageMode={setPageMode} theme={theme!} setTheme={setTheme} />
      <KPIScreen items={kpiItems as any} />

      <main className="app-main">
        <AnimatePresence mode="wait">
          {pageMode === "overview" && (
            <OverviewPage
              key="overview"
              {...dashboard} {...{
                today,
                tomorrow,
                todayData,
                tomorrowData,
                pinnedSlot: pinnedSlot as any,
                setPinnedSlot,
                effectiveHighlightSlot: effectiveHighlightSlot as any,
                dateSwipeHandlers,
                selectedDate,
                setSelectedDate,
                maxDate: todayDateStr,
                showMonthlySummary,
                setShowMonthlySummary,
                monthSwipeHandlers,
                selectedMonth,
                setSelectedMonth,
                maxMonth: currentMonthStr,
                showBilling,
                setShowBilling,
                billingMode,
                setBillingMode,
                billingMonth,
                setBillingMonth,
                billingYear,
                setBillingYear,
                maxBillingMonth: currentMonthStr,
                maxBillingYear: currentYearStr,
                showBatteryPanel: false,
                setShowBatteryPanel: () => {},
                refreshPrices,
                refreshBattery: dashboard.refreshBattery,
                showPlanner,
                handlePlannerToggle,
                plannerDuration,
                setPlannerDuration: (d: string) => setPlannerDuration(d),
                handleLoadPlanner,
                finalPlannerError: (plannerValidationError || (dashboard as any).plannerError) as any,
                showConfig,
                setShowConfig,
                configRows,
                cacheRows,
                consumptionCacheRows,
                exportCacheRows,
                priceProviderLabel,
                priceProviderUrl,
                feesHistory: (dashboard as any).feesHistory,
                feesHistoryLoading: (dashboard as any).feesHistoryLoading,
                feesHistoryError: (dashboard as any).feesHistoryError,
                saveFeesHistory: (dashboard as any).saveFeesHistory,
                showFeesHistory,
                setShowFeesHistory,
                energyBalancePeriod,
                energyBalanceAnchor,
                setEnergyBalanceAnchor,
                setEnergyBalancePeriod: (p: any) => setEnergyBalancePeriod(p),
                defaultFeesValues,
                thresholds: (dashboard as any).alerts?.thresholds || [],
              }}
            />
          )}
          {pageMode === "costs" && (
            <DetailPage
              key="costs"
              {...dashboard} {...{
                selectedDate,
                setSelectedDate,
                selectedDateObj: new Date(`${selectedDate}T00:00:00`),
                selectedDatePriceData,
                selectedDatePricesLoading: dashboard.selectedDatePricesLoading,
                selectedDatePricesError: dashboard.selectedDatePricesError,
                maxDate: todayDateStr,
                maxMonth: currentMonthStr,
                effectiveHighlightSlot: effectiveHighlightSlot as any,
                pinnedSlot: pinnedSlot as any,
                setPinnedSlot,
                dateSwipeHandlers,
                showDetailAnnotations: true,
                energyBalancePeriod,
                energyBalanceAnchor,
                setEnergyBalanceAnchor,
                setEnergyBalancePeriod,
                refreshBattery: dashboard.refreshBattery,
                heatmapMonth,
                setHeatmapMonth,
                heatmapMetric,
                setHeatmapMetric,
                thresholds: dashboard.alerts?.thresholds || [],
              }}
            />
          )}
          {pageMode === "battery" && (
            <div key="battery" className="page-battery">
              <OverviewPage
                {...dashboard} {...{
                  today,
                  tomorrow,
                  todayData,
                  tomorrowData,
                  pinnedSlot: pinnedSlot as any,
                  setPinnedSlot,
                  effectiveHighlightSlot: effectiveHighlightSlot as any,
                  dateSwipeHandlers,
                  selectedDate,
                  setSelectedDate,
                  maxDate: todayDateStr,
                  showMonthlySummary: false,
                  setShowMonthlySummary: () => {},
                  monthSwipeHandlers,
                  selectedMonth,
                  setSelectedMonth,
                  maxMonth: currentMonthStr,
                  showBilling: false,
                  setShowBilling: () => {},
                  billingMode,
                  setBillingMode,
                  billingMonth,
                  setBillingMonth,
                  billingYear,
                  setBillingYear,
                  maxBillingMonth: currentMonthStr,
                  maxBillingYear: currentYearStr,
                  showBatteryPanel: true,
                  setShowBatteryPanel: () => {},
                  refreshPrices,
                  refreshBattery: dashboard.refreshBattery,
                  showPlanner: false,
                  handlePlannerToggle: () => {},
                  plannerDuration,
                  setPlannerDuration: () => {},
                  handleLoadPlanner: async () => {},
                  finalPlannerError: null,
                  showConfig: false,
                  setShowConfig: () => {},
                  configRows: [],
                  cacheRows: [],
                  consumptionCacheRows: [],
                  exportCacheRows: [],
                  priceProviderLabel,
                  priceProviderUrl,
                  feesHistory: null,
                  feesHistoryLoading: false,
                  feesHistoryError: null,
                  saveFeesHistory: async () => {},
                  showFeesHistory: false,
                  setShowFeesHistory: () => {},
                  energyBalancePeriod,
                  energyBalanceAnchor,
                  setEnergyBalanceAnchor,
                  setEnergyBalancePeriod: (p: any) => setEnergyBalancePeriod(p),
                  defaultFeesValues: null,
                  thresholds: [],
                }}
              />
            </div>
          )}
          {pageMode === "settings" && (
            <div key="settings" className="page-settings p-4">
              <OverviewPage
                {...dashboard} {...{
                  today,
                  tomorrow,
                  todayData,
                  tomorrowData,
                  pinnedSlot: pinnedSlot as any,
                  setPinnedSlot,
                  effectiveHighlightSlot: effectiveHighlightSlot as any,
                  dateSwipeHandlers,
                  selectedDate,
                  setSelectedDate,
                  maxDate: todayDateStr,
                  showMonthlySummary: false,
                  setShowMonthlySummary: () => {},
                  monthSwipeHandlers,
                  selectedMonth,
                  setSelectedMonth,
                  maxMonth: currentMonthStr,
                  showBilling: false,
                  setShowBilling: () => {},
                  billingMode,
                  setBillingMode,
                  billingMonth,
                  setBillingMonth,
                  billingYear,
                  setBillingYear,
                  maxBillingMonth: currentMonthStr,
                  maxBillingYear: currentYearStr,
                  showBatteryPanel: false,
                  setShowBatteryPanel: () => {},
                  refreshPrices,
                  refreshBattery: dashboard.refreshBattery,
                  showPlanner: false,
                  handlePlannerToggle: () => {},
                  plannerDuration,
                  setPlannerDuration: () => {},
                  handleLoadPlanner: async () => {},
                  finalPlannerError: null,
                  showConfig: true,
                  setShowConfig: () => {},
                  configRows,
                  cacheRows,
                  consumptionCacheRows,
                  exportCacheRows,
                  priceProviderLabel,
                  priceProviderUrl,
                  feesHistory: (dashboard as any).feesHistory,
                  feesHistoryLoading: (dashboard as any).feesHistoryLoading,
                  feesHistoryError: (dashboard as any).feesHistoryError,
                  saveFeesHistory: (dashboard as any).saveFeesHistory as any,
                  showFeesHistory: true,
                  setShowFeesHistory,
                  energyBalancePeriod,
                  energyBalanceAnchor,
                  setEnergyBalanceAnchor,
                  setEnergyBalancePeriod: (p: any) => setEnergyBalancePeriod(p),
                  defaultFeesValues,
                  thresholds: [],
                }}
              />
            </div>
          )}
          {pageMode === "pnd" && (
            <div key="pnd" className="page-pnd">
              <PndPage config={config} refreshConfig={refreshConfig} />
            </div>
          )}
        </AnimatePresence>
      </main>

      <footer className="footer">
        <div>(c) {new Date().getFullYear()} mondychan <a href="https://github.com/mondychan" target="_blank" rel="noopener noreferrer">github</a></div>
        <div className="version-tag">Verze doplnku: {dashboard.version || "-"}</div>
      </footer>

      <BottomNav pageMode={pageMode} setPageMode={setPageMode} />
    </div>
  );
};

export default App;
