// The "What's important to you" chips. Each chip is one of the four things the
// ranking actually weighs, so pressing it changes the result for a real
// reason. Pressing raises that weight above every default, the same rule the
// sentence search uses; pressing again puts the default back.

import {
  DEFAULT_STATE,
  WEIGHT_KEYS,
  type WeightKey,
  type Weights,
} from "./search-state";

export const IMPORTANT_WEIGHT = 50;

export const PRIORITY_CHIPS: { key: WeightKey; label: string }[] = [
  { key: "commute", label: "Short commute" },
  { key: "rent", label: "Low rent" },
  { key: "amenities", label: "Shops, cafés and gyms nearby" },
  { key: "job_access", label: "Part-time jobs nearby" },
];

export function isImportant(weights: Weights, key: WeightKey): boolean {
  return weights[key] >= IMPORTANT_WEIGHT;
}

export function toggleImportant(weights: Weights, key: WeightKey): Weights {
  const next = { ...weights };
  next[key] = isImportant(weights, key)
    ? DEFAULT_STATE.weights[key]
    : IMPORTANT_WEIGHT;
  return next;
}

/** How many chips are pressed, for the summary line. */
export function importantCount(weights: Weights): number {
  return WEIGHT_KEYS.filter((key) => isImportant(weights, key)).length;
}
