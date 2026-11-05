import { Fragment, useEffect, useLayoutEffect, useRef, useState, type KeyboardEvent } from "react";

import type { Device, Health, Size } from "../agent/client";
import { DEVICE_NAMES, answerRole, hasGpu, profileOf, roleRows } from "../agent/models";
import type { Totals } from "../agent/reducer";
import { onDeviceRequest, publishDevice } from "../menu/device";
import { TAB_GROUPS, TAB_META, go, hrefFor, type TabId } from "../workbench/route";
import { Chevron } from "./Icons";
import { LogoSmall } from "./Logo";
import { ModelsChip } from "./ModelsChip";

interface Props {
  /** The screen on show (the route's tab). */
  tab: TabId;
  /** The design the one-design tabs show: their links carry it (#energy/A1). */
  designId: string | null;
  /** Name the reasoning model as the answerer (the agent decides per message; off by default). */
  reasoning?: boolean;
  /** Where the models run (the GPU | CPU switch); applies from the next run. */
  device: Device;
  onDevice: (d: Device) => void;
  /** Which model (the Auto | 9B | 4B switch; auto: the first that fits); applies from the next run. */
  size?: Size;
  onSize?: (s: Size) => void;
  /** A run is streaming: the switch waits until the reply has finished. */
  running: boolean;
  projectName: string;
  exampleData: boolean;
  health: Health;
  totals: Totals;
  onMenu: () => void;
  onHome: () => void;
  /** The tab on show was clicked again: refresh it. */
  onReselect?: (tab: TabId) => void;
}

/** Two letters for the project's avatar. */
function initialsOf(name: string): string {
  const words = name.split(/[\s_-]+/).filter((w) => /[\p{L}\p{N}]/u.test(w));
  if (!words.length) return "P";
  return (words.length > 1 ? words[0][0] + words[1][0] : words[0].slice(0, 2)).toUpperCase();
}

export function fmtTokens(n: number): string {
  return n.toLocaleString("en-US");
}

/** Energy in Wh: "0.04 Wh", "0.9 Wh", "12 Wh". */
export function fmtWh(wh: number): string {
  return `${wh < 0.1 ? wh.toFixed(2) : wh < 10 ? wh.toFixed(1) : Math.round(wh)} Wh`;
}

export function fmtSeconds(s: number): string {
  if (s < 0.1) return `${s.toFixed(2)} s`;
  if (s < 60) return `${s.toFixed(1)} s`;
  const m = Math.floor(s / 60);
  return `${m} min ${Math.round(s - m * 60)} s`;
}

export function Header({ tab, designId, reasoning = false, device, onDevice, size = "auto", onSize, running, projectName, exampleData, health, totals, onMenu, onHome, onReselect }: Props) {
  // "Resend on the CPU / GPU" (a message's context menu) reads the switch and asks it to switch.
  publishDevice({ device, gpu: hasGpu(health), busy: running });
  const switchTo = useRef(onDevice);
  switchTo.current = onDevice;
  useEffect(() => onDeviceRequest((d) => switchTo.current(d)), []);
  // The chip names the model that writes the replies in this mode, on the device picked.
  const role = answerRole(health, device, reasoning, size);
  const model = role.model ?? "local model";
  const dev = role.device ?? (health.state === "ok" ? "cpu" : undefined);
  const where = dev ? ` · ${DEVICE_NAMES[dev]}` : ", local";
  // The server's readiness covers its default device: say "not ready" only for that model.
  const deepMissing = reasoning && health.reasoning?.ready === false && health.reasoning.model === model;
  const offlineModel = health.model ?? model;
  const modelState =
    health.state === "ok"
      ? { dot: deepMissing ? "#D99A1E" : "#2BA866", text: model }
      : health.state === "checking"
        ? { dot: "#B9C3C6", text: health.model ?? "Checking model" }
        : health.state === "model-offline"
          ? { dot: "#D99A1E", text: health.fix?.startsWith("ollama pull") ? `${offlineModel} not pulled` : `${offlineModel} offline` }
          : { dot: "#B42318", text: "Server offline" };
  const rows = health.state === "ok" ? roleRows(health, device, reasoning, size) : [];
  // On a laptop or phone the switch beside the chip already says where it runs, when the two agree.
  const sameAsSwitch = dev === (device === "cpu" ? "cpu" : "gpu");
  return (
    <header className="hdr">
      <button type="button" className="menu-btn ta-btn ta-soft" aria-label="Projects and chats" onClick={onMenu}>
        <svg width="18" height="18" viewBox="0 0 18 18" aria-hidden="true">
          <path d="M3 5h12M3 9h12M3 13h12" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </button>
      <a
        href="/"
        className="hdr-brand"
        aria-label="dioscuri, back to the chat"
        onClick={(e) => {
          e.preventDefault();
          onHome();
        }}
      >
        <LogoSmall />
      </a>
      <span className="hdr-proj" title={exampleData ? "The organisers' daily demand for 2027, reservoir and caps (requirements of 28 Oct 2026)" : projectName}>
        <span className="hdr-avatar" aria-hidden="true">
          {initialsOf(projectName)}
        </span>
        <span className="hdr-proj-name">{projectName}</span>
      </span>
      <ScreenNav tab={tab} designId={designId} onReselect={onReselect} />
      <div className="hdr-right">
        <button
          type="button"
          className="hdr-k ta-btn"
          title="Find a screen, a design or an action (⌘K or Ctrl K)"
          aria-label="Find a screen, a design or an action"
          onClick={() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "k", ctrlKey: true }))}
        >
          <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
            <circle cx="7" cy="7" r="4.6" fill="none" stroke="currentColor" strokeWidth="1.6" />
            <path d="M10.5 10.5 14 14" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
          </svg>
          <kbd>⌘K</kbd>
        </button>
        {/* While the models load (the first message would wait for them): how far it has got. */}
        <ModelsChip />
        <span className="model-ctl hdr-run">
          <span
            className="pill pill-line model-pill"
            tabIndex={0}
            aria-describedby={rows.length ? "model-pop" : undefined}
            title={rows.length ? undefined : health.state === "ok" ? "Open-weight models served by Ollama on this machine" : "See the note in the chat"}
          >
            <span className="dot" style={{ background: modelState.dot }} />
            <span>
              {modelState.text}
              {health.state === "ok" && (
                <>
                  <span className={sameAsSwitch ? "hide-compact hide-narrow" : undefined}>{where}</span>
                  {deepMissing && " (not ready)"}
                </>
              )}
            </span>
            {rows.length > 0 && <ModelPopover rows={rows} health={health} why={profileOf(health, device, size)?.why} />}
          </span>
          <DeviceSwitch device={device} health={health} locked={running} onChange={onDevice} />
          {onSize && <SizeSwitch size={size} locked={running} onChange={onSize} />}
        </span>
        <span className="hdr-usage" title={`This chat: ${totals.llmCalls} model call${totals.llmCalls === 1 ? "" : "s"} (${fmtTokens(totals.promptTokens)} tokens in, ${fmtTokens(totals.outputTokens)} out), ${totals.toolCalls} tool calls, ${totals.cacheHits} from cache${totals.energyWh > 0 ? `; ${fmtWh(totals.energyWh)} of GPU energy measured while it ran (the whole GPU, an upper bound)` : ""}`}>
          <span className="hdr-use">
            <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
              <path d="M3 4.5h10M3 8h10M3 11.5h6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
            </svg>
            <strong>{fmtTokens(totals.tokens)}</strong>
            <span className="hide-narrow"> tokens</span>
          </span>
          <span className="hdr-use hdr-time">
            <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
              <circle cx="8" cy="8.6" r="5.4" fill="none" stroke="currentColor" strokeWidth="1.5" />
              <path d="M8 5.8v3l2 1.3M6.5 1.8h3" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
            </svg>
            <strong>{fmtSeconds(totals.seconds)}</strong>
          </span>
          {totals.energyWh > 0 && (
            <span className="hdr-use">
              <svg width="13" height="13" viewBox="0 0 16 16" aria-hidden="true">
                <path d="M9 1.8 4 9h3.6L7 14.2 12 7H8.4z" fill="none" stroke="currentColor" strokeWidth="1.4" strokeLinejoin="round" />
              </svg>
              <strong>{fmtWh(totals.energyWh)}</strong>
            </span>
          )}
        </span>
      </div>
    </header>
  );
}

/** Which model does what on the picked device, shown on hover or focus of the model chip. */
function ModelPopover({ rows, health, why }: { rows: ReturnType<typeof roleRows>; health: Health; why?: string }) {
  return (
    <span className="model-pop" id="model-pop" role="tooltip">
      <span className="model-pop-title">Open-weight models on this machine</span>
      {rows.map((r) => (
        <span key={r.label} className={`model-pop-row${r.active ? " on" : ""}`}>
          <span className="model-pop-label">{r.label}</span>
          <span className="model-pop-model">{r.role.model}</span>
          <span className={`model-pop-dev ${r.role.device}`}>{DEVICE_NAMES[r.role.device] ?? r.role.device}</span>
        </span>
      ))}
      <span className="model-pop-foot">Served by Ollama{health.gpu ? ` · ${health.gpu}` : health.gpu === "" ? " · no GPU found" : ""}</span>
      {why && <span className="model-pop-why">{why}</span>}
    </span>
  );
}

export const LOCKED_TIP = "Available when the reply has finished";

/**
 * GPU | CPU: where the models run from the next run on. GPU is off when the server found none;
 * both are locked while a reply is streaming (the run in progress keeps its device).
 */
function DeviceSwitch({ device, health, locked, onChange }: { device: Device; health: Health; locked: boolean; onChange: (d: Device) => void }) {
  const gpu = hasGpu(health);
  const opts: { value: Device; label: string; off: boolean; tip: string }[] = [
    { value: "auto", label: "GPU", off: !gpu || locked, tip: locked ? LOCKED_TIP : gpu ? `Run the models on the GPU${health.gpu ? ` (${health.gpu})` : ""}` : "No GPU found" },
    { value: "cpu", label: "CPU", off: locked, tip: locked ? LOCKED_TIP : "Run the models on the CPU, as a laptop without a GPU would (much slower)" },
  ];
  const at = device === "cpu" ? 1 : 0;
  return (
    <span className={`dev-seg${locked ? " locked" : ""}`} role="radiogroup" aria-label="Run the models on" aria-disabled={locked || undefined}>
      <span className="dev-thumb ta-thumb" style={{ left: `calc(3px + ${at} * (100% - 6px) / 2)` }} aria-hidden="true" />
      {opts.map((o, i) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={i === at}
          aria-disabled={o.off || undefined}
          aria-label={o.off ? `${o.label}: ${o.tip}` : o.label}
          tabIndex={i === at ? 0 : -1}
          className={o.value === "auto" && !gpu ? "off" : undefined}
          onClick={() => !o.off && onChange(o.value)}
          onKeyDown={(e) => {
            if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
            e.preventDefault();
            if (locked) return;
            const next = opts[1 - i];
            if (next.off) return;
            onChange(next.value);
            (e.currentTarget.parentElement?.querySelectorAll("button")[1 - i] as HTMLButtonElement | undefined)?.focus();
          }}
        >
          {o.label}
          <span className="tip" aria-hidden="true">
            {o.tip}
          </span>
        </button>
      ))}
    </span>
  );
}

/**
 * Auto | 9B | 4B: which model runs from the next run on. Auto takes the first that fits: the 9B
 * on the GPU, the 4B on the GPU, the 9B on the CPU, the 4B on the CPU. Locked while a reply is
 * streaming, like the device switch.
 */
function SizeSwitch({ size, locked, onChange }: { size: Size; locked: boolean; onChange: (s: Size) => void }) {
  const opts: { value: Size; label: string; tip: string }[] = [
    { value: "auto", label: "Auto", tip: "The first model that fits: 9B on the GPU, else 4B on the GPU, else 9B on the CPU, else 4B" },
    { value: "9b", label: "9B", tip: "qwen3.5:9b: better answers, slower on the CPU" },
    { value: "4b", label: "4B", tip: "qwen3.5:4b: faster, smaller" },
  ];
  const at = Math.max(0, opts.findIndex((o) => o.value === size));
  const n = opts.length;
  return (
    <span className={`dev-seg size-seg${locked ? " locked" : ""}`} role="radiogroup" aria-label="Model" aria-disabled={locked || undefined}>
      <span
        className="dev-thumb ta-thumb"
        style={{ width: `calc((100% - 6px) / ${n})`, left: `calc(3px + ${at} * (100% - 6px) / ${n})` }}
        aria-hidden="true"
      />
      {opts.map((o, i) => (
        <button
          key={o.value}
          type="button"
          role="radio"
          aria-checked={i === at}
          aria-disabled={locked || undefined}
          aria-label={locked ? `${o.label}: ${LOCKED_TIP}` : `${o.label}: ${o.tip}`}
          tabIndex={i === at ? 0 : -1}
          onClick={() => !locked && onChange(o.value)}
          onKeyDown={(e) => {
            if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
            e.preventDefault();
            if (locked) return;
            const j = (i + (e.key === "ArrowRight" ? 1 : n - 1)) % n;
            onChange(opts[j].value);
            (e.currentTarget.parentElement?.querySelectorAll("button")[j] as HTMLButtonElement | undefined)?.focus();
          }}
        >
          {o.label}
          <span className="tip" aria-hidden="true">
            {locked ? LOCKED_TIP : o.tip}
          </span>
        </button>
      ))}
    </span>
  );
}

const ORDER: TabId[] = TAB_GROUPS.flatMap((g) => g.tabs);

/** A tab's link: the one-design tabs carry the design picked (#energy/A1). */
function tabHref(t: TabId, designId: string | null): string {
  return hrefFor(t, TAB_META[t].scope === "design" ? designId : null);
}

/**
 * The screens, grouped by what they read (the chat | one design | all designs | how we know),
 * with thin dividers between the groups. A tablist: arrow keys, Home and End move between the
 * tabs (roving tabindex), Enter or Space opens one. At 900 px and below it folds into a select.
 */
function ScreenNav({ tab, designId, onReselect }: { tab: TabId; designId: string | null; onReselect?: (tab: TabId) => void }) {
  const refs = useRef<(HTMLAnchorElement | null)[]>([]);
  // A thumb slides under the tab on show (BoardUI's segmented control).
  const [thumb, setThumb] = useState<{ left: number; width: number } | null>(null);
  useLayoutEffect(() => {
    const place = () => {
      const el = refs.current[ORDER.indexOf(tab)];
      if (el) setThumb({ left: el.offsetLeft, width: el.offsetWidth });
    };
    place();
    window.addEventListener("resize", place);
    document.fonts?.ready.then(place).catch(() => undefined);
    return () => window.removeEventListener("resize", place);
  }, [tab]);
  const onKey = (e: KeyboardEvent<HTMLAnchorElement>, i: number) => {
    const last = ORDER.length - 1;
    const to: Record<string, number> = { ArrowRight: i === last ? 0 : i + 1, ArrowLeft: i === 0 ? last : i - 1, Home: 0, End: last };
    if (e.key === " ") {
      e.preventDefault();
      e.currentTarget.click();
      return;
    }
    if (!(e.key in to)) return;
    e.preventDefault();
    refs.current[to[e.key]]?.focus();
  };
  return (
    <nav className="nav" aria-label="Screens">
      <div className="nav-tabs" role="tablist" aria-label="Screens">
        {thumb && <span className="nav-thumb" aria-hidden="true" style={{ transform: `translateX(${thumb.left}px)`, width: thumb.width }} />}
        {TAB_GROUPS.map((g, gi) => (
          <Fragment key={g.caption}>
            {gi > 0 && <span className="nav-div" aria-hidden="true" />}
            {g.tabs.map((t) => {
              const i = ORDER.indexOf(t);
              const on = t === tab;
              return (
                <a
                  key={t}
                  ref={(el) => {
                    refs.current[i] = el;
                  }}
                  id={`nav-tab-${t}`}
                  role="tab"
                  href={tabHref(t, designId)}
                  aria-selected={on}
                  aria-controls={on ? (t === "chat" ? "chat-panel" : "tab-panel") : undefined}
                  tabIndex={on ? 0 : -1}
                  className="nav-item ta-nav"
                  title={on && t !== "chat" ? `${TAB_META[t].label}: click again to refresh` : `${g.caption}: ${TAB_META[t].hint}`}
                  onKeyDown={(e) => onKey(e, i)}
                  onClick={(e) => {
                    // The tab on show, clicked again: refresh it rather than navigate.
                    if (on && onReselect && !e.metaKey && !e.ctrlKey && !e.shiftKey) {
                      e.preventDefault();
                      onReselect(t);
                    }
                  }}
                >
                  {TAB_META[t].label}
                </a>
              );
            })}
          </Fragment>
        ))}
      </div>
      <label className="nav-pick">
        <span className="sr-only">Screen</span>
        <select value={tab} onChange={(e) => go(e.target.value as TabId, TAB_META[e.target.value as TabId].scope === "design" ? designId : null)}>
          {TAB_GROUPS.map((g) => (
            <optgroup key={g.caption} label={g.caption}>
              {g.tabs.map((t) => (
                <option key={t} value={t}>
                  {TAB_META[t].label}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <span className="nav-pick-chev" aria-hidden="true">
          <Chevron open={false} />
        </span>
      </label>
    </nav>
  );
}
