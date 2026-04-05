import React from "react";
import { motion } from "framer-motion";

interface BottomNavProps {
  pageMode: "overview" | "detail";
  setPageMode: (mode: "overview" | "detail") => void;
}

const BottomNav: React.FC<BottomNavProps> = ({ pageMode, setPageMode }) => {
  return (
    <nav className="bottom-nav">
      <button 
        className={`bottom-nav-item ${pageMode === "overview" ? "is-active" : ""}`}
        onClick={() => setPageMode("overview")}
      >
        <span className="bottom-nav-icon">📊</span>
        <span className="bottom-nav-label">Přehled</span>
        {pageMode === "overview" && <motion.div layoutId="nav-pill" className="nav-pill" />}
      </button>
      
      <button 
        className={`bottom-nav-item ${pageMode === "detail" ? "is-active" : ""}`}
        onClick={() => setPageMode("detail")}
      >
        <span className="bottom-nav-icon">📈</span>
        <span className="bottom-nav-label">Detail</span>
        {pageMode === "detail" && <motion.div layoutId="nav-pill" className="nav-pill" />}
      </button>
    </nav>
  );
};

export default BottomNav;
