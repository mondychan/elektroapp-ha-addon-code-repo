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

  const todayDate = useMemo(() => getTodayDateStr(), []);

  const fetchPrices = useCallback(async () => {
    try {
      const data = await elektroappApi.getPrices();
      setPrices(data?.prices || []);
    } catch (err) {
      console.error("Error fetching prices:", err);
    }
  }, []);

  const fetchSelectedDatePrices = useCallback(
    async (dateValue, options = {}) => {
      const { reset = true } = options;
      if (reset) {
        setSelectedDatePrices([]);
        setSelectedDatePricesError(null);
      }
      setSelectedDatePricesLoading(true);
      try {
        const data = await elektroappApi.getPrices(dateValue);
        setSelectedDatePrices(data?.prices || []);
      } catch (err) {
        console.error("Error fetching selected-date prices:", err);
        setSelectedDatePricesError(formatApiError(err, "Nepodarilo se nacist ceny pro vybrany den."));
      } finally {
        setSelectedDatePricesLoading(false);
      }
    },
    []
  );

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
      await fetchSelectedDatePrices(selectedDate, { reset: false });
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
  }, [fetchCosts, fetchExport, fetchPrices, fetchSelectedDatePrices, fetchTodayKpiSummaries, selectedDate, showConfig, todayDate]);

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
    fetchSelectedDatePrices(selectedDate, { reset: true });
  }, [fetchSelectedDatePrices, selectedDate]);

  useEffect(() => {
    if (!autoRefreshEnabled || !isPageVisible) return;
    const refresh = () => {
      fetchPrices();
      fetchSelectedDatePrices(selectedDate, { reset: false });
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
  }, [autoRefreshEnabled, isPageVisible, selectedDate, fetchCosts, fetchExport, fetchPrices, fetchSelectedDatePrices, fetchTodayKpiSummaries, refreshBattery]);

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
  };
};
