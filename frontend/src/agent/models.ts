// Which local model does what, on the device picked in the header (GET /api/health `profiles`).
// Pure functions of the health answer, so the header, the reasoning bar and the tests agree.

import type { Device, Health, Profile, RoleModel, Size } from "./client";

export const DEVICE_NAMES = { gpu: "GPU", cpu: "CPU" } as const;

/** The roles a profile names, in the order the header lists them. */
export const ROLES: { key: Exclude<keyof Profile, "why">; label: string; reasoning?: boolean }[] = [
  { key: "fast", label: "Reads messages" },
  { key: "answer", label: "Answers" },
  { key: "answer_reasoning", label: "Answers when it reasons", reasoning: true },
  { key: "reasoning", label: "Plans when it reasons", reasoning: true },
  { key: "generator", label: "Writes models" },
];

/** True unless the server says it found no GPU (an empty name); unknown counts as available. */
export function hasGpu(health: Health): boolean {
  return health.gpu !== "";
}

/** The device runs use: the user's pick, else the server's default; the CPU when there's no GPU. */
export function pickDevice(chosen: Device | null | undefined, health: Health): Device {
  if (!hasGpu(health)) return "cpu";
  return chosen ?? health.default_device ?? "auto";
}

/** The model size runs use: the user's pick, else the server's default, else auto. */
export function pickSize(chosen: Size | null | undefined, health: Health): Size {
  return chosen ?? health.default_size ?? "auto";
}

/** The profile key of a choice: the device alone for auto, else "device:size". */
export const profileKey = (device: Device, size: Size = "auto") => (size === "auto" ? device : `${device}:${size}`);

/** The profile for a device and size choice, when the server sends profiles. */
export function profileOf(health: Health, device: Device, size: Size = "auto"): Profile | undefined {
  return health.profiles?.[profileKey(device, size)];
}

/**
 * The model that writes the replies in this mode on this device. Without profiles (an older
 * server) it is today's label: the reasoning model in reasoning mode, else the fast one.
 */
export function answerRole(health: Health, device: Device, reasoning: boolean, size: Size = "auto"): Partial<RoleModel> {
  const p = profileOf(health, device, size);
  const role = p && (reasoning ? (p.answer_reasoning ?? p.reasoning ?? p.answer) : p.answer);
  if (role?.model) return role;
  const deep = reasoning && health.reasoning?.model ? health.reasoning : null;
  return deep ? { model: deep.model, device: deep.device } : { model: health.model, device: health.device };
}

/** Every role with its model, for the header's popover. Older servers give what they know. */
export function roleRows(health: Health, device: Device, reasoning: boolean, size: Size = "auto"): { label: string; role: RoleModel; active: boolean }[] {
  const p = profileOf(health, device, size);
  const rows: { label: string; role: RoleModel; active: boolean }[] = [];
  if (p) {
    const answerKey = reasoning ? (p.answer_reasoning ? "answer_reasoning" : p.reasoning ? "reasoning" : "answer") : "answer";
    for (const r of ROLES) {
      const role = p[r.key];
      if (role?.model) rows.push({ label: r.label, role, active: r.key === answerKey });
    }
    return rows;
  }
  const dev = health.device ?? "cpu";
  if (health.model) rows.push({ label: "Reads messages and answers", role: { model: health.model, device: dev }, active: !reasoning });
  if (health.reasoning?.model)
    rows.push({ label: "Plans and explains when it reasons", role: { model: health.reasoning.model, device: health.reasoning.device ?? dev }, active: reasoning });
  return rows;
}

export const roleText = (r: Partial<RoleModel>) => `${r.model ?? "local model"}${r.device ? ` · ${DEVICE_NAMES[r.device]}` : ""}`;
