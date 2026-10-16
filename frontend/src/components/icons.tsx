// A handful of line icons drawn inline, so no icon library is needed. They
// are decorative: the text next to each one says what it means.

import type { ReactNode } from "react";

function Icon({ children, size = 18 }: { children: ReactNode; size?: number }) {
  return (
    <svg
      aria-hidden
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.8}
      strokeLinecap="round"
      strokeLinejoin="round"
      className="shrink-0"
    >
      {children}
    </svg>
  );
}

type Props = { size?: number };

export const ArrowRight = (p: Props) => (
  <Icon {...p}>
    <path d="M5 12h14M13 6l6 6-6 6" />
  </Icon>
);
export const ArrowDown = (p: Props) => (
  <Icon {...p}>
    <path d="M12 5v14M6 13l6 6 6-6" />
  </Icon>
);
export const Sparkle = (p: Props) => (
  <Icon {...p}>
    <path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z" />
    <path d="M19 15l.7 2 2 .7-2 .7-.7 2-.7-2-2-.7 2-.7z" />
  </Icon>
);
export const Search = (p: Props) => (
  <Icon {...p}>
    <circle cx="11" cy="11" r="6.5" />
    <path d="M16 16l4.5 4.5" />
  </Icon>
);
export const MapIcon = (p: Props) => (
  <Icon {...p}>
    <path d="M3 6.5l6-2.5 6 2.5 6-2.5v13.5l-6 2.5-6-2.5-6 2.5z" />
    <path d="M9 4v13.5M15 6.5V20" />
  </Icon>
);
export const Files = (p: Props) => (
  <Icon {...p}>
    <path d="M8 3h7l4 4v11a1 1 0 0 1-1 1H8a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z" />
    <path d="M15 3v4h4M4 7v13a1 1 0 0 0 1 1h10" />
  </Icon>
);
export const Campus = (p: Props) => (
  <Icon {...p}>
    <path d="M2 9l10-5 10 5-10 5z" />
    <path d="M6 11v5c0 1.5 2.7 3 6 3s6-1.5 6-3v-5M22 9v6" />
  </Icon>
);
export const Euro = (p: Props) => (
  <Icon {...p}>
    <path d="M18 6.5A7 7 0 1 0 18 17.5M4 10h10M4 14h10" />
  </Icon>
);
export const Train = (p: Props) => (
  <Icon {...p}>
    <rect x="5" y="3" width="14" height="14" rx="3" />
    <path d="M5 10h14M8.5 21l2-4M15.5 21l-2-4" />
    <circle cx="9" cy="13.5" r=".6" />
    <circle cx="15" cy="13.5" r=".6" />
  </Icon>
);

export const Crosshair = (p: Props) => (
  <Icon {...p}>
    <circle cx="12" cy="12" r="7" />
    <path d="M12 2v4M12 18v4M2 12h4M18 12h4" />
    <circle cx="12" cy="12" r="1.5" fill="currentColor" />
  </Icon>
);

export const Plus = (p: Props) => (
  <Icon {...p}>
    <path d="M12 5v14M5 12h14" />
  </Icon>
);

export const Minus = (p: Props) => (
  <Icon {...p}>
    <path d="M5 12h14" />
  </Icon>
);

export const ChevronLeft = (p: Props) => (
  <Icon {...p}>
    <path d="M15 6l-6 6 6 6" />
  </Icon>
);

export const ChevronRight = (p: Props) => (
  <Icon {...p}>
    <path d="M9 6l6 6-6 6" />
  </Icon>
);
