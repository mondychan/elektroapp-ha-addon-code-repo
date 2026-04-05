import React from "react";
import { motion, AnimatePresence } from "framer-motion";

interface AlertBannerProps {
  alerts: {
    current_price: number;
    min_price_today: number;
    max_price_today: number;
    is_cheap_now: boolean;
    is_expensive_now: boolean;
    next_cheap_start?: string;
    next_cheap_price?: number;
    recommendation: string;
  } | null;
}

const AlertBanner: React.FC<AlertBannerProps> = ({ alerts }) => {
  if (!alerts) return null;

  const { is_cheap_now, is_expensive_now, recommendation, next_cheap_start, next_cheap_price } = alerts;
  
  let statusClass = "alert-banner--neutral";
  if (is_cheap_now) statusClass = "alert-banner--success";
  if (is_expensive_now) statusClass = "alert-banner--warning";

  return (
    <AnimatePresence>
      <motion.div 
        className={`alert-banner ${statusClass}`}
        initial={{ height: 0, opacity: 0 }}
        animate={{ height: "auto", opacity: 1 }}
        exit={{ height: 0, opacity: 0 }}
      >
        <div className="alert-banner-content">
          <div className="alert-banner-main">
            <span className="alert-banner-badge">{recommendation}</span>
            <span className="alert-banner-price">Aktuální cena: <strong>{alerts.current_price?.toFixed(2) ?? "-"} Kč</strong></span>
          </div>
          
          {!is_cheap_now && next_cheap_start && (
            <div className="alert-banner-detail">
              Další levné okno začne v <strong>{next_cheap_start.split(" ")[1]}</strong> ({next_cheap_price?.toFixed(2)} Kč)
            </div>
          )}
          
          {is_cheap_now && (
            <div className="alert-banner-detail">
              Nyní je ideální čas pro zapnutí náročných spotřebičů.
            </div>
          )}
        </div>
      </motion.div>
    </AnimatePresence>
  );
};

export default AlertBanner;
