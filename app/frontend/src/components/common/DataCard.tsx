import React from "react";
import { motion, AnimatePresence } from "framer-motion";

interface DataCardProps {
  title?: string;
  headerActions?: React.ReactNode;
  loading?: boolean;
  error?: any;
  empty?: boolean;
  emptyMessage?: string;
  className?: string;
  children: React.ReactNode;
}

const DataCard: React.FC<DataCardProps> = ({
  title,
  headerActions,
  loading,
  error,
  empty,
  emptyMessage = "Žádná data nejsou k dispozici.",
  className = "",
  children,
}) => {
  const errorMessage = typeof error === "string" ? error : error?.message || "Došlo k chybě při načítání.";

  return (
    <div className={`card ${className}`.trim()}>
      {title && (
        <div className="card-header">
          <h3>{title}</h3>
          {headerActions}
        </div>
      )}
      
      <div className="card-body" style={{ position: "relative", minHeight: loading ? "150px" : "auto" }}>
        <AnimatePresence mode="wait">
          {loading ? (
            <motion.div
              key="loading"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="data-state-container loading-state"
            >
              <div className="spinner" />
              <p>Načítám...</p>
            </motion.div>
          ) : error ? (
            <motion.div
              key="error"
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="data-state-container error-state"
            >
              <svg viewBox="0 0 24 24" width="48" height="48" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10" />
                <line x1="12" y1="8" x2="12" y2="12" />
                <line x1="12" y1="16" x2="12.01" y2="16" />
              </svg>
              <p>{errorMessage}</p>
            </motion.div>
          ) : empty ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="data-state-container empty-state"
            >
              <p>{emptyMessage}</p>
            </motion.div>
          ) : (
            <motion.div
              key="content"
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.3 }}
            >
              {children}
            </motion.div>
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default DataCard;
