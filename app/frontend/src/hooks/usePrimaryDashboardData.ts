import { useCallback, useEffect, useMemo, useState } from "react";
import { buildInfluxError, elektroappApi, formatApiError } from "../api/elektroappApi";
import { getTodayDateStr } from "./dashboardUtils";
import {
  Config,
  BatteryData,
  CostsKpi,
  ExportKpi,
  SolarForecast,
  RecommendationsResponse,
  DiagnosticsSummary,
  RawPriceEntry,
} from "../types/elektroapp";

interface UsePrimaryDashboardDataProps {
  selectedDate: string;
  showConfig: boolean;
  autoRefreshEnabled: boolean;
  isPageVisible: boolean;
}

export const usePrimaryDashboardData = ({ selectedDate, showConfig, autoRefreshEnabled, isPageVisible }: UsePrimaryDashboardDataProps) => {
  const [prices, setPrices] = useState<RawPriceEntry[]>([]);
  const [selectedDatePrices, setSelectedDatePrices] = useState<RawPriceEntry[]>([]);
  const [selectedDatePricesLoading, setSelectedDatePricesLoading] = useState(false);
  const [selectedDatePricesError, setSelectedDatePricesError] = useState<string | null>(null);
  
  const [config, setConfig] = useState<Config | null>(null);
  const [cacheStatus, setCacheStatus] = useState<any>(null);
  const [version, setVersion] = useState<string | null>(null);

  const [costs, setCosts] = useState<any[]>([]);
  const [costsSummary, setCostsSummary] = useState<CostsKpi | null>(null);
  const [costsError, setCostsError] = useState<string | null>(null);
  const [costsFromCache, setCostsFromCache] = useState(false);
  const [costsCacheFallback] = useState(false);

  const [exportPoints, setExportPoints] = useState<any[]>([]);
  const [exportSummary, setExportSummary] = useState<ExportKpi | null>(null);
  const [exportError, setExportError] = useState<string | null>(null);
  const [exportFromCache, setExportFromCache] = useState(false);
  const [exportCacheFallback] = useState(false);

  const [batteryData, setBatteryData] = useState<BatteryData | null>(null);
  const [batteryLoading, setBatteryLoading] = useState(false);
  const [batteryError, setBatteryError] = useState<string | null>(null);

  const [todayCostsKpi, setTodayCostsKpi] = useState<CostsKpi | null>(null);
  const [todayExportKpi, setTodayExportKpi] = useState<ExportKpi | null>(null);

  const [pricesRefreshLoading, setPricesRefreshLoading] = useState(false);
  const [pricesRefreshMessage, setPricesRefreshMessage] = useState<string | null>(null);
  const [pricesRefreshError, setPricesRefreshError] = useState<string | null>(null);
  const [alerts, setAlerts] = useState<any>(null);
  const [comparison, setComparison] = useState<any>(null);
  const [comparisonLoading, setComparisonLoading] = useState(false);
  const [solarForecast, setSolarForecast] = useState<SolarForecast | null>(null);
  const [solarForecastLoading, setSolarForecastLoading] = useState(false);
  const [recommendations, setRecommendations] = useState<RecommendationsResponse | null>(null);
  const [diagnosticsSummary, setDiagnosticsSummary] = useState<DiagnosticsSummary | null>(null);

  const todayDate = useMemo(() => getTodayDateStr(), []);

  const refreshConfig = useCallback(async () => {
    const [configData, versionData] = await Promise.all([
      elektroappApi.getConfig(),
      elektroappApi.getVersion(),
    ]);
    setConfig(configData);
    setVersion(versionData?.version ?? null);
    return configData;
  }, []);

  const fetchDashboardSnapshot = useCallback(async (dateValue: string, options: { silent?: boolean } = {}) => {
    const { silent = false } = options;
    if (!silent) {
      setSelectedDatePricesLoading(true);
      setComparisonLoading(true);
      setSolarForecastLoading(true);
    }
    
    try {
      const data = await elektroappApi.getDashboardSnapshot(dateValue);
      
      const legacyPrices = Array.isArray(data.prices) ? data.prices : data.prices?.prices;
      const overviewPrices = data.overview_prices?.prices || legacyPrices || [
        ...(data.today_prices || []),
        ...(data.tomorrow_prices || []),
      ];
      setPrices(overviewPrices || []);
      setSelectedDatePrices(data.selected_date_prices || legacyPrices || []);
      setCosts(data.costs?.points || []);
      setCostsSummary(data.costs?.summary || null);
      setCostsFromCache(Boolean(data.costs?.from_cache));
      setExportPoints(data.export?.points || []);
      setExportSummary(data.export?.summary || null);
      setExportFromCache(Boolean(data.export?.from_cache));
      setBatteryData(data.battery || null);
      setAlerts(data.alerts);
      setComparison(data.comparison);
      setSolarForecast(data.solar || null);
      setRecommendations(data.recommendations || null);
      setDiagnosticsSummary(data.diagnostics_summary || null);
      
      if (dateValue === todayDate) {
        setTodayCostsKpi(data.costs?.summary || null);
        setTodayExportKpi(data.export?.summary || null);
      }
      
      setSelectedDatePricesError(null);
      setCostsError(null);
      setExportError(null);
    } catch (err) {
      const errMsg = formatApiError(err, "Nepodařilo se načíst data dashboardu.");
      setSelectedDatePricesError(errMsg);
      setCostsError(errMsg);
      setExportError(errMsg);
      setBatteryError(errMsg);
    } finally {
      setSelectedDatePricesLoading(false);
      setComparisonLoading(false);
      setSolarForecastLoading(false);
      setBatteryLoading(false);
    }
  }, [todayDate]);

  const refreshBattery = useCallback(async (options: { silent?: boolean } = {}) => {
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
      const resp = await elektroappApi.refreshPrices({});
      const refreshed = resp?.refreshed || [];
      const summary = refreshed.map((item: any) => `${item.date}: ${item.count} zaznamu`).join(" | ");
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

    refreshConfig().catch(e => console.error("Config fetch error", e));
  }, [fetchDashboardSnapshot, refreshConfig, selectedDate]);

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
    recommendations,
    diagnosticsSummary,
    refreshConfig,
  };
};
