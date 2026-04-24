import React from "react";
import { motion } from "framer-motion";
import dashboardIcon from "@material-symbols/svg-500/rounded/dashboard.svg";
import monitoringIcon from "@material-symbols/svg-500/rounded/monitoring.svg";
import recommendationsIcon from "@material-symbols/svg-500/rounded/lightbulb_2.svg";
import batteryIcon from "@material-symbols/svg-500/rounded/battery_charging_full.svg";
import heatPumpIcon from "@material-symbols/svg-500/rounded/heat_pump.svg";
import pndIcon from "@material-symbols/svg-500/rounded/receipt_long.svg";
import settingsIcon from "@material-symbols/svg-500/rounded/settings.svg";

interface BottomNavProps {
  pageMode: "overview" | "costs" | "recommendations" | "battery" | "hp" | "pnd" | "settings";
  setPageMode: (mode: "overview" | "costs" | "recommendations" | "battery" | "hp" | "pnd" | "settings") => void;
}

const BottomNav: React.FC<BottomNavProps> = ({ pageMode, setPageMode }) => {
  const items = [
    { id: "overview", label: "Přehled", icon: dashboardIcon },
    { id: "costs", label: "Detail", icon: monitoringIcon },
    { id: "recommendations", label: "Dop.", icon: recommendationsIcon },
    { id: "battery", label: "Baterie", icon: batteryIcon },
    { id: "hp", label: "HP", icon: heatPumpIcon },
    { id: "pnd", label: "PND", icon: pndIcon },
    { id: "settings", label: "Nastavení", icon: settingsIcon },
  ] as const;

  return (
    <nav className="bottom-nav">
      {items.map((item) => (
        <button
          key={item.id}
          className={`bottom-nav-item ${pageMode === item.id ? "is-active" : ""}`}
          onClick={() => setPageMode(item.id)}
        >
          <span
            className="bottom-nav-icon"
            aria-hidden="true"
            style={{ WebkitMaskImage: `url(${item.icon})`, maskImage: `url(${item.icon})` }}
          />
          <span className="bottom-nav-label">{item.label}</span>
          {pageMode === item.id && <motion.div layoutId="nav-pill" className="nav-pill" />}
        </button>
      ))}
    </nav>
  );
};

export default BottomNav;
