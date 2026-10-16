import { describe, expect, it } from "vitest";
import { z } from "zod";

import aiStatus from "./__fixtures__/ai-status.json";
import areaBriefing from "./__fixtures__/area-briefing.json";
import areaBriefingUnknown from "./__fixtures__/area-briefing-unknown.json";
import areaDetail from "./__fixtures__/area-detail.json";
import askAnswered from "./__fixtures__/ask-answered.json";
import askNoEvidence from "./__fixtures__/ask-no-evidence.json";
import cities from "./__fixtures__/cities.json";
import comparison from "./__fixtures__/comparison.json";
import employers from "./__fixtures__/employers.json";
import errorInvalid from "./__fixtures__/error-invalid.json";
import errorNotFound from "./__fixtures__/error-not-found.json";
import errorUnavailable from "./__fixtures__/error-unavailable.json";
import intent from "./__fixtures__/intent.json";
import intentEmpty from "./__fixtures__/intent-empty.json";
import layerAreas from "./__fixtures__/layer-areas.json";
import layerCells from "./__fixtures__/layer-cells.json";
import search from "./__fixtures__/search.json";
import sources from "./__fixtures__/sources.json";
import universities from "./__fixtures__/universities.json";
import {
  aiStatusSchema,
  areaBriefingSchema,
  areaDetailSchema,
  areaLayerSchema,
  askSchema,
  cellLayerSchema,
  citySchema,
  comparisonSchema,
  dataSourceSchema,
  employerSchema,
  errorSchema,
  factsSchema,
  intentSchema,
  searchResultSchema,
  universitySchema,
  UNKNOWN,
} from "./schemas";

// The fixtures are responses captured from the real backend, so these tests
// fail if the frontend's schemas and the API drift apart.
describe("schemas accept what the real API returns", () => {
  it.each([
    ["cities", z.array(citySchema), cities],
    ["universities", z.array(universitySchema), universities],
    ["employers", z.array(employerSchema), employers],
    ["sources", z.array(dataSourceSchema), sources],
    ["search", searchResultSchema, search],
    ["area detail", areaDetailSchema, areaDetail],
    ["comparison", comparisonSchema, comparison],
    ["area layer", areaLayerSchema, layerAreas],
    ["cell layer", cellLayerSchema, layerCells],
    ["not-found error", errorSchema, errorNotFound],
    ["validation error", errorSchema, errorInvalid],
    ["AI status", aiStatusSchema, aiStatus],
    ["sentence read as settings", intentSchema, intent],
    ["sentence with nothing usable", intentSchema, intentEmpty],
    ["answer with sources", askSchema, askAnswered],
    ["no-evidence answer", askSchema, askNoEvidence],
    ["area briefing", areaBriefingSchema, areaBriefing],
    ["area without a briefing", areaBriefingSchema, areaBriefingUnknown],
    ["AI-unavailable error", errorSchema, errorUnavailable],
  ])("%s", (_name, schema, fixture) => {
    expect(schema.safeParse(fixture).success).toBe(true);
  });

  it("keeps the three groups of a search", () => {
    const result = searchResultSchema.parse(search);

    expect(result.ranked.length).toBeGreaterThan(0);
    expect(result.ranked[0].rank).toBe(1);
    expect(result.ranked[0].reasons).toHaveLength(4);
    expect(result.excluded[0].violations[0]).toMatch(/over your/);
    expect(result.ranked[0].full_day?.employer.name).toMatch(/BMW/);
  });

  it("reads which field a validation error is about", () => {
    const { error } = errorSchema.parse(errorInvalid);

    expect(error.code).toBe("invalid_request");
    expect(error.details.map((detail) => detail.field)).toContain(
      "max_commute_minutes",
    );
  });
});

describe("missing figures", () => {
  const facts = {
    cell_count: 5,
    rent: UNKNOWN,
    commute_minutes: UNKNOWN,
    amenities: UNKNOWN,
    job_access: UNKNOWN,
  };

  it('accepts the string "UNKNOWN" for any figure', () => {
    expect(factsSchema.parse(facts).rent).toBe(UNKNOWN);
  });

  it("rejects null, so a missing figure can never pass as a value", () => {
    expect(factsSchema.safeParse({ ...facts, rent: null }).success).toBe(false);
    expect(
      factsSchema.safeParse({ ...facts, commute_minutes: null }).success,
    ).toBe(false);
  });

  it("rejects a response that lacks a field", () => {
    const withoutRent = { ...facts, rent: undefined };

    expect(factsSchema.safeParse(withoutRent).success).toBe(false);
  });
});

describe("the AI layer", () => {
  it("gives every source of an answer its number, link, date and sample flag", () => {
    const answer = askSchema.parse(askAnswered);

    expect(answer.status).toBe("answered");
    expect(answer.answer).toContain(`[${answer.citations[0].number}]`);
    expect(answer.citations[0].source_url).toMatch(/^https:\/\//);
    expect(answer.citations[0].retrieved_on).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(answer.citations[0].is_sample).toBe(true);
  });

  it("has no sources when the documents do not cover the question", () => {
    expect(askSchema.parse(askNoEvidence).citations).toEqual([]);
  });

  it("rejects an answer status the app does not know how to show", () => {
    const invented = { ...askNoEvidence, status: "guessed" };

    expect(askSchema.safeParse(invented).success).toBe(false);
  });

  it('uses "UNKNOWN", not null, for an area without a briefing', () => {
    expect(areaBriefingSchema.parse(areaBriefingUnknown).briefing).toBe(
      UNKNOWN,
    );
    expect(
      areaBriefingSchema.safeParse({ ...areaBriefingUnknown, briefing: null })
        .success,
    ).toBe(false);
  });

  it("recognises the error that means: carry on without the model", () => {
    expect(errorSchema.parse(errorUnavailable).error.code).toBe(
      "ai_unavailable",
    );
  });
});
