// A design's own name, typed where its menu was (menu/namebox.ts). The name shows in the picker,
// the designs strip and the @ list beside the design's handle, and the agent reads it in messages.

import { useEffect, useLayoutEffect, useRef, useState, useSyncExternalStore } from "react";

import { workbench } from "../workbench/store";
import { placeMenu } from "./keys";
import { closeNameBox, nameBoxStore, type NameBox } from "./namebox";
import { showToast } from "./store";

function Box({ box }: { box: NameBox }) {
  const [text, setText] = useState(box.current);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);
  const root = useRef<HTMLDivElement>(null);
  const input = useRef<HTMLInputElement>(null);

  useLayoutEffect(() => {
    const el = root.current;
    if (!el) return;
    const view = { w: window.innerWidth, h: window.innerHeight };
    const size = { w: el.offsetWidth, h: el.offsetHeight };
    setPos(box.at ? placeMenu(box.at, size, view, 12) : { left: Math.max(12, (view.w - size.w) / 2), top: 120 });
  }, [box]);
  useEffect(() => {
    if (!pos) return;
    input.current?.focus();
    input.current?.select();
  }, [pos]);
  useEffect(() => {
    const away = (e: Event) => {
      if (!root.current?.contains(e.target as Node)) closeNameBox();
    };
    document.addEventListener("pointerdown", away, true);
    return () => document.removeEventListener("pointerdown", away, true);
  }, []);

  const save = async () => {
    closeNameBox();
    const name = text.replace(/\s+/g, " ").trim();
    if (name === box.current.trim()) return;
    const res = await workbench.setMeta(box.design, { name });
    showToast(res.ok ? (name ? `${box.handle} is now “${name}”` : `${box.handle}'s name taken away`) : `Couldn't rename ${box.handle}: ${res.message}`, res.ok ? "ok" : "bad");
  };

  return (
    <div ref={root} className="qa nb" role="dialog" aria-label={`Name ${box.handle}`} style={pos ? { left: pos.left, top: pos.top } : { left: 0, top: 0, visibility: "hidden" }}>
      <label className="nb-label" htmlFor="nb-input">
        Name <span className="uid-chip small">{box.handle}</span>
      </label>
      <input
        id="nb-input"
        ref={input}
        className="nb-input"
        value={text}
        maxLength={60}
        placeholder="For example: gas-free option"
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter") {
            e.preventDefault();
            void save();
          } else if (e.key === "Escape") {
            e.preventDefault();
            closeNameBox();
          }
        }}
      />
      <span className="nb-hint">Enter keeps it, Esc leaves it. The chat understands this name too.</span>
    </div>
  );
}

export function NameBoxHost() {
  const box = useSyncExternalStore(nameBoxStore.subscribe, nameBoxStore.getSnapshot, nameBoxStore.getSnapshot);
  return box ? <Box key={box.id} box={box} /> : null;
}
