// Icons and status glyphs from the canvas, as small components.

interface Size {
  size?: number;
}

export function Spinner({ size = 20, light = false }: Size & { light?: boolean }) {
  return (
    <svg className="ta-spin" width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="8" fill="none" stroke={light ? "rgba(255,255,255,.25)" : "#E1E8E8"} strokeWidth={size < 16 ? 3 : 2.4} />
      <path d="M10 2a8 8 0 0 1 8 8" fill="none" stroke={light ? "#FFFFFF" : "#0B8FA0"} strokeWidth={size < 16 ? 3 : 2.4} strokeLinecap="round" />
    </svg>
  );
}

/**
 * Working: a 3 × 3 grid of dots with a wave crossing it corner to corner (after BoardUI's agent
 * thinking indicator). CSS only; still under prefers-reduced-motion.
 */
export function ThinkingDots({ size = 20 }: Size) {
  const dot = Math.round(size / 5);
  const gap = Math.max(1, Math.round((size - 3 * dot) / 2));
  return (
    <span className="thinking-dots" aria-hidden="true" style={{ width: size, height: size, gridTemplateColumns: `repeat(3, ${dot}px)`, gap }}>
      {Array.from({ length: 9 }, (_, i) => (
        <span key={i} style={{ width: dot, height: dot, animationDelay: `${((i % 3) + Math.floor(i / 3)) * 0.11}s` }} />
      ))}
    </span>
  );
}

export function DoneIcon({ size = 20 }: Size) {
  return (
    <svg className="ta-pop" width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="10" fill="#E3F5EA" />
      <path d="M6 10.4 8.7 13 14 7.2" fill="none" stroke="#0F7A3D" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function FailIcon({ size = 20 }: Size) {
  return (
    <svg className="ta-pop" width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <circle cx="10" cy="10" r="10" fill="#FBE3E0" />
      <path d="M7.2 7.2l5.6 5.6M12.8 7.2l-5.6 5.6" fill="none" stroke="#B42318" strokeWidth="2" strokeLinecap="round" />
    </svg>
  );
}

export function WaitingIcon({ size = 20 }: Size) {
  const dot = Math.round(size * 0.4);
  return (
    <span aria-hidden="true" style={{ width: size, height: size, borderRadius: "50%", background: "#FBF1DC", display: "inline-flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
      <span style={{ width: dot, height: dot, borderRadius: "50%", background: "#D99A1E" }} />
    </span>
  );
}

export function StoppedIcon({ size = 20 }: Size) {
  const sq = Math.round(size * 0.4);
  return (
    <span aria-hidden="true" style={{ width: size, height: size, borderRadius: "50%", background: "#EEF2F2", display: "inline-flex", alignItems: "center", justifyContent: "center", flex: "none" }}>
      <span style={{ width: sq, height: sq, borderRadius: 2, background: "#66727C" }} />
    </span>
  );
}

export function PendingIcon({ size = 20 }: Size) {
  return <span aria-hidden="true" style={{ width: size, height: size, borderRadius: "50%", border: "2px solid #DCE3E3", flex: "none" }} />;
}

export function Chevron({ open }: { open: boolean }) {
  return (
    <svg className="chevron" width="16" height="16" viewBox="0 0 16 16" aria-hidden="true" style={{ transform: `rotate(${open ? 180 : 0}deg)` }}>
      <path d="M4 6l4 4 4-4" fill="none" stroke="#66727C" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Plus({ size = 16, color = "currentColor" }: Size & { color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M8 3.5v9M3.5 8h9" stroke={color} strokeWidth="1.8" strokeLinecap="round" />
    </svg>
  );
}

export function FileIcon({ size = 13 }: Size) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
      <path d="M4 1.8h5l3 3V14H4z M9 1.8V5h3" fill="none" stroke="#66727C" strokeWidth="1.3" strokeLinejoin="round" />
    </svg>
  );
}

export function ChatIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 16 16" aria-hidden="true">
      <path d="M2.5 3.5h11v7.2H7.6L4.6 13.2v-2.5H2.5z" fill="none" stroke="#8A959E" strokeWidth="1.4" strokeLinejoin="round" />
    </svg>
  );
}

export function Tick({ size = 13, color = "currentColor" }: Size & { color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
      <path d="M3 8.5 6.5 12 13 4.5" fill="none" stroke={color} strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Cross({ size = 10 }: Size) {
  return (
    <svg width={size} height={size} viewBox="0 0 10 10" aria-hidden="true">
      <path d="M2 2l6 6M8 2 2 8" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
    </svg>
  );
}

export function Retry({ size = 15 }: Size) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M13.2 8a5.2 5.2 0 1 1-1.7-3.85M13.2 2.6v2.8h-2.8" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Copy({ size = 15 }: Size) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M5.5 5.5h7v7h-7zM3.5 10.5v-7h7" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round" />
    </svg>
  );
}

export function Plug({ size = 16, color = "currentColor" }: Size & { color?: string }) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true">
      <path d="M5.8 1.8v3M10.2 1.8v3M4.2 4.8h7.6v2.6a3.8 3.8 0 0 1-7.6 0zM8 11.2v3" fill="none" stroke={color} strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Arrow({ size = 14 }: Size) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
      <path d="M3 8h10M9 4l4 4-4 4" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

/** A file's icon by its kind: a sheet for tables, a picture for images, a page for the rest. */
export function FileGlyph({ name = "", kind, size = 13 }: Size & { name?: string; kind?: string }) {
  const k = kind ?? (/\.(csv|xlsx?)$/i.test(name) ? "table" : /\.(png|jpe?g|webp|gif)$/i.test(name) ? "image" : "text");
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
      {k === "table" ? (
        <path d="M2.5 3h11v10h-11zM2.5 6.3h11M2.5 9.6h11M6.2 6.3V13" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      ) : k === "image" ? (
        <>
          <path d="M2.5 3h11v10h-11z" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          <path d="M2.8 11.6 6.2 8l2.4 2.4 1.6-1.6 3.1 3.1" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
          <circle cx="10.6" cy="5.8" r="1.1" fill="currentColor" />
        </>
      ) : (
        <path d="M4 1.8h5l3 3V14H4z M9 1.8V5h3" fill="none" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
      )}
    </svg>
  );
}

export function Download({ size = 15 }: Size) {
  return (
    <svg width={size} height={size} viewBox="0 0 16 16" aria-hidden="true" style={{ flex: "none" }}>
      <path d="M8 2.5v8M4.5 7 8 10.5 11.5 7M3 13.5h10" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}
