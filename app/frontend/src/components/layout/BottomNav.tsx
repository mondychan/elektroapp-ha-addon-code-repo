import React from "react";
import { motion } from "framer-motion";

interface BottomNavProps {
  pageMode: "overview" | "costs" | "battery" | "settings";
  setPageMode: (mode: "overview" | "costs" | "battery" | "settings") => void;
}

const BottomNav: React.FC<BottomNavProps> = ({ pageMode, setPageMode }) => {
  const items = [
    { id: "overview", label: "Přehled", icon: "📊" },
    { id: "costs", label: "Náklady", icon: "📈" },
    { id: "battery", label: "Baterie", icon: "🔋" },
    { id: "settings", label: "Nastavení", icon: "⚙️" },
  ] as const;

  return (
    <nav className="bottom-nav">
      {items.map((item) => (
        <button
          key={item.id}
          className={`bottom-nav-item ${pageMode === item.id ? "is-active" : ""}`}
          onClick={() => setPageMode(item.id)}
        >
          <span className="bottom-nav-icon">{item.icon}</span>
          <span className="bottom-nav-label">{item.label}</span>
          {pageMode === item.id && <motion.div layoutId="nav-pill" className="nav-pill" />}
        </button>
      ))}
    </nav>
  );
};

export default BottomNav;
