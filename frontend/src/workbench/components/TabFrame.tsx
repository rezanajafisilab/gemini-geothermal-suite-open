// The common layout of a tab page: the title row (the title at the left, then the design picker
// on one-design tabs, actions at the right), an optional lead line and toolbar, and the content.
// It also draws the shared states in place of the content: loading, server offline, error, and
// no designs yet.
//
//   <TabFrame scope="design" title="Energy over the year" actions={<AskButton … />}>
//     {design && <EnergyCharts design={design} />}
//   </TabFrame>
//
// scope "design" and "designs" read the workbench (useWorkbench) for their state; "none" tabs
// (Trace, Evidence) pass their own: status={resourceStatus(trace, trace.data?.runs.length === 0)}.

import type { ReactNode } from "react";

import { Plug, Retry, Spinner } from "../../components/Icons";
import { CopyCommand } from "../../components/StatusCards";
import type { ApiError } from "../api";
import { usesFixtures } from "../api";
import type { Resource } from "../resource";
import { useWorkbench, type WorkbenchView } from "../store";
import { TAB_GROUPS, TAB_META, useRoute, type TabId } from "../route";
import { fmtNum } from "../format";
import { DesignPicker } from "./DesignPicker";
import { ExportMenu } from "./ExportMenu";
import { ASK_FOR_DESIGN, EmptyState, type EmptyAction } from "./EmptyState";
import { PageSkeleton } from "./Skeleton";
import "./workbench.css";

export type FrameStatus =
  | { kind: "ready" }
  | { kind: "loading" }
  | { kind: "offline"; onRetry?: () => void }
  | { kind: "error"; message: string; onRetry?: () => void }
  | { kind: "empty"; title?: string; hint?: ReactNode; action?: EmptyAction | null; icon?: ReactNode };

const NO_DESIGNS = { title: "No designs in this chat yet", hint: "Ask for a design in the chat; it shows up here." };

/** The state of a tab that reads the conversation's designs. */
export function designsStatus(wb: WorkbenchView): FrameStatus {
  if (wb.workbench) return wb.designs.length ? { kind: "ready" } : { kind: "empty", ...NO_DESIGNS, action: ASK_FOR_DESIGN };
  if (wb.status === "error" && wb.error) return errorStatus(wb.error, wb.refresh);
  return { kind: "loading" };
}

/** The state of a tab that loads its own data (useResource); `empty` when it has nothing. */
export function resourceStatus(res: Resource<unknown>, empty = false, emptyState?: Omit<Extract<FrameStatus, { kind: "empty" }>, "kind">): FrameStatus {
  if (res.data != null) return empty ? { kind: "empty", ...emptyState } : { kind: "ready" };
  if (res.status === "error" && res.error) return errorStatus(res.error, res.reload);
  return { kind: "loading" };
}

function errorStatus(error: ApiError, retry: () => unknown): FrameStatus {
  const onRetry = () => void retry();
  return error.offline ? { kind: "offline", onRetry } : { kind: "error", message: error.message, onRetry };
}

interface Props {
  title: ReactNode;
  /** One line under the title. */
  lead?: ReactNode;
  /** "design": one design, with the picker; "designs": all of them; "none": pass `status`. */
  scope: "design" | "designs" | "none";
  /** Buttons at the right of the title row (shown once the content is). */
  actions?: ReactNode;
  /** A row under the title (filters, a segmented control), shown with the content. */
  toolbar?: ReactNode;
  /** Overrides the state worked out from the workbench. */
  status?: FrameStatus;
  className?: string;
  children?: ReactNode;
}

export function TabFrame({ title, lead, scope, actions, toolbar, status, className, children }: Props) {
  const wb = useWorkbench();
  const s: FrameStatus = status ?? (scope === "none" ? { kind: "ready" } : designsStatus(wb));
  const ready = s.kind === "ready";
  const staleError = scope !== "none" && wb.workbench && wb.error;
  const tab = useRoute().tab;
  const group = TAB_GROUPS.find((g) => g.tabs.includes(tab))?.caption;
  return (
    <section className={`wb-frame${className ? ` ${className}` : ""}`} aria-labelledby="wb-title">
      <header className="wb-head ta-rise">
        <div className="wb-head-main">
          <span className={`wb-tab-icon tab-${tab}`} aria-hidden="true">
            <TabIcon tab={tab} />
          </span>
          <div className="wb-titles">
            {group && (
              <span className="wb-eyebrow">
                {group}
                {TAB_META[tab] && <span className="wb-eyebrow-hint"> · {TAB_META[tab].hint}</span>}
              </span>
            )}
            <div className="wb-title-row">
              <h1 id="wb-title">{title}</h1>
              {usesFixtures() && (
                <span className="tag tag-amber" title="Made-up data from src/fixtures (fixture mode), not the server: see src/workbench/api.ts">
                  Fixture data
                </span>
              )}
              {scope !== "none" && wb.refreshing && (
                <span className="wb-refreshing" role="status" aria-label="Refreshing">
                  <Spinner size={16} />
                </span>
              )}
            </div>
            {lead && <p className="wb-lead">{lead}</p>}
          </div>
          {ready && (actions || scope === "design") && (
            <div className="wb-actions">
              {actions}
              {scope === "design" && <ExportMenu />}
            </div>
          )}
        </div>
        {scope === "design" && ready && <DesignBar />}
      </header>
      {staleError && (
        <div className="wb-strip" role="status">
          <span>
            <strong>Couldn't refresh.</strong> {wb.error!.offline ? "The agent server isn't answering" : wb.error!.message}; this is what it last sent.
          </span>
          <button type="button" className="link-btn" onClick={() => void wb.refresh()}>
            Try again
          </button>
        </div>
      )}
      {ready && toolbar}
      <FrameBody status={s}>{children}</FrameBody>
    </section>
  );
}

/** The design the tab shows: the picker, and its headline figures beside it. */
function DesignBar() {
  const wb = useWorkbench();
  const d = wb.selected;
  if (!d) return null;
  const e = d.economics;
  const figs: [string, string, string][] = [
    ["Cost of heat and cold", e.lcoe != null ? fmtNum(e.lcoe) : fmtNum(e.lcoh), "€/MWh"],
    ["CO₂ against gas", `−${fmtNum(Math.abs(e.co2_saving_pct))}`, "%"],
    ["Capital", fmtNum(e.capex_meur), "M€"],
    ["Heat covered", fmtNum((d.year.heat_coverage ?? 0) * 100), "%"],
  ];
  return (
    <div className="wb-dbar">
      <span className="wb-dbar-cap">Design</span>
      <DesignPicker />
      <dl className="wb-dbar-figs">
        {figs.map(([k, v, u]) => (
          <div key={k} className="wb-dbar-fig">
            <dt>{k}</dt>
            <dd>
              {v}
              <span className="u">{u}</span>
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}

const TAB_PATHS: Partial<Record<TabId, string>> = {
  design: "M2.5 12.5h3v-4h5v-5h3M5.5 8.5V5h2M10.5 3.5v9",
  energy: "M2.5 13.5h11M4 11V7M7 11V4M10 11V8M13 11V5.5",
  economics: "M11.6 4.4A4.2 4.2 0 1 0 11.6 11.6M2.8 6.9h6.4M2.8 9.1h6.4",
  compare: "M2.5 3.5h4.5v9H2.5zM9 3.5h4.5v9H9z",
  sensitivity: "M2.5 8h11M5 5v6M8 3.5v9M11 6v4",
  trace: "M3 3.5h10M3 8h7M3 12.5h4M11.5 11l1.5 1.5L15 10",
  evidence: "M8 1.9l5 1.8v3.9c0 3.1-2.1 5.4-5 6.5-2.9-1.1-5-3.4-5-6.5V3.7zM5.6 8l1.6 1.6 3.2-3.2",
};

function TabIcon({ tab }: { tab: TabId }) {
  return (
    <svg width="18" height="18" viewBox="0 0 16 16">
      <path d={TAB_PATHS[tab] ?? "M3 3h10v10H3z"} fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function FrameBody({ status, children }: { status: FrameStatus; children?: ReactNode }) {
  switch (status.kind) {
    case "ready":
      return <div className="wb-body">{children}</div>;
    case "loading":
      return <PageSkeleton />;
    case "offline":
      return <OfflineState onRetry={status.onRetry} />;
    case "error":
      return <ErrorState message={status.message} onRetry={status.onRetry} />;
    case "empty":
      return (
        <EmptyState
          title={status.title ?? NO_DESIGNS.title}
          hint={status.hint ?? NO_DESIGNS.hint}
          icon={status.icon}
          action={status.action === null ? undefined : (status.action ?? ASK_FOR_DESIGN)}
        />
      );
  }
}

const SERVER_CMD = "PYTHONPATH=src python -m gemini_agent.server";

/** Open the same page on the fixture data (?workbench=fixture), keeping the tab. */
function exampleHref(): string {
  if (typeof window === "undefined") return "?workbench=fixture";
  const q = new URLSearchParams(window.location.search);
  q.set("workbench", "fixture");
  return `?${q}${window.location.hash}`;
}

/** The server-offline notice, in the chat's OfflineBanner style. */
export function OfflineState({ onRetry }: { onRetry?: () => void }) {
  return (
    <section role="status" aria-label="Agent server not available" className="banner wb-state ta-rise">
      <div style={{ display: "flex", alignItems: "flex-start", gap: 10 }}>
        <span className="icon-box" style={{ background: "#FBEACB" }}>
          <Plug color="#8A5A00" />
        </span>
        <div style={{ display: "flex", flexDirection: "column", gap: 1, minWidth: 0 }}>
          <h3>The agent server isn't answering</h3>
          <p>The tabs read the conversation's designs from the Python server. Start it from the repo root:</p>
        </div>
      </div>
      <CopyCommand command={SERVER_CMD} />
      <div className="wb-state-actions">
        {onRetry && (
          <button type="button" className="btn btn-ink ta-btn ta-ink" style={{ fontSize: 14, padding: "8px 14px 8px 12px" }} onClick={onRetry}>
            <Retry />
            Try again
          </button>
        )}
        <a className="link-btn" style={{ fontSize: 13.5 }} href={exampleHref()}>
          Show example data instead
        </a>
      </div>
    </section>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <section role="alert" className="card error-card wb-state ta-rise">
      <strong style={{ fontSize: 15, fontWeight: 650 }}>This tab couldn't load</strong>
      <p className="error-msg">{message}</p>
      {onRetry && (
        <div className="wb-state-actions">
          <button type="button" className="btn btn-soft ta-btn ta-soft" style={{ fontSize: 14, padding: "8px 14px 8px 12px" }} onClick={onRetry}>
            <Retry />
            Try again
          </button>
        </div>
      )}
    </section>
  );
}
