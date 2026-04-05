import { useInsightsData } from "./useInsightsData";
import { usePlannerData } from "./usePlannerData";
import { usePrimaryDashboardData } from "./usePrimaryDashboardData";

export { getTodayDateStr, normalizeEnergyBalanceAnchor, shiftEnergyBalanceAnchor } from "./dashboardUtils";

interface UseDashboardDataProps {
  selectedDate: string;
  selectedMonth: string;
  showConfig: boolean;
  showFeesHistory: boolean;
  showBilling: boolean;
  billingMode: "month" | "year";
  billingMonth: string;
  billingYear: string;
  pageMode: "overview" | "detail";
  energyBalancePeriod: "week" | "month" | "year";
  energyBalanceAnchor: string;
  heatmapMonth: string;
  heatmapMetric: "buy" | "sell";
  autoRefreshEnabled: boolean;
  isPageVisible: boolean;
}

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
}: UseDashboardDataProps) => {
  const primary = usePrimaryDashboardData({
    selectedDate,
    showConfig,
    autoRefreshEnabled,
    isPageVisible,
  });

  const insights = useInsightsData({
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
  });

  const planner = usePlannerData();

  return {
    ...primary,
    ...insights,
    ...planner,
  };
};
