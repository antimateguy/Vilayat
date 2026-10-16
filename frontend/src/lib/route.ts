// Turning a stored journey into readable steps and into lines for the map.

import type {
  CommuteRoute,
  CommuteSpread,
  LegMode,
  RouteLeg,
} from "./api/schemas";

export interface Step {
  /** The line's name ("U2", "Bus 53") for a ride; null for walking. */
  line: string | null;
  text: string;
  /** Waiting before this step, shown separately when it is a minute or more. */
  wait: number;
}

/**
 * "Walk 4 min to Scheidplatz", "U2 from Scheidplatz to Hauptbahnhof, 9 min",
 * "Walk 4 min to campus". A walk takes its destination from the ride after it;
 * the last walk ends at `destination` (the campus, or the employer).
 */
export function describeSteps(
  legs: RouteLeg[],
  destination = "campus",
): Step[] {
  return legs.map((leg, index) => {
    if (leg.mode !== "walk") {
      const from = leg.from_stop ? ` from ${leg.from_stop}` : "";
      const to = leg.to_stop ? ` to ${leg.to_stop}` : "";
      return {
        line: leg.line ?? RIDE_NAMES[leg.mode],
        text: `${from}${to}, ${leg.minutes} min`.replace(/^, /, "").trim(),
        wait: leg.wait_minutes,
      };
    }
    const next = legs[index + 1];
    const target =
      index === legs.length - 1
        ? destination
        : (next?.from_stop ?? "the next stop");
    const distance =
      leg.distance_m >= 50 ? ` (${formatDistance(leg.distance_m)})` : "";
    return {
      line: null,
      text: `Walk ${leg.minutes} min${distance} to ${target}`,
      wait: leg.wait_minutes,
    };
  });
}

const RIDE_NAMES: Record<RouteLeg["mode"], string> = {
  walk: "Walk",
  bus: "Bus",
  tram: "Tram",
  subway: "U-Bahn",
  rail: "Train",
  ferry: "Ferry",
  other: "Ride",
};

export function formatDistance(metres: number): string {
  if (metres < 1000) return `${Math.round(metres / 10) * 10} m`;
  return `${(metres / 1000).toFixed(1)} km`;
}

/** "U2, then Bus 53", or "on foot" for a journey without a ride. */
export function summariseLines(route: CommuteRoute): string {
  const rides = route.legs.filter((leg) => leg.mode !== "walk");
  if (rides.length === 0) return "on foot";
  return rides.map((leg) => leg.line ?? RIDE_NAMES[leg.mode]).join(", then ");
}

/**
 * Why the journey shown is not the only answer: the spread over the area's
 * hexagons, and which figure the ranking uses.
 */
export function spreadSentence(spread: CommuteSpread): string {
  if (spread.fastest_minutes === spread.slowest_minutes) {
    return `From every part of this area the morning trip takes about ${spread.median_minutes} min.`;
  }
  return (
    `Depending on where in the area you live, the morning trip takes ` +
    `${spread.fastest_minutes} to ${spread.slowest_minutes} min. The ranking uses ` +
    `the middle value, ${spread.median_minutes} min.`
  );
}

/**
 * Colours for rides whose timetable gives none (Munich's lists every line as
 * black), one per kind of transport, as journey planners do.
 */
export const MODE_COLOURS: Record<LegMode, string> = {
  walk: "#1d2a7a",
  bus: "#7b3fa0",
  tram: "#c8102e",
  subway: "#0065ae",
  rail: "#2e7d32",
  ferry: "#00838f",
  other: "#5a5a5a",
};

export function legColour(leg: RouteLeg): string {
  if (leg.mode === "walk") return MODE_COLOURS.walk;
  return leg.line_colour ?? MODE_COLOURS[leg.mode];
}

/** Black or white, whichever reads better on the given background. */
export function textOn(background: string): string {
  const value = Number.parseInt(background.slice(1), 16);
  const channel = (shift: number) => {
    const c = ((value >> shift) & 255) / 255;
    return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const luminance =
    0.2126 * channel(16) + 0.7152 * channel(8) + 0.0722 * channel(0);
  // White text meets 4.5:1 down to a luminance of about 0.18.
  return luminance > 0.18 ? "#201e1d" : "#ffffff";
}

export function rideLabel(leg: RouteLeg): string {
  return leg.line ?? RIDE_NAMES[leg.mode];
}

interface MapFeature {
  type: "Feature";
  properties: Record<string, string>;
  geometry: { type: "Point"; coordinates: [number, number] } | RouteLeg["path"];
}

/**
 * GeoJSON for the map, drawn the way journey planners draw a trip: each ride
 * in its line's colour with the line's name on it, walking dotted, a ring at
 * every stop where you get on or off, and a dot where the trip starts.
 */
export function journeyFeatures(routes: CommuteRoute[]) {
  const features: MapFeature[] = [];
  for (const route of routes) {
    for (const leg of route.legs) {
      const colour = legColour(leg);
      const coordinates = leg.path.coordinates;
      features.push({
        type: "Feature",
        properties: { part: leg.mode === "walk" ? "walk" : "ride", colour },
        geometry: leg.path,
      });
      if (leg.mode === "walk" || coordinates.length === 0) continue;
      for (const point of [
        coordinates[0],
        coordinates[coordinates.length - 1],
      ]) {
        features.push({
          type: "Feature",
          properties: { part: "stop", colour },
          geometry: { type: "Point", coordinates: point },
        });
      }
      features.push({
        type: "Feature",
        properties: {
          part: "label",
          colour,
          text: textOn(colour),
          label: rideLabel(leg),
        },
        geometry: {
          type: "Point",
          coordinates: coordinates[Math.floor(coordinates.length / 2)],
        },
      });
    }
  }
  const start = routes[0]?.legs[0]?.path.coordinates[0];
  if (start) {
    features.push({
      type: "Feature",
      properties: { part: "start" },
      geometry: { type: "Point", coordinates: start },
    });
  }
  return { type: "FeatureCollection" as const, features };
}
