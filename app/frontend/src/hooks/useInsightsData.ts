import { useCallback, useEffect, useState } from "react";
import { buildInfluxError, elektroappApi, formatApiError } from "../api/elektroappApi";
import { normalizeEnergyBalanceAnchor } from "./dashboardUtils";

import { PageMode } from "../components/layout/AppHeader";

interface UseInsightsDataProps {
  selectedMonth: string;
  showConfig: boolean;
  showFeesHistory: boolean;
  showBilling: boolean;
  billingMode: "month" | "year";
  billingMonth: string;
  billingYear: string;
  pageMode: PageMode;
  energyBalancePeriod: "week" | "month" | "year";
  energyBalanceAnchor: string;
  heatmapMonth: string;
  heatmapMetric: "buy" | "sell";
}

export const useInsightsData = ({
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
}: UseInsightsDataProps) => {
  const [monthlySummary, setMonthlySummary] = useState<any[]>([]);
  const [monthlyTotals, setMonthlyTotals] = useState<any>(null);
  const [monthlyError, setMonthlyError] = useState<string | null>(null);

  const [billingData, setBillingData] = useState<any>(null);
  const [billingLoading, setBillingLoading] = useState(false);
  const [billingError, setBillingError] = useState<string | null>(null);

  const [energyBalanceData, setEnergyBalanceData] = useState<any>(null);
  const [energyBalanceLoading, setEnergyBalanceLoading] = useState(false);
  const [energyBalanceError, setEnergyBalanceError] = useState<string | null>(null);

  const [heatmapData, setHeatmapData] = useState<any>(null);
  const [heatmapLoading, setHeatmapLoading] = useState(false);
  const [heatmapError, setHeatmapError] = useState<string | null>(null);

  const [feesHistory, setFeesHistory] = useState<any[]>([]);
  const [feesHistoryLoading, setFeesHistoryLoading] = useState(false);
  const [feesHistoryError, setFeesHistoryError] = useState<string | null>(null);

  const fetchEnergyBalance = useCallback(async () => {
    setEnergyBalanceLoading(true);
    setEnergyBalanceError(null);
    const anchor = normalizeEnergyBalanceAnchor(energyBalancePeriod, energyBalanceAnchor);
    try {
      const data = await (elektroappApi as any).getEnergyBalance(energyBalancePeriod, anchor);
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
      const data = await (elektroappApi as any).getHistoryHeatmap(heatmapMonth, heatmapMetric);
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

  const saveFeesHistory = useCallback(async (historyPayload: any) => {
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
    const request = billingMode === "year" ? (elektroappApi as any).getBillingYear(billingYear) : (elektroappApi as any).getBillingMonth(billingMonth);
    request
      .then((data: any) => setBillingData(data))
      .catch((err: any) => {
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
    if (pageMode !== "costs") return;
    fetchEnergyBalance();
  }, [pageMode, fetchEnergyBalance]);

  useEffect(() => {
    if (pageMode !== "costs") return;
    fetchHeatmap();
  }, [pageMode, fetchHeatmap]);

  return {
    monthlySummary,
    monthlyTotals,
    monthlyError,
    billingData,
    billingLoading,
    billingError,
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
  };
};
