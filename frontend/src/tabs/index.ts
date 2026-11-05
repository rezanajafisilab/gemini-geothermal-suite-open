// The tab pages, one per route, each loaded when first opened. This is the only place that knows
// them: a tab's code lives in its own files (src/tabs/<Name>Tab.tsx and .css, and a folder
// src/tabs/<name>/ for its parts), so tabs never need to edit App.tsx or Header.tsx.

import { lazy, type ComponentType, type LazyExoticComponent } from "react";

import type { TabId } from "../workbench/route";

export const TAB_PAGES: Record<Exclude<TabId, "chat">, LazyExoticComponent<ComponentType>> = {
  design: lazy(() => import("./DesignTab")),
  energy: lazy(() => import("./EnergyTab")),
  economics: lazy(() => import("./EconomicsTab")),
  compare: lazy(() => import("./CompareTab")),
  sensitivity: lazy(() => import("./SensitivityTab")),
  trace: lazy(() => import("./TraceTab")),
  evidence: lazy(() => import("./EvidenceTab")),
};
