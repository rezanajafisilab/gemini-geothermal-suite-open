// Number formats of the Economics tab: fixed decimals (so a column of €/MWh lines up and adds
// up), a real minus, thousands separators.

/** 20 → "20.0", −0.25 → "−0.3" (the labels of a waterfall, which add up at this precision). */
export function eur(v: number, digits = 1): string {
  if (!Number.isFinite(v)) return "–";
  const s = Math.abs(v).toLocaleString("en-US", { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return v < 0 && Number(s.replace(/,/g, "")) !== 0 ? `−${s}` : s;
}

/** M€: one decimal, two below 0.1 so a small item doesn't read as nothing (0.04 → "0.04"). */
export function meur(v: number): string {
  return Math.abs(v) > 0 && Math.abs(v) < 0.095 ? eur(v, 2) : eur(v);
}

/** With its sign: "+18.7", "−1.5". */
export function signed(v: number, digits = 1): string {
  if (!Number.isFinite(v)) return "–";
  const s = eur(Math.abs(v), digits);
  return Number(s.replace(/,/g, "")) === 0 ? s : `${v < 0 ? "−" : "+"}${s}`;
}

/** Tonnes, whole: 14,422.9 → "14,423". */
export function tonnes(v: number): string {
  return Number.isFinite(v) ? Math.round(v).toLocaleString("en-US") : "–";
}
