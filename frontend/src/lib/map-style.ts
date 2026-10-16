import {
  type AreaLayer,
  type CellLayer,
  type SearchResult,
  UNKNOWN,
} from "./api/schemas";
import type { Overlay } from "./search-state";

// Colour on the map does one job: magnitude. So it is one hue (the India green
// of the Vilayat design), light to dark,
// and darker always means "better for the student" on every layer. Areas that
// are not in the ranking are neutral grey, never a second hue. Both ramps pass
// the lightness-step and contrast checks of the palette validator.

/** Five steps for the hexagon layers. */
export const BAND_COLOURS = [
  "#62b350",
  "#3d9a2e",
  "#127a0a",
  "#0b5306",
  "#072b04",
] as const;

/** Four steps for the ranked areas, by quarter of the current results. */
export const SCORE_COLOURS = [
  "#62b350",
  "#3d9a2e",
  "#0b5306",
  "#072b04",
] as const;

export const NEUTRAL = {
  excluded: "#d7d3d3",
  outline: "#7d7979",
  ink: "#201e1d",
  surface: "#f3f2f2",
} as const;

/** The typical journey: the flag's chakra navy, a hue no area or hexagon uses,
 * so the route never reads as an outline or a shade of the green ramps. */
export const ROUTE_COLOUR = "#1d2a7a";

export type AreaStatus = "ranked" | "excluded" | "unchecked" | "none";

export interface Band {
  label: string;
  colour: string;
}

interface BandScale {
  title: string;
  note: string;
  /** Upper limits of every band but the last, lightest band first. */
  limits: number[];
  bands: Band[];
}

// Commute is the one layer where a smaller number is better, so its bands are
// listed from long to short: the darkest band is still the best one.
const SCALES: Record<Exclude<Overlay, "none">, BandScale> = {
  commute: {
    title: "Minutes to campus",
    note: "Weekday morning, by public transport",
    limits: [-60, -45, -30, -15],
    bands: [
      { label: "Over 60", colour: BAND_COLOURS[0] },
      { label: "46 to 60", colour: BAND_COLOURS[1] },
      { label: "31 to 45", colour: BAND_COLOURS[2] },
      { label: "16 to 30", colour: BAND_COLOURS[3] },
      { label: "Up to 15", colour: BAND_COLOURS[4] },
    ],
  },
  amenities: {
    title: "Everyday amenities in the cell",
    note: "Supermarkets, cafes, libraries and gyms",
    limits: [1, 3, 8, 20],
    bands: [
      { label: "None", colour: BAND_COLOURS[0] },
      { label: "1 to 2", colour: BAND_COLOURS[1] },
      { label: "3 to 7", colour: BAND_COLOURS[2] },
      { label: "8 to 19", colour: BAND_COLOURS[3] },
      { label: "20 or more", colour: BAND_COLOURS[4] },
    ],
  },
  job_access: {
    title: "Part-time job access",
    note: "Where student-type employers cluster; not vacancies",
    limits: [0.2, 0.4, 0.6, 0.8],
    bands: [
      { label: "Lowest fifth", colour: BAND_COLOURS[0] },
      { label: "Low", colour: BAND_COLOURS[1] },
      { label: "Middle", colour: BAND_COLOURS[2] },
      { label: "High", colour: BAND_COLOURS[3] },
      { label: "Highest fifth", colour: BAND_COLOURS[4] },
    ],
  },
};

export function overlayScale(overlay: Exclude<Overlay, "none">): BandScale {
  return SCALES[overlay];
}

/** Which band (0 = lightest) a value falls in. */
export function bandIndex(
  overlay: Exclude<Overlay, "none">,
  value: number,
): number {
  // Commute limits are stored negated so that "greater is better" holds for all.
  const comparable = overlay === "commute" ? -value : value;
  const index = SCALES[overlay].limits.findIndex((limit) => comparable < limit);
  return index === -1 ? SCALES[overlay].limits.length : index;
}

/** Give each hexagon its band, so the map only has to look up a colour. */
export function styleCells(
  layer: CellLayer,
  overlay: Exclude<Overlay, "none">,
) {
  return {
    type: "FeatureCollection" as const,
    features: layer.features.map((feature) => {
      const { value } = feature.properties;
      const band = value === UNKNOWN ? -1 : bandIndex(overlay, value);
      return {
        ...feature,
        properties: {
          ...feature.properties,
          band,
          colour: band === -1 ? NEUTRAL.surface : BAND_COLOURS[band],
          known: band !== -1,
        },
      };
    }),
  };
}

/** Position of a rank among `total` results as a colour step, best = darkest. */
export function scoreStep(rank: number, total: number): number {
  if (total <= 1) return SCORE_COLOURS.length - 1;
  const fromBest = (rank - 1) / (total - 1);
  return Math.min(
    SCORE_COLOURS.length - 1,
    Math.floor((1 - fromBest) * SCORE_COLOURS.length),
  );
}

/**
 * Join the search result onto the area outlines: every area gets its status,
 * and a ranked area its rank and colour.
 */
export function styleAreas(layer: AreaLayer, result: SearchResult | undefined) {
  const ranked = new Map(result?.ranked.map((item) => [item.area.id, item]));
  const excluded = new Set(result?.excluded.map((item) => item.area.id));
  const unchecked = new Set(result?.unchecked.map((item) => item.area.id));
  const total = result?.ranked.length ?? 0;

  return {
    type: "FeatureCollection" as const,
    features: layer.features.map((feature) => {
      const item = ranked.get(feature.id);
      let status: AreaStatus = "none";
      if (item) status = "ranked";
      else if (excluded.has(feature.id)) status = "excluded";
      else if (unchecked.has(feature.id)) status = "unchecked";
      return {
        ...feature,
        properties: {
          ...feature.properties,
          status,
          rank: item?.rank ?? 0,
          colour: item
            ? SCORE_COLOURS[scoreStep(item.rank, total)]
            : NEUTRAL.excluded,
        },
      };
    }),
  };
}

type Ring = [number, number][];

/** Area of a ring by the shoelace formula; the unit does not matter here. */
function ringArea(ring: Ring): number {
  let sum = 0;
  for (let i = 0; i < ring.length - 1; i += 1) {
    sum += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1];
  }
  return Math.abs(sum) / 2;
}

function ringCentre(ring: Ring): [number, number] {
  const points = ring.slice(0, -1);
  const lon = points.reduce((sum, point) => sum + point[0], 0) / points.length;
  const lat = points.reduce((sum, point) => sum + point[1], 0) / points.length;
  return [lon, lat];
}

/**
 * One point per ranked area, where its rank number is drawn. An area made of
 * several parts gets a single label, on its largest part.
 */
export function rankLabels(areas: ReturnType<typeof styleAreas>) {
  return {
    type: "FeatureCollection" as const,
    features: areas.features
      .filter((feature) => feature.properties.status === "ranked")
      .flatMap((feature) => {
        const polygons = feature.geometry.coordinates as Ring[][];
        const outerRings = polygons
          .map((polygon) => polygon[0])
          .filter((ring) => Array.isArray(ring) && ring.length >= 4);
        if (outerRings.length === 0) return [];
        const largest = outerRings.reduce((best, ring) =>
          ringArea(ring) > ringArea(best) ? ring : best,
        );
        return [
          {
            type: "Feature" as const,
            geometry: {
              type: "Point" as const,
              coordinates: ringCentre(largest),
            },
            properties: {
              area_id: feature.properties.area_id,
              rank: feature.properties.rank,
            },
          },
        ];
      }),
  };
}
