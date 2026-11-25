import { describe, expect, it } from "vitest";

import { plainText, segments, SentenceBuffer } from "./answer-text";

describe("answer text", () => {
  it("splits citation markers out of the text", () => {
    expect(segments("Sorts widgets [c1]. Tested [c2][c3].")).toEqual([
      { kind: "text", text: "Sorts widgets " },
      { kind: "cite", id: "c1" },
      { kind: "text", text: ". Tested " },
      { kind: "cite", id: "c2" },
      { kind: "cite", id: "c3" },
      { kind: "text", text: "." },
    ]);
  });

  it("removes markers for plain text", () => {
    expect(plainText("Sorts widgets [c1]. Tested [c2] .")).toBe("Sorts widgets. Tested.");
  });

  it("releases whole sentences only, including their trailing citations", () => {
    const buffer = new SentenceBuffer();
    const got: string[] = [];
    for (const delta of ["It sorts wid", "gets [c1]. It was ", "tested [c2]. And then", " more"]) {
      got.push(...buffer.push(delta));
    }
    expect(got).toEqual(["It sorts widgets.", "It was tested."]);
    expect(buffer.flush()).toEqual(["And then more"]);
  });
});
