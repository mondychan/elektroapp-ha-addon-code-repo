import React from "react";

interface SectionCardProps {
  title: string;
  eyebrow?: string;
  actions?: React.ReactNode;
  className?: string;
  children: React.ReactNode;
}

const SectionCard: React.FC<SectionCardProps> = ({ title, eyebrow, actions, className = "", children }) => (
  <section className={`modern-section-card ${className}`.trim()}>
    <div className="modern-section-card__header">
      <div>
        <h2>{title}</h2>
        {eyebrow ? <p>{eyebrow}</p> : null}
      </div>
      {actions ? <div className="modern-section-card__actions">{actions}</div> : null}
    </div>
    <div className="modern-section-card__body">{children}</div>
  </section>
);

export default SectionCard;
