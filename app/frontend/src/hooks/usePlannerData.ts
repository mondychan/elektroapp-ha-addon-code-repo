import { useCallback, useState } from "react";
import { elektroappApi, formatApiError } from "../api/elektroappApi";

export interface PlannerRecommendation {
  start_at: string;
  end_at: string;
  duration_minutes: number;
  average_price: number;
  slots: number[];
}

export const usePlannerData = () => {
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [plannerResults, setPlannerResults] = useState<PlannerRecommendation[]>([]);
  const [plannerNote, setPlannerNote] = useState<string | null>(null);
  const [plannerError, setPlannerError] = useState<string | null>(null);

  const loadPlanner = useCallback(async (durationValue: string | number) => {
    setPlannerLoading(true);
    setPlannerError(null);
    setPlannerNote(null);
    try {
      const data = await elektroappApi.getSchedule(Number(durationValue), 3);
      setPlannerResults(data?.recommendations || []);
      setPlannerNote(data?.note || null);
    } catch (err: any) {
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

  return {
    loadPlanner,
    plannerLoading,
    plannerResults,
    plannerNote,
    plannerError,
  };
};
