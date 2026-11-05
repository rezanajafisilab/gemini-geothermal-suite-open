// Small line icons for the inputs card: one per page and one per row (a parameter group), drawn
// on a 16-px grid in the current colour. Pages and rows get a tint each (CSS: .ic-ico.t-*), so a
// glance tells heat from cold, rock from brine, limits from prices.

import type { ReactNode } from "react";

const P = { fill: "none", stroke: "currentColor", strokeWidth: 1.5, strokeLinecap: "round", strokeLinejoin: "round" } as const;

const SHAPES: Record<string, ReactNode> = {
  chart: <path {...P} d="M2.5 13.5h11M4.5 11V8M8 11V4.5M11.5 11V6.5" />,
  flame: <path {...P} d="M8 14c2.6 0 4.3-1.8 4.3-4.2 0-2.6-2.2-3.9-2.8-6.3-1.2 1-1.6 2.3-1.6 3.4C7 6.1 6.5 5 6.4 4 4.8 5.4 3.7 7.3 3.7 9.8 3.7 12.2 5.4 14 8 14Z" />,
  snow: <path {...P} d="M8 2v12M2.8 5l10.4 6M2.8 11l10.4-6M6.4 2.9 8 4.3l1.6-1.4M6.4 13.1 8 11.7l1.6 1.4" />,
  layers: <path {...P} d="M8 2.5 14 5.5 8 8.5 2 5.5Zm-6 5.5 6 3 6-3M2 10.5l6 3 6-3" />,
  thermo: <path {...P} d="M9.5 9.3V3.6a1.5 1.5 0 0 0-3 0v5.7a2.9 2.9 0 1 0 3 0ZM8 6.5v4.2" />,
  well: <path {...P} d="M5 2.5v8.5M11 2.5v8.5M3 2.5h10M8 6v7.5M5.8 11.3 8 13.5l2.2-2.2" />,
  drop: <path {...P} d="M8 2.2c2.2 2.8 4.2 5 4.2 7.4a4.2 4.2 0 0 1-8.4 0c0-2.4 2-4.6 4.2-7.4Z" />,
  bubbles: (
    <g {...P}>
      <circle cx="5.5" cy="10" r="2.8" />
      <circle cx="10.8" cy="6.2" r="2" />
      <circle cx="9.8" cy="12" r="1.2" />
    </g>
  ),
  gauge: <path {...P} d="M2.6 11.5a5.6 5.6 0 1 1 10.8 0M8 9.5l2.6-3" />,
  flow: <path {...P} d="M5 13V3M2.8 5.2 5 3l2.2 2.2M11 3v10M8.8 10.8 11 13l2.2-2.2" />,
  calendar: <path {...P} d="M2.5 4h11v9.5h-11zM2.5 7h11M5.5 2.5v3M10.5 2.5v3" />,
  wrench: <path {...P} d="M10.2 2.6a3 3 0 0 0-3.6 3.9L2.8 10.3a1.2 1.2 0 0 0 1.7 1.7L8.3 8.2a3 3 0 0 0 3.9-3.6l-1.8 1.8-1.6-.4-.4-1.6Z" />,
  pipe: <path {...P} d="M2 6h7a3 3 0 0 1 3 3v5M2 10h7M9 10v4" />,
  loss: <path {...P} d="M2 6h8M2 10h8M12.5 4.5v7M10.8 9.8l1.7 1.7 1.7-1.7" />,
  euro: <path {...P} d="M11.8 4.2a4.4 4.4 0 1 0 0 7.6M3 7h6M3 9.2h6" />,
  target: (
    <g {...P}>
      <circle cx="8" cy="8" r="5.6" />
      <circle cx="8" cy="8" r="2.6" />
      <circle cx="8" cy="8" r=".4" />
    </g>
  ),
  sun: <path {...P} d="M8 5.2a2.8 2.8 0 1 1 0 5.6 2.8 2.8 0 0 1 0-5.6ZM8 1.8v1.4M8 12.8v1.4M1.8 8h1.4M12.8 8h1.4M3.6 3.6l1 1M11.4 11.4l1 1M3.6 12.4l1-1M11.4 4.6l1-1" />,
  sliders: <path {...P} d="M3 4.5h10M3 11.5h10M6 3v3M10.5 10v3" />,
  info: (
    <g {...P}>
      <circle cx="8" cy="8" r="6" />
      <path d="M8 7.3v3.6M8 5.2v.1" />
    </g>
  ),
  check: (
    <g {...P}>
      <circle cx="8" cy="8" r="6" />
      <path d="m5.4 8.2 1.8 1.8 3.4-3.6" />
    </g>
  ),
  pen: <path {...P} d="M10.6 2.6l2.8 2.8-7.6 7.6-3.4.6.6-3.4z" />,
  link: <path {...P} d="M6.6 9.4 9.4 6.6M7.4 4.6l1-1a2.3 2.3 0 0 1 3.2 3.2l-1 1M8.6 11.4l-1 1a2.3 2.3 0 0 1-3.2-3.2l1-1" />,
  // The plant's units (the Maintenance section): two flows passing, a cycle, a bolt.
  exchange: <path {...P} d="M2.5 5.5h11M10.5 2.5l3 3-3 3M13.5 10.5h-11M5.5 7.5l-3 3 3 3" />,
  cycle: <path {...P} d="M12.6 6.2A5 5 0 0 0 3.6 5.4M3.4 9.8a5 5 0 0 0 9 .8M12.8 2.8v3.6H9.2M3.2 13.2V9.6h3.6" />,
  bolt: <path {...P} d="M9.2 1.8 3.8 9.2h4.1l-1.1 5 5.4-7.4H8.1z" />,
  plus: <path {...P} d="M8 3.5v9M3.5 8h9" />,
  close: <path {...P} d="m4.5 4.5 7 7m0-7-7 7" />,
  // Back to the default (5 Nov): an arrow turning back.
  undo: <path {...P} d="M4 6.5h5.6a3 3 0 0 1 0 6H6.5M6.4 3.9 3.8 6.5l2.6 2.6" />,
};

/** Each page's icon and tint. */
export const PAGE_ICON: Record<string, [string, string]> = {
  demand: ["chart", "amber"],
  reservoir: ["layers", "earth"],
  brine: ["drop", "teal"],
  limits: ["gauge", "violet"],
  networks: ["pipe", "red"],
  prices: ["euro", "green"],
  request: ["target", "ink"],
  review: ["check", "teal"],
};

/** Each row's icon and tint, by its label; else its page's. */
export const ROW_ICON: Record<string, [string, string]> = {
  Heat: ["flame", "heat"],
  Cold: ["snow", "cold"],
  Scaled: ["sliders", "amber"],
  Aquifer: ["layers", "earth"],
  Aquifers: ["layers", "earth"],
  "Second aquifer": ["layers", "earth"],
  Temperature: ["thermo", "heat"],
  "Wells drilled into": ["well", "earth"],
  Brine: ["drop", "teal"],
  "Heat capacity": ["thermo", "teal"],
  "The brine's gas": ["bubbles", "teal"],
  "Relaxed by you": ["sliders", "violet"],
  "Doublets and flow": ["flow", "violet"],
  "Operating days": ["calendar", "violet"],
  "Doublet stops": ["wrench", "violet"],
  "Units' yearly service": ["wrench", "violet"],
  "Heating network": ["pipe", "heat"],
  "Cooling network": ["pipe", "cold"],
  "Network heat losses": ["loss", "red"],
  Prices: ["euro", "green"],
  "Design for": ["target", "ink"],
  "Free cooling, solar, heat store": ["sun", "amber"],
  "Not modelled": ["info", "ink"],
};

export function Ico({ name, tint, size = 16, boxed = true }: { name: string; tint?: string; size?: number; boxed?: boolean }) {
  const svg = (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      {SHAPES[name] ?? SHAPES.info}
    </svg>
  );
  return boxed ? <span className={`ic-ico t-${tint ?? "ink"}`}>{svg}</span> : svg;
}
