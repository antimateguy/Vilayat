import { describe, expect, it } from "vitest";

import type { CommuteRoute, RouteLeg } from "./api/schemas";
import {
  describeSteps,
  formatDistance,
  journeyFeatures,
  legColour,
  textOn,
  spreadSentence,
  summariseLines,
} from "./route";

function leg(overrides: Partial<RouteLeg>): RouteLeg {
  return {
    mode: "walk",
    minutes: 4,
    wait_minutes: 0,
    distance_m: 320,
    line: null,
    from_stop: null,
    to_stop: null,
    line_colour: null,
    path: {
      type: "LineString",
      coordinates: [
        [11.57, 48.14],
        [11.58, 48.15],
      ],
    },
    ...overrides,
  };
}

const RIDE = leg({
  mode: "subway",
  minutes: 9,
  wait_minutes: 2,
  distance_m: 3000,
  line: "U2",
  from_stop: "Scheidplatz",
  to_stop: "Hauptbahnhof",
});

const ROUTE: CommuteRoute = {
  departs_at: "07:52",
  total_minutes: 19,
  start: [11.57, 48.14],
  legs: [leg({}), RIDE, leg({ minutes: 5, distance_m: 1200 })],
  computed_at: "2026-10-16T12:00:00Z",
};

describe("describeSteps", () => {
  it("walks to the stop of the next ride and finally to campus", () => {
    const steps = describeSteps(ROUTE.legs);

    expect(steps.map((step) => step.text)).toEqual([
      "Walk 4 min (320 m) to Scheidplatz",
      "from Scheidplatz to Hauptbahnhof, 9 min",
      "Walk 5 min (1.2 km) to campus",
    ]);
    expect(steps[1]).toMatchObject({ line: "U2", wait: 2 });
  });

  it("names an unnamed ride by its kind", () => {
    const [step] = describeSteps([
      leg({ mode: "bus", from_stop: null, to_stop: null, minutes: 7 }),
    ]);

    expect(step).toMatchObject({ line: "Bus", text: "7 min" });
  });
});

describe("describeSteps destination", () => {
  it("ends the afternoon leg at the employer", () => {
    const steps = describeSteps(ROUTE.legs, "BMW Group Headquarters");

    expect(steps[2].text).toBe("Walk 5 min (1.2 km) to BMW Group Headquarters");
  });
});

describe("summaries", () => {
  it("lists the lines in order, or says the trip is on foot", () => {
    expect(summariseLines(ROUTE)).toBe("U2");
    expect(
      summariseLines({
        ...ROUTE,
        legs: [RIDE, leg({}), { ...RIDE, line: "S1" }],
      }),
    ).toBe("U2, then S1");
    expect(summariseLines({ ...ROUTE, legs: [leg({})] })).toBe("on foot");
  });

  it("explains the spread and the figure the ranking uses", () => {
    expect(
      spreadSentence({
        cells: 19,
        fastest_minutes: 17,
        median_minutes: 30,
        slowest_minutes: 46,
      }),
    ).toBe(
      "Depending on where in the area you live, the morning trip takes 17 to 46 min. The ranking uses the middle value, 30 min.",
    );
    expect(
      spreadSentence({
        cells: 1,
        fastest_minutes: 12,
        median_minutes: 12,
        slowest_minutes: 12,
      }),
    ).toMatch(/about 12 min/);
  });

  it("formats distances", () => {
    expect(formatDistance(64)).toBe("60 m");
    expect(formatDistance(1530)).toBe("1.5 km");
  });
});

describe("journeyFeatures", () => {
  it("draws rides, walks, stops, a line label and the start", () => {
    const { features } = journeyFeatures([ROUTE]);
    const parts = features.map((feature) => feature.properties.part);

    expect(parts).toEqual([
      "walk",
      "ride",
      "stop",
      "stop",
      "label",
      "walk",
      "start",
    ]);
    const label = features[4].properties;
    expect(label).toMatchObject({
      label: "U2",
      colour: "#0065ae",
      text: "#ffffff",
    });
  });

  it("joins the trip to campus and the trip to work, starting from home", () => {
    const toJob = {
      ...ROUTE,
      legs: [
        leg({
          path: {
            type: "LineString",
            coordinates: [
              [11.6, 48.2],
              [11.7, 48.3],
            ],
          },
        }),
      ],
    };
    const { features } = journeyFeatures([ROUTE, toJob]);
    const start = features.find(
      (feature) => feature.properties.part === "start",
    );

    expect(start?.geometry.coordinates).toEqual([11.57, 48.14]);
  });
});

describe("colours", () => {
  it("prefers the timetable's colour and falls back to one per mode", () => {
    expect(legColour({ ...RIDE, line_colour: "#DA421E" })).toBe("#DA421E");
    expect(legColour(RIDE)).toBe("#0065ae");
    expect(legColour(leg({}))).toBe("#1d2a7a");
  });

  it("picks readable text for a badge", () => {
    expect(textOn("#0065ae")).toBe("#ffffff");
    expect(textOn("#f2b705")).toBe("#201e1d");
  });
});
