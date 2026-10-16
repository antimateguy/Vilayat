import { type OrUnknown, UNKNOWN } from "./api/schemas";

/** What the reader sees in place of a figure the app does not have. */
export const UNKNOWN_LABEL = "Unknown";

export function isKnown<T>(value: OrUnknown<T>): value is T {
  return value !== UNKNOWN;
}

export function formatMinutes(value: OrUnknown<number>): string {
  return isKnown(value) ? `${value} min` : UNKNOWN_LABEL;
}

export function formatEur(value: OrUnknown<number>): string {
  if (!isKnown(value)) return UNKNOWN_LABEL;
  return `${Math.round(value).toLocaleString("en-GB")} EUR`;
}

/** A 0 to 1 score as a whole number out of 100. */
export function formatScore(value: OrUnknown<number>): string {
  return isKnown(value) ? String(Math.round(value * 100)) : UNKNOWN_LABEL;
}

export function formatPercent(value: number): string {
  return `${Math.round(value * 100)}%`;
}

/** "2026-10-05" as "5 Oct 2026". Unparseable input is returned unchanged. */
export function formatDate(value: OrUnknown<string>): string {
  if (!isKnown(value)) return UNKNOWN_LABEL;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return value;
  const months = [
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
  ];
  return `${Number(match[3])} ${months[Number(match[2]) - 1]} ${match[1]}`;
}

const AMENITY_LABELS: Record<string, [string, string]> = {
  supermarket: ["supermarket", "supermarkets"],
  cafe: ["cafe", "cafes"],
  library: ["library", "libraries"],
  gym: ["gym", "gyms"],
};

/** {"cafe": 2, "gym": 1} as ["2 cafes", "1 gym"], in a fixed order. */
export function formatAmenities(counts: Record<string, number>): string[] {
  return Object.keys(AMENITY_LABELS)
    .filter((key) => key in counts)
    .map((key) => {
      const [singular, plural] = AMENITY_LABELS[key];
      return `${counts[key]} ${counts[key] === 1 ? singular : plural}`;
    });
}

export const PREFERENCE_LABELS: Record<string, string> = {
  commute: "Commute",
  rent: "Rent",
  amenities: "Amenities",
  job_access: "Job access",
};
