import React from "react";

interface SectionCardProps {
  title: string;
  eyebrow?: string;
  actions?: React.ReactNode;
  className?: string;
  hideHeader?: boolean;
  children: React.ReactNode;
}

const SectionCard: React.FC<SectionCardProps> = ({ title, eyebrow, actions, className = "", hideHeader = false, children }) => (
  <section className={`modern-section-card ${hideHeader ? "modern-section-card--no-header" : ""} ${className}`.trim()} aria-label={hideHeader ? title : undefined}>
    {!hideHeader ? (
      <div className="modern-section-card__header">
        <div>
          <h2>{title}</h2>
          {eyebrow ? <p>{eyebrow}</p> : null}
        </div>
        {actions ? <div className="modern-section-card__actions">{actions}</div> : null}
      </div>
    ) : null}
    <div className="modern-section-card__body">{children}</div>
  </section>
);

export default SectionCard;
