// Files attached to a chat: what the composer holds until the next message, what a sent message
// shows, and the files a paste brings. Pure helpers, so the store and the composer stay small
// and these rules are tested on their own (attachments.test.ts).

import type { TurnAttachment } from "../agent/types";

/** A file attached to a conversation (searched and cited by the agent). */
export interface Attachment {
  name: string;
  status: "uploading" | "ready" | "failed";
  /** Passages indexed (0 for an image: it is read whole, not searched as text). */
  chunks?: number;
  error?: string;
  /** An image's object URL for the chip's thumbnail (this visit only, never saved). */
  preview?: string;
  /**
   * The turn (message) it was sent with. Unset while it waits in the composer. The server keeps
   * searching it for the rest of the chat; the UI shows it under that one message only.
   */
  sentIn?: string;
}

export const IMAGE = /\.(png|jpe?g|webp|gif)$/i;

export const isImage = (name: string) => IMAGE.test(name);

export const kindOf = (name: string): TurnAttachment["kind"] => (isImage(name) ? "image" : "text");

/** The files attached since the last message: the composer's chips, sent with the next message. */
export function pendingFiles(files: Attachment[]): Attachment[] {
  return files.filter((f) => !f.sentIn);
}

/** The files sent with one message, as its bubble shows them. */
export function sentWith(files: Attachment[], turnId: string): Attachment[] {
  return files.filter((f) => f.sentIn === turnId);
}

/** What a message keeps of a file: its name and kind, and the passages the server indexed. */
export function toTurnAttachment(f: Attachment): TurnAttachment {
  const kind = kindOf(f.name);
  return {
    name: f.name,
    kind,
    ...(kind === "text" && f.chunks != null ? { chunks: f.chunks } : {}),
    ...(f.status === "uploading" ? { uploading: true } : {}),
  };
}

/** The words after a file's name on its chip: "image", "3 passages"; nothing while the count is unknown. */
export function attachmentLabel(kind: TurnAttachment["kind"], chunks?: number): string | undefined {
  if (kind === "image") return "image";
  if (chunks == null) return undefined;
  return `${chunks} ${chunks === 1 ? "passage" : "passages"}`;
}

/** A DataTransfer, or anything with its `files` (tests build one from plain File objects). */
export interface ClipboardLike {
  files?: ArrayLike<File> | null;
}

// Browsers name a pasted screenshot "image.png" (or nothing): a name worth replacing. A file
// copied from the file manager keeps its own name.
const GENERIC_NAME = /^(?:image|unknown|blob|clipboard|pasted)?(?:\.\w+)?$/i;
const EXT_OF_TYPE: Record<string, string> = { "image/png": "png", "image/jpeg": "jpg", "image/webp": "webp", "image/gif": "gif" };

/**
 * The files on a clipboard, for the composer's paste handler: a screenshot, or files copied
 * from the file manager. Empty for a text paste (the textarea then pastes as usual). A pasted
 * image with no name of its own becomes `pasted-image-<HHMMSS>.png` (`-2`, `-3`, ... when one
 * paste brings several).
 */
export function pastedFiles(data: ClipboardLike | null | undefined, now = new Date()): File[] {
  const files = Array.from(data?.files ?? []);
  const stamp = [now.getHours(), now.getMinutes(), now.getSeconds()].map((n) => String(n).padStart(2, "0")).join("");
  let n = 0;
  return files.map((f) => {
    const image = f.type.startsWith("image/") || isImage(f.name);
    if (!image || !GENERIC_NAME.test(f.name)) return f;
    n += 1;
    const ext = EXT_OF_TYPE[f.type] ?? f.name.match(IMAGE)?.[1]?.toLowerCase() ?? "png";
    const name = `pasted-image-${stamp}${n > 1 ? `-${n}` : ""}.${ext}`;
    return new File([f], name, { type: f.type, lastModified: f.lastModified });
  });
}
