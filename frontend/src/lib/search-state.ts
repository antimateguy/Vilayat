// The search settings live in the page address, so a link reproduces a search.
// This module converts between the address and a validated settings object.
// Nothing here touches the browser, which keeps it easy to test.

export const WEIGHT_KEYS = [
  "commute",
  "rent",
  "amenities",
  "job_access",
] as const;
export type WeightKey = (typeof WEIGHT_KEYS)[number];
export type Weights = Record<WeightKey, number>;

export const OVERLAYS = ["none", "commute", "amenities", "job_access"] as const;
export type Overlay = (typeof OVERLAYS)[number];

export interface SearchState {
  city: string;
  /** null until the list of campuses has loaded and one is chosen. */
  campusId: number | null;
  maxRentEur: number;
  maxCommuteMinutes: number;
  /** Slider positions from 0 to 100; only their proportions matter. */
  weights: Weights;
  employerId: number | null;
  /** Hexagon layer drawn over the map. */
  overlay: Overlay;
  /** The area whose detail panel is open. */
  areaId: number | null;
}

export const LIMITS = {
  rent: { min: 300, max: 1500, step: 25 },
  commute: { min: 10, max: 90, step: 5 },
  weight: { min: 0, max: 100, step: 5 },
} as const;

export const DEFAULT_STATE: SearchState = {
  city: "munich",
  campusId: null,
  maxRentEur: 800,
  maxCommuteMinutes: 40,
  weights: { commute: 35, rent: 35, amenities: 15, job_access: 15 },
  employerId: null,
  overlay: "none",
  areaId: null,
};

const WEIGHT_PARAMS: Record<WeightKey, string> = {
  commute: "wc",
  rent: "wr",
  amenities: "wa",
  job_access: "wj",
};

function integer(value: string | null): number | null {
  if (value === null || !/^\d{1,6}$/.test(value)) return null;
  return Number(value);
}

function clamp(value: number, range: { min: number; max: number }): number {
  return Math.min(range.max, Math.max(range.min, value));
}

/** Read settings from a query string. Anything missing or invalid falls back to the default. */
export function parseSearchState(params: URLSearchParams): SearchState {
  const city = params.get("city");
  const overlay = params.get("layer");
  const rent = integer(params.get("rent"));
  const commute = integer(params.get("commute"));

  const weights = { ...DEFAULT_STATE.weights };
  for (const key of WEIGHT_KEYS) {
    const value = integer(params.get(WEIGHT_PARAMS[key]));
    if (value !== null) weights[key] = clamp(value, LIMITS.weight);
  }

  return {
    city: city && /^[a-z][a-z-]{0,31}$/.test(city) ? city : DEFAULT_STATE.city,
    campusId: integer(params.get("campus")),
    maxRentEur:
      rent === null ? DEFAULT_STATE.maxRentEur : clamp(rent, LIMITS.rent),
    maxCommuteMinutes:
      commute === null
        ? DEFAULT_STATE.maxCommuteMinutes
        : clamp(commute, LIMITS.commute),
    weights,
    employerId: integer(params.get("employer")),
    overlay: (OVERLAYS as readonly string[]).includes(overlay ?? "")
      ? (overlay as Overlay)
      : DEFAULT_STATE.overlay,
    areaId: integer(params.get("area")),
  };
}

/** Write settings to a query string, leaving out whatever equals the default. */
export function toSearchParams(state: SearchState): URLSearchParams {
  const params = new URLSearchParams();
  if (state.city !== DEFAULT_STATE.city) params.set("city", state.city);
  if (state.campusId !== null) params.set("campus", String(state.campusId));
  if (state.maxRentEur !== DEFAULT_STATE.maxRentEur) {
    params.set("rent", String(state.maxRentEur));
  }
  if (state.maxCommuteMinutes !== DEFAULT_STATE.maxCommuteMinutes) {
    params.set("commute", String(state.maxCommuteMinutes));
  }
  for (const key of WEIGHT_KEYS) {
    if (state.weights[key] !== DEFAULT_STATE.weights[key]) {
      params.set(WEIGHT_PARAMS[key], String(state.weights[key]));
    }
  }
  if (state.employerId !== null)
    params.set("employer", String(state.employerId));
  if (state.overlay !== DEFAULT_STATE.overlay)
    params.set("layer", state.overlay);
  if (state.areaId !== null) params.set("area", String(state.areaId));
  return params;
}

/** The body of POST /search, or null while no campus is chosen. */
export function toSearchRequest(state: SearchState) {
  if (state.campusId === null) return null;
  return {
    campus_id: state.campusId,
    max_commute_minutes: state.maxCommuteMinutes,
    max_rent_eur: state.maxRentEur,
    weights: state.weights,
    employer_id: state.employerId,
  };
}

/** All sliders at zero would make ranking impossible; the API refuses it. */
export function hasUsableWeights(weights: Weights): boolean {
  return WEIGHT_KEYS.some((key) => weights[key] > 0);
}

/** Changing any of these asks a new question, which is answered on the
 * Ranking layer, framed afresh. Choosing an area or a layer does not. */
const SEARCH_KEYS = [
  "city",
  "campusId",
  "maxRentEur",
  "maxCommuteMinutes",
  "employerId",
  "weights",
] as const;

export function searchChanged(
  current: SearchState,
  changes: Partial<SearchState>,
): boolean {
  return SEARCH_KEYS.some(
    (key) =>
      key in changes &&
      JSON.stringify(changes[key]) !== JSON.stringify(current[key]),
  );
}
