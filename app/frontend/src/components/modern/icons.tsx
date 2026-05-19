import React from "react";

type IconProps = {
  size?: number;
  className?: string;
};

const IconBase = ({
  size = 22,
  className,
  children,
}: IconProps & { children: React.ReactNode }) => (
  <svg
    className={className}
    width={size}
    height={size}
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    strokeWidth="2"
    strokeLinecap="round"
    strokeLinejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    {children}
  </svg>
);

export const IconBolt = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M13 2 4 14h7l-1 8 10-13h-7l1-7Z" fill="currentColor" stroke="none" />
  </IconBase>
);

export const IconMenu = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M4 7h16" />
    <path d="M4 12h16" />
    <path d="M4 17h16" />
  </IconBase>
);

export const IconX = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M18 6 6 18" />
    <path d="m6 6 12 12" />
  </IconBase>
);

export const IconPin = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M12 17v5" />
    <path d="m5 17 14 0" />
    <path d="M8 3h8l-1 7 3 4H6l3-4-1-7Z" />
  </IconBase>
);

export const IconPinOff = (props: IconProps) => (
  <IconBase {...props}>
    <path d="m3 3 18 18" />
    <path d="M12 17v5" />
    <path d="m5 17 10 0" />
    <path d="M8 3h8l-.55 3.85" />
    <path d="m14 10 4 4H8" />
  </IconBase>
);

export const IconRefresh = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M20 12a8 8 0 1 1-2.34-5.66" />
    <path d="M20 4v6h-6" />
  </IconBase>
);

export const IconGrid = (props: IconProps) => (
  <IconBase {...props}>
    <rect x="4" y="4" width="6" height="6" rx="1" />
    <rect x="14" y="4" width="6" height="6" rx="1" />
    <rect x="4" y="14" width="6" height="6" rx="1" />
    <rect x="14" y="14" width="6" height="6" rx="1" />
  </IconBase>
);

export const IconChart = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M4 19V5" />
    <path d="M4 19h16" />
    <path d="m7 15 4-4 3 3 5-7" />
  </IconBase>
);

export const IconBulb = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M9 18h6" />
    <path d="M10 22h4" />
    <path d="M8.5 14.5A6 6 0 1 1 15.5 14c-.8.6-1.5 1.6-1.5 2.5h-4c0-.8-.6-1.5-1.5-2Z" />
  </IconBase>
);

export const IconBattery = (props: IconProps) => (
  <IconBase {...props}>
    <rect x="5" y="6" width="12" height="15" rx="2" />
    <path d="M9 3h4" />
    <path d="M9 11h4" />
    <path d="M9 15h4" />
  </IconBase>
);

export const IconSun = (props: IconProps) => (
  <IconBase {...props}>
    <circle cx="12" cy="12" r="4" />
    <path d="M12 2v2" />
    <path d="M12 20v2" />
    <path d="m4.93 4.93 1.41 1.41" />
    <path d="m17.66 17.66 1.41 1.41" />
    <path d="M2 12h2" />
    <path d="M20 12h2" />
    <path d="m6.34 17.66-1.41 1.41" />
    <path d="m19.07 4.93-1.41 1.41" />
  </IconBase>
);

export const IconSunset = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M4 18h16" />
    <path d="M6 14a6 6 0 0 1 12 0" />
    <path d="M12 4v4" />
    <path d="m4.93 8.93 1.41 1.41" />
    <path d="m19.07 8.93-1.41 1.41" />
  </IconBase>
);

export const IconPie = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M12 3v9h9" />
    <path d="M20.5 15.5A9 9 0 1 1 8.5 3.5" />
    <path d="M14 3.2A9 9 0 0 1 20.8 10" />
  </IconBase>
);

export const IconTrend = (props: IconProps) => (
  <IconBase {...props}>
    <path d="m4 16 5-5 4 4 7-8" />
    <path d="M15 7h5v5" />
  </IconBase>
);

export const IconHome = (props: IconProps) => (
  <IconBase {...props}>
    <path d="m3 11 9-8 9 8" />
    <path d="M5 10v10h14V10" />
    <path d="M9 20v-6h6v6" />
  </IconBase>
);

export const IconGridTower = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M12 3v18" />
    <path d="M8 21h8" />
    <path d="m6 8 6-5 6 5" />
    <path d="m7 13 5-4 5 4" />
    <path d="M9 17h6" />
  </IconBase>
);

export const IconExport = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M4 12h15" />
    <path d="m13 6 6 6-6 6" />
  </IconBase>
);

export const IconSettings = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Z" />
    <path d="M19.4 15a1.7 1.7 0 0 0 .34 1.87l.05.05a2 2 0 1 1-2.83 2.83l-.05-.05A1.7 1.7 0 0 0 15 19.36a1.7 1.7 0 0 0-1 .58V20a2 2 0 1 1-4 0v-.07a1.7 1.7 0 0 0-1-.58 1.7 1.7 0 0 0-1.87.34l-.05.05a2 2 0 1 1-2.83-2.83l.05-.05A1.7 1.7 0 0 0 4.64 15a1.7 1.7 0 0 0-.58-1H4a2 2 0 1 1 0-4h.07a1.7 1.7 0 0 0 .58-1 1.7 1.7 0 0 0-.34-1.87l-.05-.05a2 2 0 1 1 2.83-2.83l.05.05A1.7 1.7 0 0 0 9 4.64a1.7 1.7 0 0 0 1-.58V4a2 2 0 1 1 4 0v.07a1.7 1.7 0 0 0 1 .58 1.7 1.7 0 0 0 1.87-.34l.05-.05a2 2 0 1 1 2.83 2.83l-.05.05A1.7 1.7 0 0 0 19.36 9c.22.34.42.68.58 1H20a2 2 0 1 1 0 4h-.07a1.7 1.7 0 0 0-.53 1Z" />
  </IconBase>
);

export const IconCalendar = (props: IconProps) => (
  <IconBase {...props}>
    <rect x="4" y="5" width="16" height="16" rx="2" />
    <path d="M8 3v4" />
    <path d="M16 3v4" />
    <path d="M4 10h16" />
  </IconBase>
);

export const IconChevronRight = (props: IconProps) => (
  <IconBase {...props}>
    <path d="m9 18 6-6-6-6" />
  </IconBase>
);

export const IconPlug = (props: IconProps) => (
  <IconBase {...props}>
    <path d="M9 7V3" />
    <path d="M15 7V3" />
    <path d="M7 7h10v4a5 5 0 0 1-10 0V7Z" />
    <path d="M12 16v5" />
  </IconBase>
);

export const IconTable = (props: IconProps) => (
  <IconBase {...props}>
    <rect x="4" y="5" width="16" height="14" rx="1" />
    <path d="M4 10h16" />
    <path d="M9 5v14" />
    <path d="M15 5v14" />
  </IconBase>
);
