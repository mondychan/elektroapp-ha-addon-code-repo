import { useCallback, useEffect, useMemo, useState } from "react";
import { buildInfluxError, elektroappApi, formatApiError } from "../api/elektroappApi";
import { getTodayDateStr } from "./dashboardUtils";

export const usePrimaryDashboardData = ({ selectedDate, showConfig, autoRefreshEnabled, isPageVisible }) => {
  const [prices, setPrices] = useState([]);
  const [selectedDatePrices, setSelectedDatePrices] = useState([]);
  const [selectedDatePricesLoading, setSelectedDatePricesLoading] = useState(false);
  const [selectedDatePricesError, setSelectedDatePricesError] = useState(null);
  
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

  const [batteryData, setBatteryData] = useState(null);
  const [batteryLoading, setBatteryLoading] = useState(false);
  const [batteryError, setBatteryError] = useState(null);

  const [todayCostsKpi, setTodayCostsKpi] = useState(null);
  const [todayExportKpi, setTodayExportKpi] = useState(null);

  const [pricesRefreshLoading, setPricesRefreshLoading] = useState(false);
  const [pricesRefreshMessage, setPricesRefreshMessage] = useState(null);
  const [pricesRefreshError, setPricesRefreshError] = useState(null);
  const [alerts, setAlerts] = useState(null);
  const [comparison, setComparison] = useState(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [solarForecast, setSolarForecast] = useState(null);
  const [solarForecastLoading, setSolarForecastLoading] = useState(false);

  const todayDate = useMemo(() => getTodayDateStr(), []);

  const fetchDashboardSnapshot = useCallback(async (dateValue, options = {}) => {
    const { silent = false } = options;
    if (!silent) {
      setSelectedDatePricesLoading(true);
      setComparisonLoading(true);
      setSolarForecastLoading(true);
    }
    
    try {
      const data = await elektroappApi.getDashboardSnapshot(dateValue);
      
      // Update states from snapshot
      setPrices(data.prices?.prices || []);
      setSelectedDatePrices(data.prices?.prices || []);
      setCosts(data.costs?.points || []);
      setCostsSummary(data.costs?.summary || null);
      setCostsFromCache(Boolean(data.costs?.from_cache));
      setExportPoints(data.export?.points || []);
      setExportSummary(data.export?.summary || null);
      setExportFromCache(Boolean(data.export?.from_cache));
      setBatteryData(data.battery);
      setAlerts(data.alerts);
      setComparison(data.comparison);
      setSolarForecast(data.solar);
      
      if (dateValue === todayDate) {
        setTodayCostsKpi(data.costs?.summary || null);
        setTodayExportKpi(data.export?.summary || null);
      }
      
      setSelectedDatePricesError(null);
      setCostsError(null);
      setExportError(null);
    } catch (err) {
      console.error("Error fetching dashboard snapshot:", err);
      // Fallback to individual calls if snapshot fails? 
      // For now just set errors
      setSelectedDatePricesError(formatApiError(err, "Nepodařilo se načíst data dashboardu."));
    } finally {
      setSelectedDatePricesLoading(false);
      setComparisonLoading(false);
      setSolarForecastLoading(false);
    }
  }, [todayDate]);

  const refreshBattery = useCallback(async (options = {}) => {
    const { silent = false } = options;
    if (!silent) setBatteryLoading(true);
    setBatteryError(null);
    try {
      const data = await elektroappApi.getBattery();
      setBatteryData(data);
    } catch (err) {
      console.error("Error fetching battery data:", err);
      setBatteryError(buildInfluxError(err));
    } finally {
      if (!silent) setBatteryLoading(false);
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
      await fetchDashboardSnapshot(selectedDate);
      if (showConfig) {
        const cacheData = await elektroappApi.getCacheStatus();
        setCacheStatus(cacheData);
      }
    } catch (err) {
      console.error("Error refreshing prices:", err);
      setPricesRefreshError(formatApiError(err, "Obnoveni cen selhalo."));
    } finally {
      setPricesRefreshLoading(false);
    }
  }, [fetchDashboardSnapshot, selectedDate, showConfig]);

  // Initial load
  useEffect(() => {
    fetchDashboardSnapshot(selectedDate);
    
    elektroappApi.getConfig().then(setConfig).catch(e => console.error("Config fetch error", e));
    elektroappApi.getVersion().then(d => setVersion(d?.version)).catch(e => console.error("Version fetch error", e));
  }, [fetchDashboardSnapshot, selectedDate]);

  useEffect(() => {
    if (!showConfig) return;
    elektroappApi.getCacheStatus().then(setCacheStatus).catch(e => console.error("Cache status error", e));
  }, [showConfig]);

  // Auto Refresh
  useEffect(() => {
    if (!autoRefreshEnabled || !isPageVisible) return;
    const intervalId = setInterval(() => {
      fetchDashboardSnapshot(selectedDate, { silent: true });
    }, 600000); // 10 minutes
    return () => clearInterval(intervalId);
  }, [autoRefreshEnabled, isPageVisible, selectedDate, fetchDashboardSnapshot]);

  // Battery Fast Refresh (1 min)
  useEffect(() => {
    if (!autoRefreshEnabled || !isPageVisible) return;
    const intervalId = setInterval(() => {
      refreshBattery({ silent: true });
    }, 60000);
    return () => clearInterval(intervalId);
  }, [autoRefreshEnabled, isPageVisible, refreshBattery]);

  return {
    prices,
    selectedDatePrices,
    selectedDatePricesLoading,
    selectedDatePricesError,
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
    batteryData,
    batteryLoading,
    batteryError,
    refreshBattery: () => refreshBattery(),
    todayCostsKpi,
    todayExportKpi,
    refreshPrices,
    pricesRefreshLoading,
    pricesRefreshMessage,
    pricesRefreshError,
    alerts,
    comparison,
    comparisonLoading,
    solarForecast,
    solarForecastLoading,
  };
};
