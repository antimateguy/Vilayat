import { describe, expect, it } from "vitest";

import { splitCitations } from "./citations";

describe("splitting an answer at its source markers", () => {
  it("separates text and markers in order", () => {
    expect(
      splitCitations("Register within 14 days [1]. Bring a passport [2]."),
    ).toEqual([
      { kind: "text", text: "Register within 14 days " },
      { kind: "citation", number: 1 },
      { kind: "text", text: ". Bring a passport " },
      { kind: "citation", number: 2 },
      { kind: "text", text: "." },
    ]);
  });

  it("handles markers side by side and at the very start", () => {
    expect(splitCitations("[3][12] Both say so")).toEqual([
      { kind: "citation", number: 3 },
      { kind: "citation", number: 12 },
      { kind: "text", text: " Both say so" },
    ]);
  });

  it("returns plain text unchanged", () => {
    expect(splitCitations("No sources here.")).toEqual([
      { kind: "text", text: "No sources here." },
    ]);
    expect(splitCitations("")).toEqual([]);
  });

  it("does not mistake other brackets for markers", () => {
    expect(splitCitations("See [a] and [1a].")).toEqual([
      { kind: "text", text: "See [a] and [1a]." },
    ]);
  });
});
