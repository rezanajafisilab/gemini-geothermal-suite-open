// Replay and screenshot options read from the URL (see fixtures/scenes.ts).
const params = new URLSearchParams(typeof window === "undefined" ? "" : window.location.search);

/** &open=1: keep every steps group and reasoning block open (screenshots of finished runs). */
export const KEEP_OPEN = params.get("open") === "1";
