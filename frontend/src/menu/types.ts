// What a right-click (context) menu is about, and what it lists. Each place in the app declares
// what was right-clicked as a MenuTarget (a design, a number in a reply, a unit of the plant, a
// day of a chart …), with the data and the local callbacks it has; the registry (registry.ts)
// turns a target into the menu's items. Nothing here computes a result: an item opens a tab,
// copies, or puts a question in the chat's composer for the user to send.

import type { TabId } from "../workbench/route";

export type IconName =
  | "design"
  | "energy"
  | "economics"
  | "compare"
  | "tray"
  | "untray"
  | "ask"
  | "whatif"
  | "failure"
  | "pdf"
  | "link"
  | "copy"
  | "sensitivity"
  | "edit"
  | "resend"
  | "cpu"
  | "gpu"
  | "flag"
  | "markdown"
  | "inspect"
  | "size"
  | "out"
  | "fit"
  | "full"
  | "day"
  | "series"
  | "price"
  | "sortAsc"
  | "sortDesc"
  | "filter"
  | "scenario"
  | "low"
  | "high"
  | "open"
  | "step"
  | "source"
  | "cut"
  | "paste"
  | "selectAll"
  | "remove"
  | "star";

export interface MenuItem {
  id: string;
  label: string;
  icon: IconName;
  /** A short tag at the right: "chat" when the item puts a question in the composer. */
  hint?: string;
  run: () => void | Promise<void>;
  disabled?: boolean;
  /** Why it is disabled, said beside it. */
  why?: string;
}

export interface MenuSection {
  items: MenuItem[];
}

export interface MenuModel {
  /** What was right-clicked, in the menu's head ("A1", "42.4 €/MWh", "Heat pump"). */
  title: string;
  /** A second line under the title (the design's code, the kind of thing). */
  sub?: string;
  sections: MenuSection[];
}

/** A design by any of its names: the tabs' id ("A1 · 1D-HP-EC-N1"), the chat's name ("A1") or its code. */
export interface DesignRef {
  id: string;
  /** "A1": how questions name it (else the id). */
  name?: string;
  /** Its code or description, for the menu's head. */
  sub?: string;
}

export type Side = "heat" | "cool";

export type MenuTarget =
  | {
      kind: "design";
      design: DesignRef;
      /** On the Compare tab: tick or untick it there, in place of a link. */
      tray?: { ticked: boolean; toggle: () => void; full?: boolean };
      /** On the Compare tab: show only the scenario it belongs to. */
      onlyScenario?: () => void;
    }
  | {
      kind: "number";
      /** As shown, with its unit: "42.4 €/MWh". */
      text: string;
      unit: string;
      /** The words around it, to say which number in a question. */
      before: string;
      after: string;
      /** Show the step that produced it (the chip's own click), when there is one. */
      showSource?: () => void;
    }
  | {
      kind: "message";
      text: string;
      /** Send it again as a new message. */
      resend: () => void;
    }
  | {
      kind: "answer";
      markdown: string;
      /** The text selected in it when the menu opened. */
      selection?: string;
    }
  | {
      kind: "unit";
      design: DesignRef;
      node: { id: string; type: string; label: string; doublet?: number };
      /** Its size today, MW (a what-if offers a bigger one). */
      sizeMw?: number;
      /** Pick it in the inspector. */
      inspect?: () => void;
      /** Open the edit panel on its field (the field's words, e.g. "Change its size"). */
      edit?: { label: string; run: () => void };
      /** Its line over the year on the Energy tab. */
      energy?: { side: Side; series: string | null };
      /** Its lines on the Economics tab (cost line items, as the design lists them). */
      costs?: string[];
    }
  | {
      kind: "canvas";
      fit?: () => void;
      fullScreen?: { on: boolean; toggle: () => void };
    }
  | {
      kind: "day";
      design: DesignRef;
      /** 0-based day of the year (0 = 1 January). */
      day: number;
      /** "12 January". */
      label: string;
      /** The day's values in words, for the clipboard. */
      values: string;
    }
  | {
      kind: "series";
      label: string;
      only: boolean;
      showOnly: () => void;
      showAll: () => void;
    }
  | {
      kind: "cost";
      design: DesignRef;
      side: "heat" | "cold";
      item: string;
      /** €/MWh as shown, and the total it is part of. */
      eur: string;
      total: string;
      /** Open the assumptions on the price this line uses. */
      price?: { label: string; open: () => void };
      /** The Sensitivity parameter that varies it. */
      sensParam?: string;
    }
  | {
      kind: "column";
      label: string;
      sort?: { dir: "asc" | "desc" | null; set: (dir: "asc" | "desc") => void };
      filter?: { label: string; on: boolean; toggle: () => void };
    }
  | {
      kind: "bar";
      design: string;
      param: string;
      label: string;
      /** The ends of its range, as shown ("20 €/MWh"). */
      low: string;
      high: string;
    }
  | {
      kind: "step";
      label: string;
      code?: string | null;
      /** What it reported, as JSON. */
      json: string;
      details?: { open: boolean; toggle: () => void };
    }
  | {
      kind: "source";
      title: string;
      citation: string;
      text?: string;
      open?: { label: string; run: () => void };
    }
  | {
      /** A text box: the browser's own menu is never shown, so this one cuts, copies and pastes. */
      kind: "text";
      field: HTMLInputElement | HTMLTextAreaElement;
      /** What was selected in it when the menu opened, and where. */
      selection: string;
      start: number;
      end: number;
      editable: boolean;
    }
  | {
      /** Text selected anywhere else on the page. */
      kind: "selection";
      text: string;
    }
  | {
      /** A chat in the sidebar. */
      kind: "chat";
      title: string;
      rename: () => void;
      remove: () => void;
    }
  | {
      /** A link that no target nearer the pointer claimed. */
      kind: "link";
      href: string;
      text: string;
    };

export type MenuKind = MenuTarget["kind"];

/**
 * What the menu's items do, outside this module. The app's own actions (ops.ts); the tests pass
 * fakes and check what an item called.
 */
export interface MenuOps {
  /** Put a question in the chat's composer (not sent) and show the chat. */
  ask: (text: string) => void;
  /** Open a design in a one-design tab, bringing it into the tabs first when it isn't. */
  openDesign: (ref: string, tab: TabId) => void | Promise<void>;
  /** The Compare tab with these designs ticked, side by side. */
  compare: (refs: string[]) => void;
  /** Tick it in the Compare tray (the tab shows the tray). */
  addToTray: (ref: string) => void;
  /** The chat's recommended design, by its tabs' id, or null. */
  recommended: () => string | null;
  /** Whether two names are the same design. */
  same: (a: string, b: string) => boolean;
  /** The PDF report can be made here (a server, a real chat). */
  canReport: () => boolean;
  downloadReport: (ref: string) => void | Promise<void>;
  /** The design's brine loop as a GEMINI project file (GET /api/gemini.json). */
  downloadGemini: (ref: string) => void | Promise<void>;
  /** The figures the permits and the SDE++ application ask for, as a PDF (GET /api/permits.pdf). */
  downloadPermits: (ref: string) => void | Promise<void>;
  /** A link to the design on a tab, for the clipboard. */
  linkFor: (tab: TabId, ref: string | null) => string;
  copy: (text: string, what: string) => void | Promise<void>;
  /** The Design tab's player on this day (1-based, as the player counts). */
  jumpToDay: (ref: string, day: number) => void;
  /** The Energy tab on one side, showing one series. */
  showEnergy: (ref: string, side: Side, series: string | null) => void;
  /** The Economics tab with these cost lines picked out. */
  showCosts: (ref: string, items: string[]) => void;
  /** The Sensitivity tab with this parameter added (for this design, when given). */
  vary: (param: string, ref?: string) => void;
  /** Where the models run, and whether a reply is being written. */
  device: () => { device: "auto" | "cpu"; gpu: boolean; busy: boolean };
  /** Switch where the models run (the header's switch). */
  setDevice: (d: "auto" | "cpu") => void;
  /** Cut, copy, paste or select all in a text box, as its own menu would. */
  editText: (t: Extract<MenuTarget, { kind: "text" }>, action: "cut" | "copy" | "paste" | "selectAll") => void | Promise<void>;
  /** Follow a link here, or in a new tab. */
  openLink: (href: string, newTab: boolean) => void;
  /** Whether a design is on the user's shortlist, and its own name (null: none). */
  meta: (ref: string) => { starred: boolean; name: string | null } | null;
  /** Star a design or take it off the shortlist. */
  star: (ref: string, on: boolean) => void | Promise<void>;
  /** Give a design a name of the user's (a small box where the menu was). */
  rename: (ref: string, current: string | null) => void;
}
