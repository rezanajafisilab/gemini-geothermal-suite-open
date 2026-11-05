// Links into the Compare tab with designs ticked: #compare/<ids joined by "|", URI-encoded>.
// The chat emits them ("compare A1 and A11 side by side"); the tab reads the route's `design`
// field (parseHash decodes it), ticks those designs and opens the side by side.

import { hrefFor } from "../../workbench/route";

/** The separator between design ids in a compare link (ids never hold one). */
export const ID_SEPARATOR = "|";

/** "#compare/A1%20%C2%B7%201D-HP-EC-N1%7CA11%20%C2%B7%201D-HP-AB" for ["A1 · 1D-HP-EC-N1", "A11 · 1D-HP-AB"]; "#compare" for none. */
export function compareHref(ids: string[]): string {
  const clean = [...new Set(ids.map((id) => id.trim()).filter(Boolean))];
  return hrefFor("compare", clean.length ? clean.join(ID_SEPARATOR) : null);
}

/** The ids a compare route names (its decoded `design` field), in order, without repeats. */
export function compareIds(param: string | null | undefined): string[] {
  if (!param) return [];
  return [...new Set(param.split(ID_SEPARATOR).map((id) => id.trim()).filter(Boolean))];
}
