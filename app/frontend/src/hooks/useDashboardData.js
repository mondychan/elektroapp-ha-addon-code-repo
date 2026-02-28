import { useCallback, useEffect, useMemo, useState } from "react";
import { buildInfluxError, elektroappApi, formatApiError } from "../api/elektroappApi";

const getTodayDateStr = () => {
  const today = new Date();
  const y = today.getFullYear();
  const m = String(today.getMonth() + 1).padStart(2, "0");
  const d = String(today.getDate()).padStart(2, "0");
  return `${y}-${m}-${d}`;
};

export const normalizeEnergyBalanceAnchor = (period, currentAnchor) => {
  const now = new Date();
  const y = now.getFullYear();
  const m = String(now.getMonth() + 1).padStart(2, "0");
  const d = String(now.getDate()).padStart(2, "0");
  if (period === "year") {
    const parsed = Number.parseInt(currentAnchor, 10);
    return Number.isFinite(parsed) ? String(parsed) : String(y);
  }
  if (period === "month") {
    if (/^\d{4}-\d{2}$/.test(currentAnchor || "")) return currentAnchor;
    return `${y}-${m}`;
  }
  if (/^\d{4}-\d{2}-\d{2}$/.test(currentAnchor || "")) return currentAnchor;
  return `${y}-${m}-${d}`;
};

export const shiftEnergyBalanceAnchor = (period, anchorValue, delta) => {
  const anchorNorm = normalizeEnergyBalanceAnchor(period, anchorValue);
  if (period === "year") {
    return String((Number.parseInt(anchorNorm, 10) || new Date().getFullYear()) + delta);
  }
  if (period === "month") {
    const [year, month] = anchorNorm.split("-").map(Number);
    const dt = new Date(year, (month || 1) - 1 + delta, 1);
    return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}`;
  }
  const [year, month, day] = anchorNorm.split("-").map(Number);
  const dt = new Date(year, (month || 1) - 1, day || 1);
  dt.setDate(dt.getDate() + delta * 7);
  return `${dt.getFullYear()}-${String(dt.getMonth() + 1).padStart(2, "0")}-${String(dt.getDate()).padStart(2, "0")}`;
};

export const useDashboardData = ({
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
  autoRefreshEnabled,
  isPageVisible,
}) => {
  const [prices, setPrices] = useState([]);
  const [config, setConfig] = useState(null);
  const [cacheStatus, setCacheStatus] = useState(null);
  const [version, setVersion] = useState(null);

  const [costs, setCosts] = useState([]);
  const [costsSummary, setCostsSummary] = useState(null);
  const [costsError, setCostsError] = useState(null);
  const [costsFromCache, setCostsFromCache] = useState(false);
  const [costsCacheFallback, setCostsCacheFallback] = useState(false);

  const [exportPoints, setExportPoints] = useState([]);
  const [exportSummary, setExportSummary] = useState(null);
  const [exportError, setExportError] = useState(null);
  const [exportFromCache, setExportFromCache] = useState(false);
  const [exportCacheFallback, setExportCacheFallback] = useState(false);

  const [monthlySummary, setMonthlySummary] = useState([]);
  const [monthlyTotals, setMonthlyTotals] = useState(null);
  const [monthlyError, setMonthlyError] = useState(null);

  const [billingData, setBillingData] = useState(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingError, setBillingError] = useState(null);

  const [batteryData, setBatteryData] = useState(null);
  const [batteryLoading, setBatteryLoading] = useState(false);
  const [batteryError, setBatteryError] = useState(null);

  const [todayCostsKpi, setTodayCostsKpi] = useState(null);
  const [todayExportKpi, setTodayExportKpi] = useState(null);

  const [energyBalanceData, setEnergyBalanceData] = useState(null);
  const [energyBalanceLoading, setEnergyBalanceLoading] = useState(false);
  const [energyBalanceError, setEnergyBalanceError] = useState(null);

  const [heatmapData, setHeatmapData] = useState(null);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [heatmapError, setHeatmapError] = useState(null);

  const [feesHistory, setFeesHistory] = useState([]);
  const [feesHistoryLoading, setFeesHistoryLoading] = useState(false);
  const [feesHistoryError, setFeesHistoryError] = useState(null);

  const [pricesRefreshLoading, setPricesRefreshLoading] = useState(false);
  const [pricesRefreshMessage, setPricesRefreshMessage] = useState(null);
  const [pricesRefreshError, setPricesRefreshError] = useState(null);

  const [plannerLoading, setPlannerLoading] = useState(false);
  const [plannerResults, setPlannerResults] = useState([]);
  const [plannerNote, setPlannerNote] = useState(null);
  const [plannerError, setPlannerError] = useState(null);

  const todayDate = useMemo(() => getTodayDateStr(), []);

  const fetchPrices = useCallback(async () => {
    try {
      const data = await elektroappApi.getPrices();
      setPrices(data?.prices || []);
    } catch (err) {
      console.error("Error fetching prices:", err);
    }
  }, []);

  const fetchCosts = useCallback(async (dateValue, options = {}) => {
    const { reset = true } = options;
    if (reset) {
      setCosts([]);
      setCostsSummary(null);
      setCostsError(null);
      setCostsFromCache(false);
      setCostsCacheFallback(false);
    }
    try {
      const data = await elektroappApi.getCosts(dateValue);
      setCosts(data?.points || []);
      setCostsSummary(data?.summary || null);
      setCostsFromCache(Boolean(data?.from_cache));
      setCostsCacheFallback(Boolean(data?.cache_fallback));
    } catch (err) {
      console.error("Error fetching costs:", err);
      setCostsError(buildInfluxError(err));
      setCostsFromCache(false);
      setCostsCacheFallback(false);
    }
  }, []);

  const fetchExport = useCallback(async (dateValue, options = {}) => {
    const { reset = true } = options;
    if (reset) {
      setExportPoints([]);
      setExportSummary(null);
      setExportError(null);
      setExportFromCache(false);
      setExportCacheFallback(false);
    }
    try {
      const data = await elektroappApi.getExport(dateValue);
      setExportPoints(data?.points || []);
      setExportSummary(data?.summary || null);
      setExportFromCache(Boolean(data?.from_cache));
      setExportCacheFallback(Boolean(data?.cache_fallback));
    } catch (err) {
      console.error("Error fetching export:", err);
      setExportError(buildInfluxError(err));
      setExportFromCache(false);
      setExportCacheFallback(false);
    }
  }, []);

  const refreshBattery = useCallback(async (options = {}) => {
    const { silent = false } = options;
    if (!silent) {
      setBatteryLoading(true);
    }
    setBatteryError(null);
    try {
      const data = await elektroappApi.getBattery();
      setBatteryData(data);
    } catch (err) {
      console.error("Error fetching battery data:", err);
      setBatteryError(buildInfluxError(err));
    } finally {
      if (!silent) {
        setBatteryLoading(false);
      }
    }
  }, []);

  const fetchTodayKpiSummaries = useCallback(async () => {
    try {
      const costsData = await elektroappApi.getCosts(todayDate);
      setTodayCostsKpi(costsData?.summary || null);
    } catch (err) {
      console.error("Error fetching today cost KPI:", err);
      setTodayCostsKpi(null);
    }
    try {
      const exportData = await elektroappApi.getExport(todayDate);
      setTodayExportKpi(exportData?.summary || null);
    } catch (err) {
      console.error("Error fetching today export KPI:", err);
      setTodayExportKpi(null);
    }
  }, [todayDate]);

  const fetchEnergyBalance = useCallback(async () => {
    setEnergyBalanceLoading(true);
    setEnergyBalanceError(null);
    const anchor = normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor);
    try {
      const data = await elektroappApi.getEnergyBalance(energyBalancePeriod, anchor);
      setEnergyBalanceData(data);
    } catch (err) {
      console.error("Error fetching energy balance:", err);
      setEnergyBalanceError(buildInfluxError(err));
    } finally {
      setEnergyBalanceLoading(false);
    }
  }, [energyBalancePeriod, energyBalanceAnchor]);

  const fetchHeatmap = useCallback(async () => {
    setHeatmapLoading(true);
    setHeatmapError(null);
    try {
      const data = await elektroappApi.getHistoryHeatmap(heatmapMonth, heatmapMetric);
      setHeatmapData(data);
    } catch (err) {
      console.error("Error fetching heatmap:", err);
      setHeatmapError(buildInfluxError(err));
    } finally {
      setHeatmapLoading(false);
    }
  }, [heatmapMonth, heatmapMetric]);

  const fetchFeesHistory = useCallback(async () => {
    setFeesHistoryLoading(true);
    setFeesHistoryError(null);
    try {
      const data = await elektroappApi.getFeesHistory();
      setFeesHistory(data?.history || []);
    } catch (err) {
      console.error("Error fetching fees history:", err);
      setFeesHistoryError(formatApiError(err, "Nepodarilo se nacist historii poplatku."));
    } finally {
      setFeesHistoryLoading(false);
    }
  }, []);

  const saveFeesHistory = useCallback(async (historyPayload) => {
    setFeesHistoryLoading(true);
    setFeesHistoryError(null);
    try {
      const data = await elektroappApi.saveFeesHistory(historyPayload);
      const history = data?.history || [];
      setFeesHistory(history);
      return history;
    } catch (err) {
      console.error("Error saving fees history:", err);
      setFeesHistoryError(formatApiError(err, "Nepodarilo se ulozit historii poplatku."));
      throw err;
    } finally {
      setFeesHistoryLoading(false);
    }
  }, []);

  const refreshPrices = useCallback(async () => {
    setPricesRefreshLoading(true);
    setPricesRefreshMessage(null);
    setPricesRefreshError(null);
    try {
      const data = await elektroappApi.refreshPrices({});
      const refreshed = data?.refreshed || [];
      const summary = refreshed.map((item) => `${item.date}: ${item.count} zaznamu`).join(" | ");
      setPricesRefreshMessage(summary || "Ceny byly obnoveny.");
      await fetchPrices();
      await fetchTodayKpiSummaries();
      if (selectedDate === todayDate) {
        await fetchCosts(selectedDate, { reset: false });
        await fetchExport(selectedDate, { reset: false });
      }
      if (showConfig) {
        try {
          const cacheData = await elektroappApi.getCacheStatus();
          setCacheStatus(cacheData);
        } catch (err) {
          console.error("Error fetching cache status:", err);
        }
      }
    } catch (err) {
      console.error("Error refreshing prices:", err);
      setPricesRefreshError(formatApiError(err, "Obnoveni cen selhalo."));
    } finally {
      setPricesRefreshLoading(false);
    }
  }, [fetchCosts, fetchExport, fetchPrices, fetchTodayKpiSummaries, selectedDate, showConfig, todayDate]);

  const loadPlanner = useCallback(async (durationValue) => {
    setPlannerLoading(true);
    setPlannerError(null);
    setPlannerNote(null);
    try {
      const data = await elektroappApi.getSchedule(durationValue, 3);
      setPlannerResults(data?.recommendations || []);
      setPlannerNote(data?.note || null);
    } catch (err) {
      console.error("Error fetching planner:", err);
      if (err?.response?.status === 422) {
        setPlannerError(formatApiError(err, "Okno je prilis dlouhe. Zadej delku 1-360 minut."));
      } else {
        setPlannerError(formatApiError(err, "Planovac neni k dispozici."));
      }
      throw err;
    } finally {
      setPlannerLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPrices();
    fetchTodayKpiSummaries();
    refreshBattery({ silent: true });
  }, [fetchPrices, fetchTodayKpiSummaries, refreshBattery]);

  useEffect(() => {
    elektroappApi
      .getConfig()
      .then((data) => setConfig(data))
      .catch((err) => console.error("Error fetching config:", err));
  }, []);

  useEffect(() => {
    elektroappApi
      .getVersion()
      .then((data) => setVersion(data?.version || null))
      .catch((err) => console.error("Error fetching version:", err));
  }, []);

  useEffect(() => {
    if (!showConfig) return;
    elektroappApi
      .getCacheStatus()
      .then((data) => setCacheStatus(data))
      .catch((err) => console.error("Error fetching cache status:", err));
  }, [showConfig]);

  useEffect(() => {
    fetchCosts(selectedDate, { reset: true });
  }, [fetchCosts, selectedDate]);

  useEffect(() => {
    fetchExport(selectedDate, { reset: true });
  }, [fetchExport, selectedDate]);

  useEffect(() => {
    setMonthlySummary([]);
    setMonthlyTotals(null);
    setMonthlyError(null);
    elektroappApi
      .getDailySummary(selectedMonth)
      .then((data) => {
        setMonthlySummary(data?.days || []);
        setMonthlyTotals(data?.summary || null);
      })
      .catch((err) => {
        console.error("Error fetching monthly summary:", err);
        setMonthlyError(buildInfluxError(err));
      });
  }, [selectedMonth]);

  useEffect(() => {
    if (!showBilling) return;
    setBillingLoading(true);
    setBillingError(null);
    setBillingData(null);
    const request = billingMode === "year" ? elektroappApi.getBillingYear(billingYear) : elektroappApi.getBillingMonth(billingMonth);
    request
      .then((data) => setBillingData(data))
      .catch((err) => {
        console.error("Error fetching billing summary:", err);
        setBillingError(buildInfluxError(err));
      })
      .finally(() => setBillingLoading(false));
  }, [showBilling, billingMode, billingMonth, billingYear]);

  useEffect(() => {
    if (!showConfig || !showFeesHistory) return;
    fetchFeesHistory();
  }, [showConfig, showFeesHistory, fetchFeesHistory]);

  useEffect(() => {
    if (pageMode !== "detail") return;
    fetchEnergyBalance();
  }, [pageMode, fetchEnergyBalance]);

  useEffect(() => {
    if (pageMode !== "detail") return;
    fetchHeatmap();
  }, [pageMode, fetchHeatmap]);

  useEffect(() => {
    if (!autoRefreshEnabled || !isPageVisible) return;
    const refresh = () => {
      fetchPrices();
      fetchTodayKpiSummaries();
      if (selectedDate === getTodayDateStr()) {
        fetchCosts(selectedDate, { reset: false });
        fetchExport(selectedDate, { reset: false });
      }
      refreshBattery({ silent: true });
    };
    refresh();
    const intervalId = setInterval(refresh, 600000);
    return () => clearInterval(intervalId);
  }, [autoRefreshEnabled, isPageVisible, selectedDate, fetchCosts, fetchExport, fetchPrices, fetchTodayKpiSummaries, refreshBattery]);

  useEffect(() => {
    if (!autoRefreshEnabled || !isPageVisible) return;
    const intervalId = setInterval(() => {
      refreshBattery({ silent: true });
    }, 60000);
    return () => clearInterval(intervalId);
  }, [autoRefreshEnabled, isPageVisible, refreshBattery]);

  return {
    prices,
    config,
    cacheStatus,
    version,
    costs,
    costsSummary,
    costsError,
    costsFromCache,
    costsCacheFallback,
    exportPoints,
    exportSummary,
    exportError,
    exportFromCache,
    exportCacheFallback,
    monthlySummary,
    monthlyTotals,
    monthlyError,
    billingData,
    billingLoading,
    billingError,
    batteryData,
    batteryLoading,
    batteryError,
    refreshBattery: () => refreshBattery(),
    todayCostsKpi,
    todayExportKpi,
    energyBalanceData,
    energyBalanceLoading,
    energyBalanceError,
    heatmapData,
    heatmapLoading,
    heatmapError,
    feesHistory,
    feesHistoryLoading,
    feesHistoryError,
    saveFeesHistory,
    refreshPrices,
    pricesRefreshLoading,
    pricesRefreshMessage,
    pricesRefreshError,
    loadPlanner,
    plannerLoading,
    plannerResults,
    plannerNote,
    plannerError,
  };
};
