// The rules behind the composer's chips and a message's files: which files wait for the next
// message, what a message keeps of them, how their chips read, and what a paste brings.

import { describe, expect, it } from "vitest";

import { attachmentLabel, kindOf, pastedFiles, pendingFiles, sentWith, toTurnAttachment, type Attachment } from "./attachments";

const ready = (name: string, chunks: number, sentIn?: string): Attachment => ({ name, status: "ready", chunks, sentIn });

describe("which files go with which message", () => {
  const files: Attachment[] = [ready("brief.pdf", 12, "t0"), ready("notes.md", 3), { name: "huge.csv", status: "failed", error: "file too large" }, ready("map.png", 0, "t1")];

  it("the composer shows the files not sent yet, failed ones included", () => {
    expect(pendingFiles(files).map((f) => f.name)).toEqual(["notes.md", "huge.csv"]);
  });

  it("a message's bubble shows the files sent with it only", () => {
    expect(sentWith(files, "t0").map((f) => f.name)).toEqual(["brief.pdf"]);
    expect(sentWith(files, "t1").map((f) => f.name)).toEqual(["map.png"]);
    expect(sentWith(files, "t9")).toEqual([]);
  });

  it("a message keeps a file's name, kind and passage count; an image has no count, an upload no count yet", () => {
    expect(toTurnAttachment(ready("notes.md", 3))).toEqual({ name: "notes.md", kind: "text", chunks: 3 });
    expect(toTurnAttachment(ready("map.png", 0))).toEqual({ name: "map.png", kind: "image" });
    expect(toTurnAttachment({ name: "brief.pdf", status: "uploading" })).toEqual({ name: "brief.pdf", kind: "text", uploading: true });
    expect(kindOf("Photo.JPG")).toBe("image");
    expect(kindOf("data.csv")).toBe("text");
  });

  it("chips say 'image' or 'n passages', never '0 chunks'", () => {
    expect(attachmentLabel("image", 0)).toBe("image");
    expect(attachmentLabel("image")).toBe("image");
    expect(attachmentLabel("text", 3)).toBe("3 passages");
    expect(attachmentLabel("text", 1)).toBe("1 passage");
    expect(attachmentLabel("text")).toBeUndefined();
  });
});

describe("paste to attach", () => {
  const at = new Date(2026, 9, 30, 9, 5, 7);

  it("a pasted screenshot gets a name with the time; several in one paste are numbered", () => {
    const shot = new File([new Uint8Array([137, 80, 78, 71])], "image.png", { type: "image/png" });
    const [one] = pastedFiles({ files: [shot] }, at);
    expect(one.name).toBe("pasted-image-090507.png");
    expect(one.type).toBe("image/png");
    expect(one.size).toBe(4);
    const two = pastedFiles({ files: [shot, new File(["x"], "", { type: "image/jpeg" })] }, at);
    expect(two.map((f) => f.name)).toEqual(["pasted-image-090507.png", "pasted-image-090507-2.jpg"]);
  });

  it("files copied from the file manager keep their names", () => {
    const brief = new File(["pdf"], "site brief.pdf", { type: "application/pdf" });
    const photo = new File(["jpg"], "well-pad.jpg", { type: "image/jpeg" });
    const out = pastedFiles({ files: [brief, photo] }, at);
    expect(out.map((f) => f.name)).toEqual(["site brief.pdf", "well-pad.jpg"]);
    expect(out[0]).toBe(brief);
  });

  it("a text paste brings no files, so the textarea pastes as usual", () => {
    expect(pastedFiles({ files: [] })).toEqual([]);
    expect(pastedFiles({ files: null })).toEqual([]);
    expect(pastedFiles(null)).toEqual([]);
  });
});
