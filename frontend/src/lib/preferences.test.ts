import { describe, expect, it } from "vitest";

import {
  IMPORTANT_WEIGHT,
  importantCount,
  isImportant,
  PRIORITY_CHIPS,
  toggleImportant,
} from "./preferences";
import { DEFAULT_STATE, WEIGHT_KEYS } from "./search-state";

describe("the priority chips", () => {
  it("offer exactly the four things the ranking weighs", () => {
    expect(PRIORITY_CHIPS.map((chip) => chip.key).sort()).toEqual(
      [...WEIGHT_KEYS].sort(),
    );
  });

  it("start unpressed, because no default weight is that high", () => {
    for (const key of WEIGHT_KEYS) {
      expect(isImportant(DEFAULT_STATE.weights, key)).toBe(false);
    }
    expect(importantCount(DEFAULT_STATE.weights)).toBe(0);
  });

  it("raise a weight when pressed and restore the default when pressed again", () => {
    const pressed = toggleImportant(DEFAULT_STATE.weights, "amenities");

    expect(pressed).toEqual({
      ...DEFAULT_STATE.weights,
      amenities: IMPORTANT_WEIGHT,
    });
    expect(toggleImportant(pressed, "amenities")).toEqual(
      DEFAULT_STATE.weights,
    );
  });

  it("leave the other weights alone and never change the input", () => {
    const before = { ...DEFAULT_STATE.weights };

    const pressed = toggleImportant(before, "rent");

    expect(before).toEqual(DEFAULT_STATE.weights);
    expect(pressed.commute).toBe(before.commute);
    expect(importantCount(pressed)).toBe(1);
  });
});
