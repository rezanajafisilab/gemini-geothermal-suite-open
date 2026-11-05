// Parts the Energy and Economics tabs share: the chart card, the KPI tile, the thin split bar and
// the Heat | Cold switch. Styles in parts.css, scoped to the two tabs.

import { useId, type HTMLAttributes, type ReactNode } from "react";

import "./parts.css";

/** A white card with a title row (title, a sub line, chips and actions at the right) and a body. */
export function Panel({
  title,
  sub,
  aside,
  className,
  children,
  delay = 0,
}: {
  title: ReactNode;
  sub?: ReactNode;
  /** Chips and buttons at the right of the title. */
  aside?: ReactNode;
  className?: string;
  children: ReactNode;
  /** The rise animation's delay, s. */
  delay?: number;
}) {
  const id = useId();
  return (
    <section className={`ee-panel ta-rise${className ? ` ${className}` : ""}`} aria-labelledby={id} style={delay ? { animationDelay: `${delay}s` } : undefined}>
      <header className="ee-panel-head">
        <div className="ee-panel-titles">
          <h2 id={id}>{title}</h2>
          {sub && <p className="ee-panel-sub">{sub}</p>}
        </div>
        {aside && <div className="ee-panel-aside">{aside}</div>}
      </header>
      {children}
    </section>
  );
}

/** A KPI tile: a label (with a swatch), a note at the right, the value and unit, then extras. */
export function Tile({
  label,
  swatch,
  note,
  noteTone,
  value,
  unit,
  valueTone,
  sub,
  children,
}: {
  label: ReactNode;
  swatch?: string;
  note?: ReactNode;
  noteTone?: "good" | "bad" | "muted";
  value: ReactNode;
  unit?: ReactNode;
  valueTone?: "good" | "bad" | "muted";
  sub?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="ee-tile">
      <span className="ee-tile-top">
        <span className="ee-tile-label">
          {swatch && <span className="ee-swatch" style={{ background: swatch }} aria-hidden="true" />}
          {label}
        </span>
        {note != null && note !== false && <span className={`ee-tile-note${noteTone ? ` ${noteTone}` : ""}`}>{note}</span>}
      </span>
      <span className="ee-tile-value">
        <strong className={valueTone ? valueTone : undefined}>{value}</strong>
        {unit && <span className="ee-tile-unit">{unit}</span>}
      </span>
      {children}
      {sub && <span className="ee-tile-sub">{sub}</span>}
    </div>
  );
}

/** A thin bar of parts over a total (each part's width is its share), the rest hatched if `short`. */
export function SplitBar({ parts, total, short = 0, label }: { parts: { key: string; value: number; color: string }[]; total: number; short?: number; label: string }) {
  if (!(total > 0)) return <span className="ee-split" role="img" aria-label={label} />;
  return (
    <span className="ee-split" role="img" aria-label={label}>
      {parts
        .filter((p) => p.value > 0)
        .map((p) => (
          <span key={p.key} className="ta-grow" style={{ width: `${Math.min(100, (p.value / total) * 100)}%`, background: p.color }} />
        ))}
      {short > 0 && <span className="ee-hatch" style={{ width: `${Math.min(100, (short / total) * 100)}%` }} />}
    </span>
  );
}

/** A thin meter: a value against a maximum. */
export function Meter({ value, max, color = "#0A6F7C", label }: { value: number; max: number; color?: string; label: string }) {
  const pct = max > 0 ? Math.max(0, Math.min(100, (value / max) * 100)) : 0;
  return (
    <span className="ee-meter" role="img" aria-label={label}>
      <span className="ta-grow" style={{ width: `${pct}%`, background: color }} />
    </span>
  );
}

/** A two- or three-way switch in the app's segmented style (global .seg). */
export function Switch<T extends string>({ options, value, onChange, label }: { options: { id: T; label: string }[]; value: T; onChange: (v: T) => void; label: string }) {
  const at = Math.max(0, options.findIndex((o) => o.id === value));
  const n = options.length;
  return (
    <span className="seg ee-switch" role="radiogroup" aria-label={label}>
      <span className="seg-thumb ta-thumb" style={{ left: `calc(4px + ${at} * (100% - 8px) / ${n})`, width: `calc((100% - 8px) / ${n})` }} />
      {options.map((o) => (
        <button
          key={o.id}
          type="button"
          role="radio"
          aria-checked={o.id === value}
          style={{ fontWeight: o.id === value ? 650 : 450 }}
          onClick={() => onChange(o.id)}
          onKeyDown={(e) => {
            const d = { ArrowRight: 1, ArrowDown: 1, ArrowLeft: -1, ArrowUp: -1 }[e.key];
            if (!d) return;
            e.preventDefault();
            const next = options[(at + d + n) % n];
            onChange(next.id);
            (e.currentTarget.parentElement?.querySelectorAll("button")[(at + d + n) % n] as HTMLButtonElement | undefined)?.focus();
          }}
          tabIndex={o.id === value ? 0 : -1}
        >
          {o.label}
        </button>
      ))}
    </span>
  );
}

/** A legend entry: a swatch (or a line key) and its label, with an optional figure. */
export function Key({
  color,
  line = false,
  hatch = false,
  swatchClass,
  children,
  attrs,
}: {
  color?: string;
  line?: boolean;
  /** The red "not covered" hatch. */
  hatch?: boolean;
  /** A class for the swatch (e.g. another fill pattern), in place of `color`. */
  swatchClass?: string;
  children: ReactNode;
  /** More attributes for the entry (a context menu's handlers, a tab stop). */
  attrs?: HTMLAttributes<HTMLSpanElement>;
}) {
  return (
    <span {...attrs} className={`ee-key${attrs?.className ? ` ${attrs.className}` : ""}`}>
      {hatch ? (
        <span className="ee-swatch ee-hatch" aria-hidden="true" />
      ) : line ? (
        <svg width="16" height="8" viewBox="0 0 16 8" aria-hidden="true">
          <path d="M1 4h14" stroke={color} strokeWidth="2.2" strokeLinecap="round" />
        </svg>
      ) : (
        <span className={`ee-swatch${swatchClass ? ` ${swatchClass}` : ""}`} style={swatchClass ? undefined : { background: color }} aria-hidden="true" />
      )}
      {children}
    </span>
  );
}

/** A Chart | Table toggle for a chart's table view. */
export function TableToggle({ on, onChange }: { on: boolean; onChange: (on: boolean) => void }) {
  return (
    <button type="button" className="ee-table-btn ta-btn" aria-pressed={on} onClick={() => onChange(!on)}>
      {on ? "Chart" : "Table"}
    </button>
  );
}

/** An id safe for SVG url(#…) references. */
export function useSvgId(prefix: string): string {
  return `${prefix}-${useId().replace(/[^\w-]/g, "")}`;
}

/** The red hatch the app uses for "not covered" (MonthlyChart's), as an SVG pattern. */
export function HatchPattern({ id }: { id: string }) {
  return (
    <pattern id={id} width="6" height="6" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
      <rect width="6" height="6" fill="#E9928A" />
      <rect width="3" height="6" fill="#B42318" />
    </pattern>
  );
}
