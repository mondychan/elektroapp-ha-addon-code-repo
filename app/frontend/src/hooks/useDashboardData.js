import { useInsightsData } from "./useInsightsData";
import { usePlannerData } from "./usePlannerData";
import { usePrimaryDashboardData } from "./usePrimaryDashboardData";

export { getTodayDateStr, normalizeEnergyBalanceAnchor, shiftEnergyBalanceAnchor } from "./dashboardUtils";

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
