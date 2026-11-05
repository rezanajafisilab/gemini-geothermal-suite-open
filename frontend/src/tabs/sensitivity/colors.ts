// Colours of the Sensitivity tab, by the job they do (the dataviz method).
//
// - Tornado (two series, low and high end of each range): violet and teal, the prototype's pair,
//   validated on the white card (scripts/validate_palette.js: both checks pass, ≥ 3:1).
// - Spider (one line per parameter, identity): the reference categorical palette in its fixed
//   order, validated as adjacent pairs on white (worst CVD ΔE 9.1, normal-vision 19.6); three of
//   its slots sit below 3:1, so every line also has a legend entry and a tooltip row. A colour
//   follows the parameter (assignSlots), never its rank; past eight, lines are grey.
// - Histogram (one series): the accent, lighter outside P10–P90 (emphasis, not a new hue).
// - Heatmap (magnitude): one teal hue, light to dark.

export const LOW = "#7856c4";
export const HIGH = "#0b8fa0";

export const SERIES = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];
export const OVERFLOW = "#9aa5ab";

export function slotColor(slot: number | undefined): string {
  return slot != null && slot >= 0 && slot < SERIES.length ? SERIES[slot] : OVERFLOW;
}

export const BAND = "#0b8fa0";
export const OUT_OF_BAND = "#a9d9df";

/** The heatmap ramp: share 0..1 → a teal step, light to dark, and the ink that reads on it. */
const RAMP = ["#eef7f8", "#d3ecef", "#b1dde2", "#86c9d1", "#58b0bb", "#2f939f", "#137784", "#0a5c66"];

export function rampColor(share: number): { bg: string; ink: string } {
  const i = Math.max(0, Math.min(RAMP.length - 1, Math.round(share * (RAMP.length - 1))));
  return { bg: RAMP[i], ink: i >= 4 ? "#ffffff" : "#11181c" };
}

export const RAMP_GRADIENT = `linear-gradient(90deg, ${RAMP.join(", ")})`;
