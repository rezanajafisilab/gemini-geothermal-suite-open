// The question before a chat is removed: its designs, runs and uploaded files go with it, from
// this browser and from the server (ChatStore.removeChat). When the server can't be reached,
// nothing is removed and the dialog says why.

import { useState } from "react";

import { HttpError } from "../agent/client";
import { Spinner } from "./Icons";
import { Modal } from "./Modal";

export function RemoveChatDialog({ title, running, onClose, onRemoved }: { title: string; running: boolean; onClose: () => void; onRemoved: () => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  return (
    <Modal label={`Remove the chat ${title}`} onClose={onClose} className="modal-confirm">
      <h2 className="confirm-title">Remove “{title}”?</h2>
      <p className="note">
        {running ? "Its run stops, and its" : "Its"} designs, runs and uploaded files are removed with it. This can't be undone.
      </p>
      {error && (
        <p className="err" role="alert">
          {error}
        </p>
      )}
      <div className="np-actions" style={{ justifyContent: "flex-end", marginTop: 14 }}>
        <button type="button" className="btn btn-soft ta-btn" onClick={onClose}>
          Cancel
        </button>
        <button
          type="button"
          className="btn btn-ink btn-danger ta-btn"
          disabled={busy}
          onClick={async () => {
            setBusy(true);
            try {
              await onRemoved();
            } catch (err) {
              const why = err instanceof HttpError ? err.message.replace(/\.$/, "") : "The chat couldn't be removed";
              setError(`${why}. Nothing was removed.`);
              setBusy(false);
            }
          }}
        >
          {busy && <Spinner size={14} light />}
          Remove chat
        </button>
      </div>
    </Modal>
  );
}
