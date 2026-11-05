// Number and label formatting shared by the chat cards and the tabs.

import type { Design } from "./types";

/** 1 decimal by default, integers without one, thousands with separators; "–" when not finite. */
export function fmtNum(v: number, digits = 1): string {
  if (!Number.isFinite(v)) return "–";
  if (Math.abs(v) >= 1000) return Math.round(v).toLocaleString("en-US");
  const r = Math.round(v * 10 ** digits) / 10 ** digits;
  return Number.isInteger(r) ? String(r) : r.toFixed(digits);
}

/** With its sign, a real minus: "+3.2", "−10", "0". */
export function fmtSigned(v: number, digits = 1): string {
  if (!Number.isFinite(v)) return "–";
  const s = fmtNum(Math.abs(v), digits);
  if (s === "0") return "0";
  return `${v < 0 ? "−" : "+"}${s}`;
}

/** A fraction as a percentage: 0.962 → "96.2%". */
export function fmtPct(fraction: number, digits = 1): string {
  return Number.isFinite(fraction) ? `${fmtNum(fraction * 100, digits)}%` : "–";
}

/** How many of a design's checks failed. */
export function failedChecks(d: Design): number {
  return d.checks.filter((c) => !c.passed).length;
}

/**
 * A failed check in a few words ("breaks the 50–300 m³/h flow cap"), and what on the inputs card
 * would fix it. The names are the verifier's own (verifier.verify_plant), not the user's words.
 */
export function checkWords(name: string): { short: string; fix: string } {
  let m = /^Flow (\d+)-(\d+) m3\/h/.exec(name);
  if (m) return { short: `breaks the ${m[1]}–${m[2]} m³/h flow cap`, fix: `Keep the flow cap at ${m[2]} m³/h or less and the lowest flow at ${m[1]} or more (inputs card, Limits).` };
  m = /^Brine cooled by at most (\d+(?:\.\d+)?) K/.exec(name);
  if (m) return { short: `misses the ${m[1]} K cap`, fix: `Keep “Brine cooled by at most” at ${m[1]} K (inputs card, Limits), or allow a heat pump so the brine need not be cooled further.` };
  m = /^At most (\d+) days/.exec(name);
  if (m) return { short: `runs more than ${m[1]} days`, fix: `Keep the operating days at ${m[1]} or fewer, or give each doublet ${365 - Number(m[1])} days off (inputs card, Limits and Maintenance).` };
  m = /^Heat at (\d+) °C every day/.exec(name);
  if (m) return { short: "short of heat on some days", fix: `Allow a boiler or heat pump (Your request, Leave out), allow more doublets, or keep the supply at ${m[1]} °C.` };
  m = /^Cold at (\d+) °C every day/.exec(name);
  if (m) return { short: "short of cold on some days", fix: `Allow the chillers (Your request, Leave out), or keep the cooling supply at ${m[1]} °C.` };
  if (/^Daily energy balance/.test(name)) return { short: "does not balance", fix: "The plant model could not balance some days: a model fault, not your inputs. Try other inputs on the card and report it." };
  if (/Carnot|COP below one/.test(name)) return { short: "breaks physics (a model fault)", fix: "A machine works better than physics allows: a model fault, not your inputs. Report it." };
  if (/temperature cross/.test(name)) return { short: "brine too cold for the exchanger", fix: "The brine reaches the exchanger colder than the heating return: a warmer reservoir (Reservoir and wells) or a colder heating return (Networks)." };
  if (/^One to three doublets/.test(name)) return { short: "has more than 3 doublets", fix: "Choose 1 to 3 doublets (inputs card, Your request)." };
  if (/^Cold water reaches the producer/.test(name)) return { short: "cools its producer too soon", fix: "Less brine per doublet (a lower flow cap), more doublets sharing it, or a thicker aquifer (Reservoir and wells)." };
  if (/bubble point/.test(name)) return { short: "ESP too deep (gas)", fix: "Less gas in the brine (Brine and gas) or a higher reservoir pressure, or a lower flow cap." };
  if (/SodM/.test(name)) return { short: "injects above SodM's limit", fix: "A lower flow cap, two injectors per doublet, or more permeable rock (Reservoir and wells)." };
  if (/^Production equals injection/.test(name)) return { short: "produces more than it injects", fix: "A model fault: report it." };
  return { short: `fails “${name}”`, fix: "" };
}

/** A design's status in words: "verified", "misses the 40 K cap", "fails 2 checks". */
export function statusWords(failed: string[], verified: boolean): string {
  if (verified && !failed.length) return "verified";
  if (failed.length === 1) return checkWords(failed[0]).short;
  if (failed.length > 1) return `fails ${failed.length} checks`;
  return "checks not run";
}

/** "what-if −10 °C" for a reservoir shift. */
export function whatIfText(deltaC: number): string {
  return `what-if ${fmtSigned(deltaC)} °C`;
}

/** What a what-if changed, in words: its label ("heating return temperature 50 °C"), else the reservoir shift. */
export function changeText(d: Pick<Design, "id" | "code" | "change_label" | "reservoir_delta_c">): string {
  if (d.change_label) return d.change_label;
  // Older ids were "<code> · <change>"; ids now lead with the design's name ("A1 · <code>").
  const cut = d.id.indexOf(" · ");
  if (cut > 0 && d.id.slice(0, cut) === d.code) return d.id.slice(cut + 3);
  return d.reservoir_delta_c ? `reservoir ${fmtSigned(d.reservoir_delta_c)} °C` : "";
}

/** Where a design came from, as the picker tags it: "agent", "your design", "what-if: reservoir −5 K". */
export function originLabel(d: Design): string {
  if (d.origin === "user") return "your design";
  if (d.origin === "what_if") {
    const what = changeText(d);
    return what ? `what-if: ${what}` : whatIfText(d.reservoir_delta_c);
  }
  return "agent";
}

/** A design id in two parts: its code and what a what-if changed ("2D-HP-AB", "reservoir -5 K"). */
export function idParts(d: Pick<Design, "id" | "code" | "change_label" | "reservoir_delta_c" | "origin">): { code: string; what: string } {
  return { code: d.code, what: d.origin === "what_if" || d.id !== d.code ? changeText(d) : "" };
}

/** "A1 Deep doublet with absorption cascade (what-if: reservoir −5 K)", for labels and questions. */
export function designTitle(d: Design): string {
  return d.origin === "what_if" ? `${d.code} ${d.name} (${originLabel(d)})` : `${d.code} ${d.name}`;
}
