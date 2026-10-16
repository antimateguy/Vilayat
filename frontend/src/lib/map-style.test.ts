import { describe, expect, it } from "vitest";

import layerAreas from "./api/__fixtures__/layer-areas.json";
import layerCells from "./api/__fixtures__/layer-cells.json";
import search from "./api/__fixtures__/search.json";
import {
  areaLayerSchema,
  cellLayerSchema,
  searchResultSchema,
  UNKNOWN,
} from "./api/schemas";
import {
  formatAmenities,
  formatDate,
  formatEur,
  formatMinutes,
  formatScore,
} from "./format";
import {
  BAND_COLOURS,
  bandIndex,
  NEUTRAL,
  overlayScale,
  rankLabels,
  SCORE_COLOURS,
  scoreStep,
  styleAreas,
  styleCells,
} from "./map-style";

const areas = areaLayerSchema.parse(layerAreas);
const cells = cellLayerSchema.parse(layerCells);
const result = searchResultSchema.parse(search);

describe("hexagon bands", () => {
  it("puts the shortest commute in the darkest band", () => {
    expect(
      [10, 15, 16, 30, 31, 45, 46, 60, 61, 119].map((m) =>
        bandIndex("commute", m),
      ),
    ).toEqual([4, 4, 3, 3, 2, 2, 1, 1, 0, 0]);
  });

  it("puts the most amenities and the best job access in the darkest band", () => {
    expect(
      [0, 1, 2, 3, 7, 8, 19, 20, 150].map((n) => bandIndex("amenities", n)),
    ).toEqual([0, 1, 1, 2, 2, 3, 3, 4, 4]);
    expect(
      [0, 0.19, 0.2, 0.5, 0.8, 1].map((s) => bandIndex("job_access", s)),
    ).toEqual([0, 0, 1, 2, 4, 4]);
  });

  it("has one legend entry per colour, on every layer", () => {
    for (const overlay of ["commute", "amenities", "job_access"] as const) {
      const scale = overlayScale(overlay);

      expect(scale.bands.map((band) => band.colour)).toEqual([...BAND_COLOURS]);
      expect(scale.limits).toHaveLength(BAND_COLOURS.length - 1);
    }
  });

  it("marks a cell without a figure as unknown instead of colouring it", () => {
    const withGap = {
      ...cells,
      features: [
        cells.features[0],
        {
          ...cells.features[1],
          properties: { ...cells.features[1].properties, value: UNKNOWN },
        },
      ],
    };

    const styled = styleCells(cellLayerSchema.parse(withGap), "commute");

    expect(styled.features[0].properties.known).toBe(true);
    expect(BAND_COLOURS).toContain(styled.features[0].properties.colour);
    expect(styled.features[1].properties).toMatchObject({
      known: false,
      band: -1,
    });
  });
});

describe("area shading", () => {
  it("gives the best rank the darkest step and the worst the lightest", () => {
    expect([1, 2, 3, 4, 5].map((rank) => scoreStep(rank, 5))).toEqual([
      3, 3, 2, 1, 0,
    ]);
    expect(scoreStep(1, 1)).toBe(3);
    expect(scoreStep(8, 8)).toBe(0);
  });

  it("joins each outline to its group in the search result", () => {
    const styled = styleAreas(areas, result);
    const statuses = new Map(
      styled.features.map((f) => [f.id, f.properties.status]),
    );

    for (const item of result.ranked) {
      if (statuses.has(item.area.id))
        expect(statuses.get(item.area.id)).toBe("ranked");
    }
    for (const item of result.excluded) {
      if (statuses.has(item.area.id))
        expect(statuses.get(item.area.id)).toBe("excluded");
    }
    expect(styled.features).toHaveLength(areas.features.length);
  });

  it("uses a blue step for a ranked area and neutral grey for the rest", () => {
    const styled = styleAreas(areas, result);

    for (const feature of styled.features) {
      const { status, colour, rank } = feature.properties;
      if (status === "ranked") {
        expect(SCORE_COLOURS).toContain(colour);
        expect(rank).toBeGreaterThan(0);
      } else {
        expect(colour).toBe(NEUTRAL.excluded);
        expect(rank).toBe(0);
      }
    }
  });

  it("leaves every area without a status before the first search has answered", () => {
    const styled = styleAreas(areas, undefined);

    expect(new Set(styled.features.map((f) => f.properties.status))).toEqual(
      new Set(["none"]),
    );
  });

  it("labels an area made of two parts once, on its larger part", () => {
    const square = (west: number, size: number) => [
      [west, 48],
      [west + size, 48],
      [west + size, 48 + size],
      [west, 48 + size],
      [west, 48],
    ];
    const layer = areaLayerSchema.parse({
      type: "FeatureCollection",
      features: [
        {
          ...areas.features[0],
          id: result.ranked[0].area.id,
          geometry: {
            type: "MultiPolygon",
            coordinates: [[square(11, 0.01)], [square(12, 0.1)]],
          },
        },
      ],
    });

    const labels = rankLabels(styleAreas(layer, result));

    expect(labels.features).toHaveLength(1);
    expect(labels.features[0].properties.rank).toBe(1);
    const [lon, lat] = labels.features[0].geometry.coordinates;
    expect(lon).toBeCloseTo(12.05);
    expect(lat).toBeCloseTo(48.05);
  });

  it("draws no rank label for an area that is not ranked", () => {
    expect(rankLabels(styleAreas(areas, undefined)).features).toEqual([]);
  });
});

describe("formatting", () => {
  it("never shows a missing figure as a number", () => {
    expect(formatMinutes(UNKNOWN)).toBe("Unknown");
    expect(formatEur(UNKNOWN)).toBe("Unknown");
    expect(formatScore(UNKNOWN)).toBe("Unknown");
    expect(formatDate(UNKNOWN)).toBe("Unknown");
  });

  it("formats known figures", () => {
    expect(formatMinutes(29)).toBe("29 min");
    expect(formatEur(1234.5)).toBe("1,235 EUR");
    expect(formatScore(0.287)).toBe("29");
    expect(formatDate("2026-10-05")).toBe("5 Oct 2026");
    expect(formatDate("yesterday")).toBe("yesterday");
  });

  it("lists amenities in a fixed order with the right plural", () => {
    expect(
      formatAmenities({ gym: 1, cafe: 2, supermarket: 0, library: 1 }),
    ).toEqual(["0 supermarkets", "2 cafes", "1 library", "1 gym"]);
  });
});
