import React from "react";
import { IconBulb, IconChevronRight } from "./icons";

interface StatusStripProps {
  statusLabel: string;
  currentPrice: string;
  nextCheapWindow?: string | null;
  recommendation?: string | null;
  onOpenRecommendations?: () => void;
}

const StatusStrip: React.FC<StatusStripProps> = ({
  statusLabel,
  currentPrice,
  nextCheapWindow,
  recommendation,
  onOpenRecommendations,
}) => (
  <section className="status-strip" aria-label="Aktuální stav">
    <div className="status-strip__badge">{statusLabel}</div>
    <div className="status-strip__price">
      <strong>Aktuální cena: {currentPrice}</strong>
      <span>{nextCheapWindow || "Další levné okno není k dispozici."}</span>
    </div>
    <button type="button" className="status-strip__tip" onClick={onOpenRecommendations}>
      <span className="status-strip__tip-icon" aria-hidden="true"><IconBulb size={18} /></span>
      <span>
        <strong>Tip</strong>
        <small>{recommendation || "Doporučení zatím není k dispozici."}</small>
      </span>
      <IconChevronRight size={18} />
    </button>
  </section>
);

export default StatusStrip;
