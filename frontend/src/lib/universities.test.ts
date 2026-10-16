import { existsSync } from "node:fs";
import { join } from "node:path";

import { describe, expect, it } from "vitest";

import universities from "./api/__fixtures__/universities.json";
import {
  HERO_ORDER,
  nextIndex,
  photoFor,
  UNIVERSITY_PHOTOS,
} from "./universities";

describe("university photographs", () => {
  it("cover every university the real API returned", () => {
    for (const university of universities) {
      expect(
        photoFor(university.short_name),
        university.short_name,
      ).not.toBeNull();
    }
  });

  it("all exist in public/ and carry a credit and a source", () => {
    for (const [name, photo] of Object.entries(UNIVERSITY_PHOTOS)) {
      expect(existsSync(join(process.cwd(), "public", photo.src)), name).toBe(
        true,
      );
      expect(photo.credit, name).toMatch(/, (CC|Public)/);
      expect(photo.source, name).toMatch(
        /^https:\/\/commons\.wikimedia\.org\//,
      );
      expect(photo.alt.length, name).toBeGreaterThan(10);
    }
  });

  it("are all part of the home page cycle, each once", () => {
    expect([...HERO_ORDER].sort()).toEqual(
      Object.keys(UNIVERSITY_PHOTOS).sort(),
    );
  });

  it("returns nothing for a university without a photo", () => {
    expect(photoFor("Somewhere Else")).toBeNull();
  });

  it("cycles back to the first photo after the last", () => {
    expect(nextIndex(0, 7)).toBe(1);
    expect(nextIndex(6, 7)).toBe(0);
    expect(nextIndex(0, 0)).toBe(0);
  });
});
