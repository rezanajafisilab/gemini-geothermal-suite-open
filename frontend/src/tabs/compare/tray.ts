// The designs ticked in the Compare tray, per conversation, for "Add to the Compare tray" from
// anywhere in the app: the Compare tab notes its ticks here, and a menu adds one to them through
// the tab's link (#compare/<ids>).

const ticked = new Map<string, string[]>();

/** The Compare tab: these are ticked now in this conversation. */
export function noteTray(threadId: string, ids: string[]): void {
  ticked.set(threadId, [...ids]);
}

/** The designs ticked in a conversation's tray ([] before the tab has been opened). */
export function trayIds(threadId: string | null): string[] {
  return (threadId && ticked.get(threadId)) || [];
}
