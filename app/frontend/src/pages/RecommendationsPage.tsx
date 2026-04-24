import React, { useEffect } from "react";
import { motion } from "framer-motion";
import RecommendationCard from "../components/RecommendationCard";
import PlannerCard from "../components/PlannerCard";
import DataCard from "../components/common/DataCard";

interface RecommendationsPageProps {
  recommendations?: any;
  plannerDuration: string;
  setPlannerDuration: (dur: string) => void;
  handleLoadPlanner: (dur?: string) => Promise<void>;
  finalPlannerError: any;
  plannerLoading: boolean;
  plannerNote: string | null;
  plannerResults: any[];
}

const RecommendationsPage: React.FC<RecommendationsPageProps> = ({
  recommendations,
  plannerDuration,
  setPlannerDuration,
  handleLoadPlanner,
  finalPlannerError,
  plannerLoading,
  plannerNote,
  plannerResults,
}) => {
  const autoLoadedRef = React.useRef(false);

  useEffect(() => {
    if (!autoLoadedRef.current && !plannerLoading && !plannerNote && !finalPlannerError && plannerResults.length === 0) {
      autoLoadedRef.current = true;
      handleLoadPlanner();
    }
  }, [finalPlannerError, handleLoadPlanner, plannerLoading, plannerNote, plannerResults.length]);

  return (
    <motion.div
      initial={{ opacity: 0, x: 20 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -20 }}
      transition={{ duration: 0.3 }}
      className="page-recommendations"
    >
      <section className="section">
        <DataCard title="Doporučení">
          <RecommendationCard recommendations={recommendations} />
        </DataCard>
      </section>

      <section className="section">
        <PlannerCard
          plannerDuration={plannerDuration}
          setPlannerDuration={setPlannerDuration}
          loadPlanner={handleLoadPlanner}
          plannerError={finalPlannerError}
          plannerLoading={plannerLoading}
          plannerNote={plannerNote}
          plannerResults={plannerResults}
        />
      </section>
    </motion.div>
  );
};

export default RecommendationsPage;
