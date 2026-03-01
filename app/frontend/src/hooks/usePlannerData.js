import { useCallback, useState } from "react";
import { elektroappApi, formatApiError } from "../api/elektroappApi";

export const usePlannerData = () => {
  const [plannerLoading, setPlannerLoading] = useState(false);
  const [plannerResults, setPlannerResults] = useState([]);
  const [plannerNote, setPlannerNote] = useState(null);
  const [plannerError, setPlannerError] = useState(null);

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

  return {
    loadPlanner,
    plannerLoading,
    plannerResults,
    plannerNote,
    plannerError,
  };
};
