// What the map should show, and how much of it is free to show it in.
//
// One rule decides the target for every situation, so the map re-frames
// itself whenever the answer changes (new results, another layer, a chosen
// area, a pane opened or closed) and the student never has to hunt for it.

import type { CommuteRoute } from "./api/schemas";
import type { Overlay } from "./search-state";

export type Bounds = [[number, number], [number, number]];

export interface Focus {
  kind: "trip" | "area" | "ranked" | "city";
  bounds: Bounds;
  /** Close enough to read the streets of a trip; never so close that one
   * area fills the screen. */
  maxZoom: number;
}

interface AreaFeatureLike {
  geometry: unknown;
  properties: { area_id: number; status: string };
}

const MAX_ZOOM: Record<Focus["kind"], number> = {
  trip: 14,
  area: 13,
  ranked: 12.5,
  city: 12,
};

/** Share of the target's size left around it, so a single area is seen with
 * its neighbours rather than filling the screen. */
const MARGIN: Record<Focus["kind"], number> = {
  trip: 0.1,
  area: 0.35,
  ranked: 0.05,
  city: 0.02,
};

export function widened(bounds: Bounds, share: number): Bounds {
  const [[west, south], [east, north]] = bounds;
  const dx = (east - west) * share;
  const dy = (north - south) * share;
  return [
    [west - dx, south - dy],
    [east + dx, north + dy],
  ];
}

/**
 * - Commute layer with an area chosen: its trip (or the area until the trip
 *   has loaded).
 * - Amenities or Jobs with an area chosen: the area.
 * - A hexagon layer with nothing chosen: the whole city, which it covers.
 * - Ranking: the areas within the limits, together with a chosen area that
 *   may lie outside them; the whole city when none fits.
 */
export function chooseFocus(
  overlay: Overlay,
  selectedAreaId: number | null,
  journey: CommuteRoute[],
  areas: { features: AreaFeatureLike[] } | null,
): Focus | null {
  const focus = (kind: Focus["kind"], bounds: Bounds | null): Focus | null =>
    bounds
      ? { kind, bounds: widened(bounds, MARGIN[kind]), maxZoom: MAX_ZOOM[kind] }
      : null;

  if (overlay === "commute" && selectedAreaId !== null && journey.length > 0) {
    const trip = focus("trip", boundsOfPoints(journeyPoints(journey)));
    if (trip) return trip;
  }
  if (!areas) return null;
  const chosen = areas.features.filter(
    (feature) => feature.properties.area_id === selectedAreaId,
  );
  if (overlay !== "none") {
    return chosen.length > 0
      ? focus("area", boundsOfFeatures(chosen))
      : focus("city", boundsOfFeatures(areas.features));
  }
  const ranked = areas.features.filter(
    (feature) => feature.properties.status === "ranked",
  );
  if (ranked.length === 0) {
    return focus("city", boundsOfFeatures(areas.features));
  }
  return focus("ranked", boundsOfFeatures([...ranked, ...chosen]));
}

/** Equal for targets that would frame the same view, so a re-render that
 * changes nothing does not move the map. */
export function focusKey(focus: Focus | null): string {
  if (!focus) return "none";
  const corners = focus.bounds.flat().map((value) => value.toFixed(4));
  return `${focus.kind}:${corners.join(",")}`;
}

export interface Padding {
  top: number;
  bottom: number;
  left: number;
  right: number;
}

/**
 * The part of the map that is really visible: clear of the layer bar at the
 * top, the legend and buttons at the bottom left and, when it is open on a
 * wide screen, the detail panel over the right-hand 380 px.
 */
export function openSpace(
  size: { width: number; height: number },
  rightPanelOpen: boolean,
  wide: boolean,
): Padding {
  const right = wide && rightPanelOpen ? PANEL_WIDTH + 32 : 32;
  return {
    top: Math.min(96, size.height * 0.2),
    bottom: Math.min(wide ? 200 : 48, size.height * 0.35),
    left: Math.min(32, size.width * 0.1),
    right: Math.min(right, size.width * 0.6),
  };
}

export const PANEL_WIDTH = 380;

export function journeyPoints(routes: CommuteRoute[]): [number, number][] {
  return routes.flatMap((route) =>
    route.legs.flatMap((leg) => leg.path.coordinates),
  );
}

export function boundsOfPoints(points: [number, number][]): Bounds | null {
  if (points.length === 0) return null;
  let west = Infinity;
  let south = Infinity;
  let east = -Infinity;
  let north = -Infinity;
  for (const [lon, lat] of points) {
    west = Math.min(west, lon);
    east = Math.max(east, lon);
    south = Math.min(south, lat);
    north = Math.max(north, lat);
  }
  return [
    [west, south],
    [east, north],
  ];
}

export function boundsOfFeatures(
  features: { geometry: unknown }[],
): Bounds | null {
  const points: [number, number][] = [];
  const visit = (node: unknown): void => {
    if (!Array.isArray(node)) return;
    if (typeof node[0] === "number" && typeof node[1] === "number") {
      points.push([node[0], node[1]]);
      return;
    }
    node.forEach(visit);
  };
  for (const feature of features) {
    visit((feature.geometry as { coordinates?: unknown }).coordinates);
  }
  return boundsOfPoints(points);
}
