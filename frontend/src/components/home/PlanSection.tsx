"use client";

import { useRouter } from "next/navigation";
import { useId, useMemo, useState } from "react";

import { FlagStripe } from "@/components/brand";
import {
  ArrowRight,
  Files,
  MapIcon,
  Search,
  Sparkle,
} from "@/components/icons";
import { SentenceSearch } from "@/components/planner/SentenceSearch";
import { SampleMark } from "@/components/ui";
import {
  useAiStatus,
  useCities,
  useEmployers,
  useSearch,
  useUniversities,
} from "@/lib/api/hooks";
import {
  isImportant,
  PRIORITY_CHIPS,
  toggleImportant,
} from "@/lib/preferences";
import {
  DEFAULT_STATE,
  LIMITS,
  type SearchState,
  toSearchParams,
  toSearchRequest,
} from "@/lib/search-state";
import { useDebouncedValue } from "@/lib/use-debounced-value";

const SUGGESTIONS = [
  "How soon must I register my address?",
  "How many days a year may I work as a student?",
  "Do flatmates share the broadcasting fee?",
  "What do I need for the residence permit?",
];

/**
 * The two cards at the foot of the home page. The planner card holds the same
 * settings as the planner and asks the real API how many areas fit; "See on
 * map" opens the planner with those settings in its address. The question
 * card hands its question to the Ask page.
 */
export function PlanSection() {
  const router = useRouter();
  const [state, setState] = useState<SearchState>(DEFAULT_STATE);
  const change = (changes: Partial<SearchState>) =>
    setState((current) => ({ ...current, ...changes }));

  const cities = useCities();
  const universities = useUniversities(state.city);
  const employers = useEmployers(state.city);
  const campuses = useMemo(
    () =>
      (universities.data ?? []).flatMap((university) =>
        university.campuses.map((campus) => ({ ...campus, university })),
      ),
    [universities.data],
  );
  const campusId =
    campuses.find((campus) => campus.id === state.campusId)?.id ??
    campuses[0]?.id ??
    null;

  const settled = useDebouncedValue(state, 300);
  const search = useSearch(toSearchRequest({ ...settled, campusId }));
  const fitting =
    search.data?.city_id === state.city ? search.data.ranked.length : null;
  const cityName =
    cities.data?.find((city) => city.id === state.city)?.name ?? "the city";

  const seeOnMap = () =>
    router.push(`/planner?${toSearchParams({ ...state, campusId })}`);

  return (
    <section
      id="plan"
      className="mx-auto w-full max-w-[1320px] scroll-mt-4 px-[clamp(16px,4vw,56px)] pt-[clamp(48px,6vw,88px)]"
    >
      <div className="flex flex-col items-center text-center">
        <span className="kicker text-ink-2 mb-3.5">
          Plan your move · Ask the documents
        </span>
        <h2 className="max-w-[24ch] text-[clamp(28px,3.2vw,44px)] leading-[1.08] tracking-[-0.02em]">
          Tell us what you need. We’ll draw the map.
        </h2>
      </div>

      <div className="bg-page mt-[clamp(20px,3vh,36px)] overflow-hidden rounded-[2px] shadow-(--shadow-card)">
        <FlagStripe />
        <div className="flex flex-wrap">
          <div className="bg-surface flex min-w-0 flex-[2_1_420px] flex-col gap-4 p-[clamp(20px,2.4vw,32px)]">
            <div>
              <span className="kicker text-in-green flex items-center gap-2">
                <MapIcon size={18} /> Plan your move
              </span>
              <h3 className="mt-1.5 text-[clamp(22px,2vw,28px)] leading-tight">
                Find where to live
              </h3>
            </div>

            <SentenceSearch
              state={state}
              cities={cities.data ?? []}
              onApply={change}
            />

            <div className="grid grid-cols-1 gap-3.5 sm:grid-cols-[2fr_3fr]">
              <SelectField
                label="City"
                value={state.city}
                onChange={(city) =>
                  change({ city, campusId: null, employerId: null })
                }
                options={(cities.data ?? []).map((city) => ({
                  value: city.id,
                  label: city.name,
                }))}
              />
              <SelectField
                label="University and campus"
                value={campusId === null ? "" : String(campusId)}
                onChange={(value) => change({ campusId: Number(value) })}
                options={campuses.map((campus) => ({
                  value: String(campus.id),
                  label: `${campus.university.short_name}, ${campus.name}`,
                }))}
              />
            </div>

            <div className="grid grid-cols-1 gap-x-6 gap-y-3 sm:grid-cols-2">
              <RangeField
                label="Maximum rent"
                value={state.maxRentEur}
                display={`${state.maxRentEur} EUR a month`}
                range={LIMITS.rent}
                ends={["300", "1,500"]}
                onChange={(maxRentEur) => change({ maxRentEur })}
              />
              <RangeField
                label="Maximum commute"
                value={state.maxCommuteMinutes}
                display={`${state.maxCommuteMinutes} min each way`}
                range={LIMITS.commute}
                ends={["10 min", "90 min"]}
                onChange={(maxCommuteMinutes) => change({ maxCommuteMinutes })}
              />
            </div>

            <SelectField
              label="Part-time employer"
              badge={
                employers.data?.some((employer) => employer.is_sample) ? (
                  <SampleMark what="placeholder list of employers" />
                ) : null
              }
              value={state.employerId === null ? "" : String(state.employerId)}
              onChange={(value) =>
                change({ employerId: value ? Number(value) : null })
              }
              options={[
                { value: "", label: "None" },
                ...(employers.data ?? []).map((employer) => ({
                  value: String(employer.id),
                  label: employer.name,
                })),
              ]}
            />

            <fieldset>
              <legend className="field-label mb-1.5">
                What’s important to you
              </legend>
              <div className="flex flex-wrap gap-2">
                {PRIORITY_CHIPS.map((chip) => (
                  <button
                    key={chip.key}
                    type="button"
                    className="chip"
                    aria-pressed={isImportant(state.weights, chip.key)}
                    onClick={() =>
                      change({
                        weights: toggleImportant(state.weights, chip.key),
                      })
                    }
                  >
                    {chip.label}
                  </button>
                ))}
              </div>
            </fieldset>

            <div className="mt-auto flex flex-wrap items-center justify-between gap-4 pt-1">
              <p
                aria-live="polite"
                className="max-w-[30ch] text-[15px] leading-snug"
              >
                <strong className="text-accent-strong text-[28px] font-semibold">
                  {fitting ?? "…"}
                </strong>{" "}
                areas in {cityName} fit your limits
              </p>
              <button
                type="button"
                onClick={seeOnMap}
                disabled={campusId === null}
                className="bg-accent text-page hover:bg-accent-strong flex items-center gap-3 rounded-full py-2 pr-2 pl-5 text-base font-semibold shadow-(--shadow-float) transition-transform hover:-translate-y-0.5 disabled:opacity-50"
              >
                See on map
                <span className="bg-page text-accent-strong grid size-[42px] place-items-center rounded-full">
                  <Search size={22} />
                </span>
              </button>
            </div>
          </div>

          <AskCard city={state.city} cityName={cityName} />
        </div>
      </div>
    </section>
  );
}

function AskCard({ city, cityName }: { city: string; cityName: string }) {
  const router = useRouter();
  const enabled = useAiStatus().data?.enabled === true;
  const [question, setQuestion] = useState("");
  const go = (text: string) => {
    const params = new URLSearchParams({ city });
    if (text.trim()) params.set("q", text.trim());
    router.push(`/ask?${params}`);
  };

  return (
    <div className="relative flex min-w-0 flex-[3_1_480px] flex-col items-center justify-center gap-5 overflow-hidden px-[clamp(24px,3vw,48px)] py-[clamp(28px,3.5vw,56px)] text-center">
      <span
        aria-hidden
        className="bg-in-saffron pointer-events-none absolute -top-24 -right-20 size-[340px] rounded-full opacity-15 blur-[70px]"
      />
      <span
        aria-hidden
        className="bg-in-green pointer-events-none absolute -bottom-28 -left-16 size-[300px] rounded-full opacity-10 blur-[70px]"
      />
      <span className="kicker text-de-red relative flex items-center gap-2">
        <Files size={18} /> Questions about moving
      </span>
      <h3 className="relative max-w-[14ch] text-[clamp(34px,3.6vw,54px)] leading-[1.08] tracking-[-0.02em]">
        Namaste.{" "}
        <em lang="de" className="text-de-red font-normal">
          Willkommen
        </em>{" "}
        in Deutschland.
      </h3>
      <p className="text-ink-2 relative max-w-[44ch] text-base leading-relaxed">
        Ask about registration, permits, work limits or fees. Answers come from
        the documents stored in Vilayat, and every statement names its source.
      </p>
      {enabled ? (
        <>
          <form
            onSubmit={(event) => {
              event.preventDefault();
              go(question);
            }}
            className="bg-page relative flex w-full max-w-[520px] items-center gap-2 rounded-full py-1.5 pr-1.5 pl-5 shadow-(--shadow-float)"
          >
            <span className="text-saffron-ink">
              <Sparkle size={22} />
            </span>
            <label htmlFor="home-question" className="sr-only">
              Your question
            </label>
            <input
              id="home-question"
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              maxLength={300}
              placeholder="Ask me anything about moving…"
              className="min-h-11 min-w-0 flex-1 bg-transparent text-[17px] outline-none"
            />
            <button
              type="submit"
              aria-label="Ask"
              className="bg-de-red grid size-[46px] flex-none place-items-center rounded-full text-white transition-transform hover:scale-105"
            >
              <ArrowRight size={20} />
            </button>
          </form>
          <span className="text-ink-2 relative mt-1.5 text-[15px]">
            Or ask about:
          </span>
          <div className="relative flex max-w-[560px] flex-wrap justify-center gap-2.5">
            {SUGGESTIONS.map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                onClick={() => go(suggestion)}
                className="bg-surface hover:bg-accent-wash inline-flex items-center gap-2.5 rounded-full px-4 py-2.5 text-left text-sm transition hover:-translate-y-0.5"
              >
                {suggestion}
                <span className="text-accent-strong">
                  <ArrowRight size={16} />
                </span>
              </button>
            ))}
          </div>
          <span className="text-ink-2 relative text-xs">
            Using the {cityName} documents · opens the Ask page
          </span>
        </>
      ) : (
        <p className="border-hairline relative rounded-[2px] border px-4 py-3 text-sm">
          Questions are switched off because no AI model is configured. The
          planner and the comparison work as usual.
        </p>
      )}
    </div>
  );
}

function SelectField({
  label,
  badge,
  value,
  options,
  onChange,
}: {
  label: string;
  badge?: React.ReactNode;
  value: string;
  options: { value: string; label: string }[];
  onChange: (value: string) => void;
}) {
  const id = useId();
  return (
    <div className="min-w-0">
      <div className="mb-1.5 flex min-h-5 items-center gap-2">
        <label htmlFor={id} className="field-label">
          {label}
        </label>
        {badge}
      </div>
      <select
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="input"
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
    </div>
  );
}

function RangeField({
  label,
  value,
  display,
  range,
  ends,
  onChange,
}: {
  label: string;
  value: number;
  display: string;
  range: { min: number; max: number; step: number };
  ends: [string, string];
  onChange: (value: number) => void;
}) {
  const id = useId();
  return (
    <div className="min-w-0">
      <div className="flex items-baseline justify-between gap-2.5">
        <label htmlFor={id} className="field-label">
          {label}
        </label>
        <output
          htmlFor={id}
          className="text-base font-semibold whitespace-nowrap"
        >
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
        className="mt-1 h-6 w-full"
      />
      <div className="text-ink-2 flex justify-between text-xs">
        <span>{ends[0]}</span>
        <span>{ends[1]}</span>
      </div>
    </div>
  );
}
