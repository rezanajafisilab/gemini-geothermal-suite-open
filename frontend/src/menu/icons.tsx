// The menus' icons: 16 × 16 strokes in the current colour, one per kind of action, drawn to sit
// with the app's own (components/Icons.tsx).

import type { IconName } from "./types";

const PATHS: Record<IconName, string> = {
  // A plant: a frame with two units and a pipe.
  design: "M2.5 3.5h11v9h-11zM5 7.5h2.5v2.5H5zM9.5 6h2v4h-2zM7.5 8.75h2",
  // A daily curve over a baseline.
  energy: "M2 12.5h12M2.5 10.5c1.6-4.5 2.6-6 3.6-6s1.6 4 2.6 4 1.6-3 2.6-3 1.6 2.4 2.2 3.6",
  // A euro sign.
  economics: "M11.4 4.2A4.3 4.3 0 1 0 11.4 11.8M2.8 6.9h6.6M2.8 9.1h6.6",
  // Two bars side by side.
  compare: "M3 13.5V6.5h3.4v7M9.6 13.5v-11H13v11M2 13.5h12",
  // A tray with an arrow in.
  tray: "M2.5 9.5v3.5h11V9.5M8 2.5v7M5.4 7l2.6 2.6L10.6 7",
  // A tray with an arrow out.
  untray: "M2.5 9.5v3.5h11V9.5M8 9.5v-7M5.4 5L8 2.4 10.6 5",
  // A speech bubble.
  ask: "M2.5 3.5h11v7.2H7.6L4.6 13.2v-2.5H2.5z",
  // Sliders.
  whatif: "M2.5 5h7M12.5 5h1M2.5 11h1M6.5 11h7M11 3.3v3.4M5 9.3v3.4",
  // A bolt.
  failure: "M9 1.8 3.8 9h3.6L6.8 14.2 12.2 6.8H8.6z",
  // A page with a fold and an arrow down.
  pdf: "M4 1.8h5.4L12.5 5v9.2H4zM9.2 2v3.2h3.2M8.2 7.2v4.6M6.2 9.9l2 2 2-2",
  // Two links.
  link: "M6.8 9.2a2.6 2.6 0 0 0 3.7 0l2-2a2.6 2.6 0 0 0-3.7-3.7l-.8.8M9.2 6.8a2.6 2.6 0 0 0-3.7 0l-2 2a2.6 2.6 0 0 0 3.7 3.7l.8-.8",
  // Two sheets.
  copy: "M5.5 5.5h7.5v8H5.5zM3 10.5V2.5h7.5",
  // A star.
  star: "M8 1.9l1.8 3.7 4.1.6-3 2.9.7 4.1L8 11.3l-3.6 1.9.7-4.1-3-2.9 4.1-.6z",
  // A bin.
  remove: "M3 4.5h10M6.2 4.5V3h3.6v1.5M4.4 4.5l.7 9h5.8l.7-9M6.8 7v4.5M9.2 7v4.5",
  // Scissors.
  cut: "M4.6 12.4a1.9 1.9 0 1 1-1.9-1.9 1.9 1.9 0 0 1 1.9 1.9zM13.2 12.4a1.9 1.9 0 1 1-1.9-1.9 1.9 1.9 0 0 1 1.9 1.9zM4.1 11 11.8 2.5M11.9 11 4.2 2.5",
  // A clipboard with a sheet.
  paste: "M5.5 2.8h5v2h-5zM4.2 3.8H3v10.4h10V3.8h-1.2M5.6 8h4.8M5.6 10.6h3.4",
  // A dashed frame round a block.
  selectAll: "M2.5 2.5h2M6.5 2.5h3M11.5 2.5h2v2M13.5 6.5v3M13.5 11.5v2h-2M9.5 13.5h-3M4.5 13.5h-2v-2M2.5 9.5v-3M2.5 4.5v-2M5.5 5.5h5v5h-5z",
  // A tornado: bars of shrinking width round a spine.
  sensitivity: "M8 2v12M3 4h10M4.5 7h7M5.6 10h4.8M6.6 13h2.8",
  // A pencil.
  edit: "M10.8 2.7l2.5 2.5-7.6 7.6-3.2.7.7-3.2zM9.4 4.1l2.5 2.5",
  // A turning arrow.
  resend: "M13 8a5 5 0 1 1-1.5-3.6M13 2.6v2.6h-2.6",
  // A chip.
  cpu: "M4.5 4.5h7v7h-7zM6.5 6.5h3v3h-3zM6.5 2v2.5M9.5 2v2.5M6.5 11.5V14M9.5 11.5V14M2 6.5h2.5M2 9.5h2.5M11.5 6.5H14M11.5 9.5H14",
  // A card with a fan.
  gpu: "M1.8 4.5h12.4v7H1.8zM6.5 8a1.6 1.6 0 1 0 0 .01M10.5 6.6h2M10.5 9.4h2M3.5 11.5v2",
  // A flag.
  flag: "M3.5 14.2V2.3M3.5 2.8h8.4l-1.8 3 1.8 3H3.5",
  // The Markdown mark.
  markdown: "M1.8 4h12.4v8H1.8zM4 10V6l1.8 2 1.8-2v4M10.6 6v4M9.2 8.6l1.4 1.4 1.4-1.4",
  // A magnifier.
  inspect: "M7 2.8a4.2 4.2 0 1 0 0 8.4 4.2 4.2 0 0 0 0-8.4zM10.1 10.1l3.6 3.6",
  // Arrows apart.
  size: "M2.5 8h11M2.5 8l2.4-2.4M2.5 8l2.4 2.4M13.5 8l-2.4-2.4M13.5 8l-2.4 2.4",
  // A unit, struck out.
  out: "M3 4h10v8H3zM3 4l10 8",
  // A frame round a centre.
  fit: "M2 5.5V2h3.5M10.5 2H14v3.5M14 10.5V14h-3.5M5.5 14H2v-3.5M6 6h4v4H6z",
  // Corners outward.
  full: "M2.5 6V2.5H6M10 2.5h3.5V6M13.5 10v3.5H10M6 13.5H2.5V10",
  // A calendar.
  day: "M2.5 3.5h11v10h-11zM2.5 6.5h11M5.5 2v3M10.5 2v3M7.2 9.6h1.6v1.6H7.2z",
  // Three stacked bands.
  series: "M2 12.5h12M2.5 10c2-1 3.5-1.6 5.5-1.6s3.5.6 5.5 1.6M2.5 7c2-1.2 3.5-2 5.5-2s3.5.8 5.5 2",
  // A tag.
  price: "M2.3 8.7V2.3h6.4l5 5-6.4 6.4zM5.4 5.4h.01",
  // Bars rising, an arrow up.
  sortAsc: "M3 13V9.5M6 13V7M9 13V4.5M12 6V2.5M10.6 3.9 12 2.5l1.4 1.4",
  // Bars falling, an arrow down.
  sortDesc: "M3 13V4.5M6 13V7M9 13V9.5M12 10v3.5M10.6 12.1l1.4 1.4 1.4-1.4",
  // A funnel.
  filter: "M2.5 3h11l-4.3 5.2v4.6l-2.4 1.2V8.2z",
  // Stacked layers.
  scenario: "M8 2.2 14 5.3 8 8.4 2 5.3zM2 8.1l6 3.1 6-3.1M2 10.9 8 14l6-3.1",
  // A bar from the spine to the left.
  low: "M10 2.5v11M3 6.5h7v3H3z",
  // A bar from the spine to the right.
  high: "M6 2.5v11M6 6.5h7v3H6z",
  // A box with an arrow out.
  open: "M8.5 2.5h5v5M13.5 2.5 7.5 8.5M11.5 9.5v4h-9v-9h4",
  // Steps.
  step: "M2.5 13.5h3.6V10h3.7V6.5h3.7V2.5",
  // A page with lines.
  source: "M4 1.8h5l3 3V14H4zM9 1.8V5h3M6 8h4M6 10.5h4",
};

export function MenuIcon({ name, size = 16 }: { name: IconName; size?: number }) {
  return (
    <svg className="cm-icon" width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d={PATHS[name]} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** The ⋯ of the "more actions" buttons. */
export function DotsIcon({ size = 16 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <circle cx="3.6" cy="8" r="1.35" fill="currentColor" />
      <circle cx="8" cy="8" r="1.35" fill="currentColor" />
      <circle cx="12.4" cy="8" r="1.35" fill="currentColor" />
    </svg>
  );
}
