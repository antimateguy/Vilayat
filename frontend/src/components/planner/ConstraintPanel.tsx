"use client";

import { useId } from "react";

import { SampleMark, SectionTitle } from "@/components/ui";
import type { City, Employer, University } from "@/lib/api/schemas";
import { formatPercent, PREFERENCE_LABELS } from "@/lib/format";
import {
  DEFAULT_STATE,
  hasUsableWeights,
  LIMITS,
  type SearchState,
  WEIGHT_KEYS,
} from "@/lib/search-state";

interface ConstraintPanelProps {
  state: SearchState;
  /** The campus in use, which may be a default chosen before the student picked one. */
  campusId: number | null;
  cities: City[];
  universities: University[];
  employers: Employer[];
  onChange: (changes: Partial<SearchState>) => void;
}

export function ConstraintPanel({
  state,
  campusId,
  cities,
  universities,
  employers,
  onChange,
}: ConstraintPanelProps) {
  const campusField = useId();
  const employerField = useId();
  const weightSum = WEIGHT_KEYS.reduce(
    (sum, key) => sum + state.weights[key],
    0,
  );

  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => event.preventDefault()}
    >
      <fieldset>
        <legend className="mb-1.5">
          <SectionTitle>City</SectionTitle>
        </legend>
        <div className="border-hairline inline-flex overflow-hidden rounded-[2px] border">
          {cities.map((city) => (
            <label
              key={city.id}
              className={`cursor-pointer px-3 py-1.5 text-sm has-focus-visible:outline-2 ${
                state.city === city.id
                  ? "bg-accent text-page font-medium"
                  : "bg-surface text-ink-2 hover:text-ink"
              }`}
            >
              <input
                type="radio"
                name="city"
                value={city.id}
                checked={state.city === city.id}
                onChange={() =>
                  // A campus, employer or area of the old city means nothing in the new one.
                  onChange({
                    city: city.id,
                    campusId: null,
                    employerId: null,
                    areaId: null,
                  })
                }
                className="sr-only"
              />
              {city.name}
            </label>
          ))}
        </div>
      </fieldset>

      <div>
        <label htmlFor={campusField} className="mb-1.5 block">
          <SectionTitle>Campus</SectionTitle>
        </label>
        <select
          id={campusField}
          value={campusId ?? ""}
          onChange={(event) =>
            onChange({ campusId: Number(event.target.value), areaId: null })
          }
          className="input"
        >
          {universities.map((university) => (
            <optgroup key={university.id} label={university.name}>
              {university.campuses.map((campus) => (
                <option key={campus.id} value={campus.id}>
                  {university.short_name}, {campus.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
      </div>

      <Slider
        label="Maximum rent"
        value={state.maxRentEur}
        display={`${state.maxRentEur} EUR a month`}
        range={LIMITS.rent}
        onChange={(maxRentEur) => onChange({ maxRentEur })}
      />
      <Slider
        label="Maximum commute"
        value={state.maxCommuteMinutes}
        display={`${state.maxCommuteMinutes} min each way`}
        range={LIMITS.commute}
        onChange={(maxCommuteMinutes) => onChange({ maxCommuteMinutes })}
      />

      <div>
        <label
          htmlFor={employerField}
          className="mb-1.5 flex items-center gap-2"
        >
          <SectionTitle>Pin an employer (optional)</SectionTitle>
          {employers.some((employer) => employer.is_sample) && (
            <SampleMark what="placeholder list of employers" />
          )}
        </label>
        <select
          id={employerField}
          value={state.employerId ?? ""}
          onChange={(event) =>
            onChange({
              employerId: event.target.value
                ? Number(event.target.value)
                : null,
            })
          }
          className="input"
        >
          <option value="">None</option>
          {employers.map((employer) => (
            <option key={employer.id} value={employer.id}>
              {employer.name}
            </option>
          ))}
        </select>
        <p className="text-muted mt-1 text-xs">
          Shows the travel for a day with that job. It never hides an area.
        </p>
      </div>

      <details className="border-hairline rounded-[2px] border px-3 py-2">
        <summary className="cursor-pointer text-sm font-medium">
          What matters most to you
        </summary>
        <div className="mt-3 flex flex-col gap-3">
          {WEIGHT_KEYS.map((key) => (
            <Slider
              key={key}
              label={PREFERENCE_LABELS[key]}
              value={state.weights[key]}
              display={
                weightSum > 0
                  ? formatPercent(state.weights[key] / weightSum)
                  : "0%"
              }
              range={LIMITS.weight}
              onChange={(value) =>
                onChange({ weights: { ...state.weights, [key]: value } })
              }
            />
          ))}
          {!hasUsableWeights(state.weights) && (
            <p role="alert" className="text-critical text-sm">
              Move at least one slider above zero to rank the areas.
            </p>
          )}
          <button
            type="button"
            onClick={() => onChange({ weights: DEFAULT_STATE.weights })}
            className="text-accent-strong self-start text-sm underline"
          >
            Reset to the defaults
          </button>
        </div>
      </details>
    </form>
  );
}

interface SliderProps {
  label: string;
  value: number;
  display: string;
  range: { min: number; max: number; step: number };
  onChange: (value: number) => void;
}

function Slider({ label, value, display, range, onChange }: SliderProps) {
  const id = useId();
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2">
        <label htmlFor={id}>
          <SectionTitle>{label}</SectionTitle>
        </label>
        <output htmlFor={id} className="text-sm font-medium tabular-nums">
          {display}
        </output>
      </div>
      <input
        id={id}
        type="range"
        min={range.min}
        max={range.max}
        step={range.step}
        value={value}
        onChange={(event) => onChange(Number(event.target.value))}
        className="w-full"
      />
    </div>
  );
}
