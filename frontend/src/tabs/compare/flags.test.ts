// Codes and variant flags in words.

import { describe, expect, it } from "vitest";

import { codeParts, depthWords, flagFamily, flagWords } from "./flags";

describe("codes and flags", () => {
  it("reads a code into its parts", () => {
    expect(codeParts("2D-HP-AB")).toEqual({ doublets: 2, topup: "HP", cooling: "AB", depths: [], flags: [] });
    expect(codeParts("2D-BO-EC@2500+3000-2I1-ST-BL")).toEqual({ doublets: 2, topup: "BO", cooling: "EC", depths: [2500, 3000], flags: ["2I1", "ST", "BL"] });
    expect(codeParts("1D-DH-NC@3000")).toMatchObject({ topup: "DH", cooling: "NC", depths: [3000] });
    expect(codeParts("U2")).toMatchObject({ doublets: null, flags: [] });
  });

  it("says every flag in words, the per-doublet ones too", () => {
    expect(flagWords("2I")).toBe("two injectors per doublet");
    expect(flagWords("2I1")).toBe("two injectors on doublet 1");
    expect(flagWords("2I12")).toBe("two injectors on doublets 1 and 2");
    expect(flagWords("ST")).toMatch(/treatment train .* per doublet/);
    expect(flagWords("ST2")).toBe("2 treatment trains");
    expect(flagWords("BL")).toMatch(/hottest doublet first/);
    expect(flagWords("PL")).toMatch(/lower half/);
    expect(flagWords("PU")).toMatch(/upper half/);
    expect(flagWords("IU")).toMatch(/injectors open over the upper half/);
    expect(flagWords("IL")).toMatch(/injectors open over the lower half/);
    expect(flagFamily("2I12")).toBe("2I");
    expect(flagFamily("ST2")).toBe("ST");
    expect(depthWords([3000])).toBe("aquifer at 3,000 m");
    expect(depthWords([2500, 3000])).toBe("doublets at 2,500 m and 3,000 m");
  });
});
