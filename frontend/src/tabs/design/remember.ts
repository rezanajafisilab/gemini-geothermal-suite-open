// State the Design tab keeps while you switch tabs (the tab unmounts): per design (the day, the
// part picked, the GEMINI project as edited, its last run) or for the tab ("*": the view). Kept in
// memory for the visit, like the workbench store; nothing goes to localStorage.

import { useCallback, useState, type Dispatch, type SetStateAction } from "react";

const memory = new Map<string, unknown>();

/** Like useState, but the value outlives the component: the same scope and key give it back. */
export function useRemembered<T>(scope: string, key: string, initial: T | (() => T)): [T, Dispatch<SetStateAction<T>>] {
  const id = `${scope}\u0000${key}`;
  const [value, setValue] = useState<T>(() => {
    if (memory.has(id)) return memory.get(id) as T;
    const v = typeof initial === "function" ? (initial as () => T)() : initial;
    memory.set(id, v);
    return v;
  });
  const set = useCallback<Dispatch<SetStateAction<T>>>(
    (next) =>
      setValue((prev) => {
        const v = typeof next === "function" ? (next as (p: T) => T)(prev) : next;
        memory.set(id, v);
        return v;
      }),
    [id],
  );
  return [value, set];
}

/** Set what a scope remembers before the tab shows it (a menu's "Jump to that day in the Design player"). */
export function remember<T>(scope: string, key: string, value: T) {
  memory.set(`${scope}\u0000${key}`, value);
}

/** Forget what a scope remembered (a deleted design). */
export function forget(scope: string) {
  for (const id of [...memory.keys()]) if (id.startsWith(`${scope}\u0000`)) memory.delete(id);
}
