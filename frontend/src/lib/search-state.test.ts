import { describe, expect, it } from "vitest";

import {
  DEFAULT_STATE,
  hasUsableWeights,
  parseSearchState,
  type SearchState,
  searchChanged,
  toSearchParams,
  toSearchRequest,
} from "./search-state";

const parse = (query: string) => parseSearchState(new URLSearchParams(query));

describe("reading the page address", () => {
  it("uses the defaults when the address has no settings", () => {
    expect(parse("")).toEqual(DEFAULT_STATE);
  });

  it("reads every setting", () => {
    expect(
      parse(
        "city=berlin&campus=3&rent=650&commute=30&wc=50&wr=20&wa=10&wj=0&employer=12&layer=commute&area=7",
      ),
    ).toEqual({
      city: "berlin",
      campusId: 3,
      maxRentEur: 650,
      maxCommuteMinutes: 30,
      weights: { commute: 50, rent: 20, amenities: 10, job_access: 0 },
      employerId: 12,
      overlay: "commute",
      areaId: 7,
    });
  });

  it("clamps numbers that are out of range", () => {
    const state = parse("rent=99999&commute=1&wc=500");

    expect(state.maxRentEur).toBe(1500);
    expect(state.maxCommuteMinutes).toBe(10);
    expect(state.weights.commute).toBe(100);
  });

  it.each([
    ["city=../etc", "city", "munich"],
    ["rent=cheap", "maxRentEur", 800],
    ["commute=-5", "maxCommuteMinutes", 40],
    ["campus=1e9", "campusId", null],
    ["layer=noise", "overlay", "none"],
    ["area=<script>", "areaId", null],
  ])("ignores an invalid value: %s", (query, key, expected) => {
    expect(parse(query)[key as keyof SearchState]).toEqual(expected);
  });
});

describe("writing the page address", () => {
  it("leaves out settings that equal the default", () => {
    expect(toSearchParams(DEFAULT_STATE).toString()).toBe("");
    expect(
      toSearchParams({
        ...DEFAULT_STATE,
        campusId: 8,
        maxRentEur: 700,
      }).toString(),
    ).toBe("campus=8&rent=700");
  });

  it("survives a round trip", () => {
    const state: SearchState = {
      city: "berlin",
      campusId: 2,
      maxRentEur: 925,
      maxCommuteMinutes: 55,
      weights: { commute: 0, rent: 100, amenities: 15, job_access: 40 },
      employerId: 31,
      overlay: "job_access",
      areaId: 44,
    };

    expect(parseSearchState(toSearchParams(state))).toEqual(state);
  });
});

describe("the search request", () => {
  it("waits until a campus is chosen", () => {
    expect(toSearchRequest(DEFAULT_STATE)).toBeNull();
  });

  it("sends the limits, the weights and the pinned employer", () => {
    expect(
      toSearchRequest({ ...DEFAULT_STATE, campusId: 8, employerId: 40 }),
    ).toEqual({
      campus_id: 8,
      max_commute_minutes: 40,
      max_rent_eur: 800,
      weights: { commute: 35, rent: 35, amenities: 15, job_access: 15 },
      employer_id: 40,
    });
  });

  it("knows that all sliders at zero cannot rank anything", () => {
    const zero = { commute: 0, rent: 0, amenities: 0, job_access: 0 };

    expect(hasUsableWeights(zero)).toBe(false);
    expect(hasUsableWeights({ ...zero, rent: 5 })).toBe(true);
  });
});

describe("searchChanged", () => {
  it("is true for a new question and false for the same values", () => {
    expect(searchChanged(DEFAULT_STATE, { maxRentEur: 900 })).toBe(true);
    expect(searchChanged(DEFAULT_STATE, { city: DEFAULT_STATE.city })).toBe(
      false,
    );
    expect(
      searchChanged(DEFAULT_STATE, { weights: { ...DEFAULT_STATE.weights } }),
    ).toBe(false);
  });

  it("ignores choosing an area or a layer", () => {
    expect(searchChanged(DEFAULT_STATE, { areaId: 5 })).toBe(false);
    expect(searchChanged(DEFAULT_STATE, { overlay: "commute" })).toBe(false);
  });
});
