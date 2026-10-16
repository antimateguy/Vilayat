// Turning the server's reading of a sentence into changes to the search
// settings. Pure logic, so it is tested without a browser. The server has
// already checked every value against the catalogue; here the values are only
// fitted to what the sliders can show.

import type { Intent } from "./api/schemas";
import { PREFERENCE_LABELS } from "./format";
import {
  LIMITS,
  type SearchState,
  WEIGHT_KEYS,
  type Weights,
} from "./search-state";

export interface AppliedIntent {
  /** The settings to change. Empty when the sentence gave none. */
  changes: Partial<SearchState>;
  /** One line per setting that was filled in, for the student to check. */
  applied: string[];
  /** What was assumed, adjusted, or asked for but not usable. */
  notes: string[];
}

interface Range {
  min: number;
  max: number;
  step: number;
}

/** The nearest value the slider can take. */
export function snapToRange(value: number, range: Range): number {
  const clamped = Math.min(range.max, Math.max(range.min, value));
  return (
    range.min + Math.round((clamped - range.min) / range.step) * range.step
  );
}

export function applyIntent(
  state: SearchState,
  intent: Intent,
  cities: { id: string; name: string }[],
): AppliedIntent {
  const changes: Partial<SearchState> = {};
  const applied: string[] = [];
  const notes: string[] = [];

  if (intent.city_id !== null && intent.city_id !== state.city) {
    // A campus, employer or open area of the old city means nothing in the new one.
    Object.assign(changes, {
      city: intent.city_id,
      campusId: null,
      employerId: null,
      areaId: null,
    });
    const name =
      cities.find((city) => city.id === intent.city_id)?.name ?? intent.city_id;
    applied.push(`City: ${name}`);
  }

  if (intent.campus !== null) {
    changes.campusId = intent.campus.id;
    changes.areaId = null;
    applied.push(
      `Campus: ${intent.campus.university_short_name}, ${intent.campus.name}`,
    );
  }

  if (intent.max_rent_eur !== null) {
    changes.maxRentEur = snapToRange(intent.max_rent_eur, LIMITS.rent);
    applied.push(`Maximum rent: ${changes.maxRentEur} EUR a month`);
    if (changes.maxRentEur !== intent.max_rent_eur) {
      notes.push(
        `You said ${intent.max_rent_eur} EUR. The rent slider goes from ` +
          `${LIMITS.rent.min} to ${LIMITS.rent.max} in steps of ${LIMITS.rent.step}, ` +
          `so ${changes.maxRentEur} EUR is used.`,
      );
    }
  }

  if (intent.max_commute_minutes !== null) {
    changes.maxCommuteMinutes = snapToRange(
      intent.max_commute_minutes,
      LIMITS.commute,
    );
    applied.push(`Maximum commute: ${changes.maxCommuteMinutes} min each way`);
    if (changes.maxCommuteMinutes !== intent.max_commute_minutes) {
      notes.push(
        `You said ${intent.max_commute_minutes} min. The commute slider goes from ` +
          `${LIMITS.commute.min} to ${LIMITS.commute.max} in steps of ` +
          `${LIMITS.commute.step}, so ${changes.maxCommuteMinutes} min is used.`,
      );
    }
  }

  if (intent.employer !== null) {
    changes.employerId = intent.employer.id;
    applied.push(`Employer pinned: ${intent.employer.name}`);
  }

  if (intent.weights !== null) {
    const weights = {} as Weights;
    for (const key of WEIGHT_KEYS) {
      // The server sends shares such as 0.35; the sliders run from 0 to 100.
      weights[key] = snapToRange(intent.weights[key] * 100, LIMITS.weight);
    }
    changes.weights = weights;
    applied.push(
      "What matters most: " +
        WEIGHT_KEYS.map(
          (key) => `${PREFERENCE_LABELS[key].toLowerCase()} ${weights[key]}`,
        ).join(", "),
    );
  }

  return { changes, applied, notes: [...notes, ...intent.notes] };
}
