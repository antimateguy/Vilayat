import { describe, expect, it } from "vitest";

import type { CommuteRoute } from "./api/schemas";
import { chooseFocus, focusKey, openSpace, widened } from "./map-focus";

function square(areaId: number, status: string, lon: number, lat: number) {
  return {
    geometry: {
      type: "MultiPolygon",
      coordinates: [
        [
          [
            [lon, lat],
            [lon + 0.01, lat],
            [lon + 0.01, lat + 0.01],
            [lon, lat],
          ],
        ],
      ],
    },
    properties: { area_id: areaId, status },
  };
}

const AREAS = {
  features: [
    square(1, "ranked", 11.5, 48.1),
    square(2, "ranked", 11.6, 48.2),
    square(3, "excluded", 11.9, 48.4),
  ],
};

const TRIP: CommuteRoute = {
  departs_at: "07:40",
  total_minutes: 20,
  start: [11.5, 48.1],
  computed_at: "2026-10-16T12:00:00Z",
  legs: [
    {
      mode: "subway",
      minutes: 15,
      wait_minutes: 2,
      distance_m: 4000,
      line: "U2",
      from_stop: "A",
      to_stop: "B",
      line_colour: null,
      path: {
        type: "LineString",
        coordinates: [
          [11.5, 48.1],
          [11.7, 48.3],
        ],
      },
    },
  ],
};

describe("chooseFocus", () => {
  it("frames the areas within the limits on the ranking", () => {
    const focus = chooseFocus("none", null, [], AREAS);

    expect(focus?.kind).toBe("ranked");
    // The two fitting squares, with a 5% margin.
    const [[west, south], [east, north]] = focus!.bounds;
    expect([west, south, east, north].map((n) => n.toFixed(4))).toEqual([
      "11.4945",
      "48.0945",
      "11.6155",
      "48.2155",
    ]);
  });

  it("keeps a chosen area outside the limits in view on the ranking", () => {
    const focus = chooseFocus("none", 3, [], AREAS);

    expect(focus!.bounds[1][0]).toBeGreaterThan(11.91);
  });

  it("frames the trip on the commute layer and the area on the others", () => {
    expect(chooseFocus("commute", 1, [TRIP], AREAS)?.kind).toBe("trip");
    expect(chooseFocus("commute", 1, [], AREAS)?.kind).toBe("area");
    expect(chooseFocus("amenities", 1, [TRIP], AREAS)?.kind).toBe("area");
  });

  it("shows the whole city on a hexagon layer, or when nothing fits", () => {
    expect(chooseFocus("job_access", null, [], AREAS)?.kind).toBe("city");
    const noneFit = {
      features: AREAS.features.map((feature) => ({
        ...feature,
        properties: { ...feature.properties, status: "excluded" },
      })),
    };
    expect(chooseFocus("none", null, [], noneFit)?.kind).toBe("city");
  });

  it("waits for the outlines", () => {
    expect(chooseFocus("none", null, [], null)).toBeNull();
  });
});

describe("focusKey", () => {
  it("is the same for the same view and differs for another", () => {
    const one = chooseFocus("none", null, [], AREAS);
    expect(focusKey(one)).toBe(focusKey(chooseFocus("none", null, [], AREAS)));
    expect(focusKey(one)).not.toBe(focusKey(chooseFocus("none", 3, [], AREAS)));
  });
});

describe("openSpace", () => {
  it("leaves room for the detail panel only when it is open on a wide screen", () => {
    const size = { width: 1200, height: 800 };

    expect(openSpace(size, true, true).right).toBe(412);
    expect(openSpace(size, false, true).right).toBe(32);
    expect(openSpace(size, true, false).right).toBe(32);
  });

  it("never pads away most of a small map", () => {
    const padding = openSpace({ width: 500, height: 300 }, true, true);

    expect(padding.right).toBeLessThanOrEqual(300);
    expect(padding.top + padding.bottom).toBeLessThan(300);
  });
});

describe("widened", () => {
  it("adds the share of the size on every side", () => {
    expect(
      widened(
        [
          [0, 0],
          [10, 20],
        ],
        0.1,
      ),
    ).toEqual([
      [-1, -2],
      [11, 22],
    ]);
  });
});
