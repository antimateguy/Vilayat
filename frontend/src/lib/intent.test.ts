import { describe, expect, it } from "vitest";

import intentEmpty from "./api/__fixtures__/intent-empty.json";
import intentFixture from "./api/__fixtures__/intent.json";
import { type Intent, intentSchema } from "./api/schemas";
import { applyIntent, snapToRange } from "./intent";
import {
  DEFAULT_STATE,
  LIMITS,
  parseSearchState,
  toSearchParams,
} from "./search-state";

const CITIES = [
  { id: "munich", name: "Munich" },
  { id: "berlin", name: "Berlin" },
];
const NOTHING: Intent = {
  understood: false,
  city_id: null,
  campus: null,
  max_rent_eur: null,
  max_commute_minutes: null,
  employer: null,
  weights: null,
  notes: [],
};
const apply = (intent: Partial<Intent>, state = DEFAULT_STATE) =>
  applyIntent(state, { ...NOTHING, ...intent }, CITIES);

describe("fitting a value to a slider", () => {
  it("keeps a value the slider can show", () => {
    expect(snapToRange(725, LIMITS.rent)).toBe(725);
  });

  it("moves to the nearest step and stays inside the range", () => {
    expect(snapToRange(733, LIMITS.rent)).toBe(725);
    expect(snapToRange(740, LIMITS.rent)).toBe(750);
    expect(snapToRange(5000, LIMITS.rent)).toBe(1500);
    expect(snapToRange(100, LIMITS.rent)).toBe(300);
    expect(snapToRange(33, LIMITS.commute)).toBe(35);
  });
});

describe("applying what a sentence asked for", () => {
  it("fills in every setting the real API returned", () => {
    const result = applyIntent(
      DEFAULT_STATE,
      intentSchema.parse(intentFixture),
      CITIES,
    );

    expect(result.changes).toEqual({
      campusId: 10,
      areaId: null,
      maxRentEur: 725,
      maxCommuteMinutes: 35,
      employerId: 40,
      weights: { commute: 35, rent: 50, amenities: 0, job_access: 15 },
    });
    expect(result.applied).toEqual([
      "Campus: LMU, Main Campus",
      "Maximum rent: 725 EUR a month",
      "Maximum commute: 35 min each way",
      "Employer pinned: BMW Group Headquarters",
      "What matters most: commute 35, rent 50, amenities 0, job access 15",
    ]);
    expect(result.notes).toEqual([
      "No campus of LMU was named, so Main Campus is used. Change it if you study elsewhere.",
    ]);
  });

  it("changes nothing when the sentence gave no setting", () => {
    const result = applyIntent(
      DEFAULT_STATE,
      intentSchema.parse(intentEmpty),
      CITIES,
    );

    expect(result.changes).toEqual({});
    expect(result.applied).toEqual([]);
    expect(result.notes).toEqual(["Not used: wants a balcony"]);
  });

  it("leaves settings alone that the sentence did not mention", () => {
    const state = {
      ...DEFAULT_STATE,
      campusId: 8,
      employerId: 40,
      maxRentEur: 900,
    };

    const next = {
      ...state,
      ...apply({ max_commute_minutes: 30 }, state).changes,
    };

    expect(next).toEqual({ ...state, maxCommuteMinutes: 30 });
  });

  it("clears the campus, employer and open area when the city changes", () => {
    const state = {
      ...DEFAULT_STATE,
      campusId: 8,
      employerId: 40,
      areaId: 106,
    };

    const result = apply({ city_id: "berlin" }, state);

    expect(result.changes).toEqual({
      city: "berlin",
      campusId: null,
      employerId: null,
      areaId: null,
    });
    expect(result.applied).toEqual(["City: Berlin"]);
  });

  it("keeps the campus and employer the sentence named for the new city", () => {
    const result = apply({
      city_id: "berlin",
      campus: {
        id: 2,
        name: "Campus Mitte",
        university_id: 2,
        university_short_name: "HU Berlin",
      },
      employer: { id: 32, name: "Zalando Headquarters" },
    });

    expect(result.changes).toMatchObject({
      city: "berlin",
      campusId: 2,
      employerId: 32,
    });
  });

  it("does not treat the current city as a change", () => {
    expect(apply({ city_id: "munich" })).toEqual({
      changes: {},
      applied: [],
      notes: [],
    });
  });

  it("says so when a value had to be fitted to the slider", () => {
    const result = apply({ max_rent_eur: 2000, max_commute_minutes: 33 });

    expect(result.changes).toEqual({ maxRentEur: 1500, maxCommuteMinutes: 35 });
    expect(result.notes).toEqual([
      "You said 2000 EUR. The rent slider goes from 300 to 1500 in steps of 25, so 1500 EUR is used.",
      "You said 33 min. The commute slider goes from 10 to 90 in steps of 5, so 35 min is used.",
    ]);
  });

  it("puts the fitting notes before the notes from the server", () => {
    const result = apply({
      max_rent_eur: 2000,
      notes: ["Not used: a balcony"],
    });

    expect(result.notes[1]).toBe("Not used: a balcony");
  });

  it("produces settings that survive a round trip through the page address", () => {
    const next = {
      ...DEFAULT_STATE,
      ...applyIntent(DEFAULT_STATE, intentSchema.parse(intentFixture), CITIES)
        .changes,
    };

    expect(parseSearchState(toSearchParams(next))).toEqual(next);
  });
});
