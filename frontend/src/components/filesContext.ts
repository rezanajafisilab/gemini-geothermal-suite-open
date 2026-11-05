// How any part of an answer opens a file or an image: the chat (ChatView) provides it and draws
// the dialog; file chips, source cards and file cards only ask.

import { createContext, useContext } from "react";

export interface FilesApi {
  /** Open a file's preview by name (a project file or an upload of this chat). */
  open: (name: string) => void;
  /** Show an image full size. */
  showImage: (image: { url: string; caption?: string }) => void;
}

const NONE: FilesApi = { open: () => {}, showImage: () => {} };

export const FilesContext = createContext<FilesApi>(NONE);

export function useFiles(): FilesApi {
  return useContext(FilesContext);
}
