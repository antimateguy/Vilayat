"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useId, useState } from "react";

import { Header } from "@/components/Header";
import { SiteFooter } from "@/components/brand";
import { SourcesFooter } from "@/components/SourcesFooter";
import { ErrorMessage, SectionTitle } from "@/components/ui";
import { useCities, useComparison } from "@/lib/api/hooks";
import type { Comparison } from "@/lib/api/schemas";
import {
  DEFAULT_STATE,
  LIMITS,
  parseSearchState,
  toSearchParams,
} from "@/lib/search-state";
import { photoFor } from "@/lib/universities";
import { useDebouncedValue } from "@/lib/use-debounced-value";

export function ComparisonView() {
  const initialParams = useSearchParams();
  const [budget, setBudget] = useState(() => {
    const state = parseSearchState(
      new URLSearchParams(initialParams.toString()),
    );
    return {
      city: state.city,
      maxRentEur: state.maxRentEur,
      maxCommuteMinutes: state.maxCommuteMinutes,
    };
  });
  const settled = useDebouncedValue(budget, 250);
  const query = toSearchParams({ ...DEFAULT_STATE, ...settled }).toString();
  useEffect(() => {
    window.history.replaceState(
      null,
      "",
      query ? `?${query}` : window.location.pathname,
    );
  }, [query]);

  const cities = useCities();
  const comparison = useComparison(
    settled.city,
    settled.maxRentEur,
    settled.maxCommuteMinutes,
  );
  const data =
    comparison.data?.city_id === budget.city ? comparison.data : undefined;

  return (
    <div className="flex min-h-dvh flex-col">
      <Header current="compare" query={query} />
      <main className="mx-auto flex w-full max-w-5xl flex-1 flex-col gap-8 px-4 py-10 md:px-12">
        <div>
          <h1 className="text-4xl tracking-tight">
            Where does this budget work?
          </h1>
          <p className="text-ink-2 mt-2.5 text-base">
            How many areas are within your rent ceiling and commute limit, for
            each university and campus.
          </p>
        </div>

        <form
          onSubmit={(event) => event.preventDefault()}
          className="grid items-end gap-x-10 gap-y-5 sm:grid-cols-3"
        >
          <fieldset>
            <legend className="mb-1.5">
              <SectionTitle>City</SectionTitle>
            </legend>
            <div className="border-hairline inline-flex overflow-hidden rounded-[2px] border">
              {(cities.data ?? []).map((city) => (
                <label
                  key={city.id}
                  className={`cursor-pointer px-3 py-1.5 text-sm has-focus-visible:outline-2 ${
                    budget.city === city.id
                      ? "bg-accent text-page font-medium"
                      : "text-ink-2 hover:text-ink"
                  }`}
                >
                  <input
                    type="radio"
                    name="city"
                    checked={budget.city === city.id}
                    onChange={() => setBudget({ ...budget, city: city.id })}
                    className="sr-only"
                  />
                  {city.name}
                </label>
              ))}
            </div>
          </fieldset>
          <BudgetSlider
            label="Maximum rent"
            display={`${budget.maxRentEur} EUR a month`}
            value={budget.maxRentEur}
            range={LIMITS.rent}
            onChange={(maxRentEur) => setBudget({ ...budget, maxRentEur })}
          />
          <BudgetSlider
            label="Maximum commute"
            display={`${budget.maxCommuteMinutes} min each way`}
            value={budget.maxCommuteMinutes}
            range={LIMITS.commute}
            onChange={(maxCommuteMinutes) =>
              setBudget({ ...budget, maxCommuteMinutes })
            }
          />
        </form>

        {cities.isError && <ErrorMessage error={cities.error} />}
        {comparison.isError && <ErrorMessage error={comparison.error} />}
        {data ? (
          <div
            className={`grid gap-8 transition-opacity sm:grid-cols-2 ${
              comparison.isPlaceholderData ? "opacity-60" : ""
            }`}
          >
            {data.universities.map((item) => (
              <UniversityCard
                key={item.university.id}
                item={item}
                total={data.total_areas}
                budget={settled}
              />
            ))}
          </div>
        ) : (
          !comparison.isError && <p className="text-ink-2 text-sm">Loading…</p>
        )}

        <SourcesFooter city={budget.city} />
      </main>
      <SiteFooter compact />
    </div>
  );
}

function UniversityCard({
  item,
  total,
  budget,
}: {
  item: Comparison["universities"][number];
  total: number;
  budget: { city: string; maxRentEur: number; maxCommuteMinutes: number };
}) {
  return (
    <section className="bg-page overflow-hidden rounded-[2px] shadow-(--shadow-float)">
      <UniversityPhoto shortName={item.university.short_name} />
      <div className="p-5">
        <h2 className="text-[22px] leading-tight">{item.university.name}</h2>
        <p className="mt-1.5">
          <span className="text-accent-strong text-[34px] font-semibold">
            {item.feasible}
          </span>
          <span className="text-ink-2 text-sm">
            {" "}
            of {total} areas work for at least one campus
          </span>
        </p>
        <ul className="mt-4 flex flex-col gap-4">
          {item.campuses.map((campus) => (
            <li key={campus.campus.id}>
              <div className="flex items-baseline justify-between gap-2 text-sm">
                <span className="font-medium">{campus.campus.name}</span>
                <span className="tabular-nums">
                  {campus.feasible} of {total}
                </span>
              </div>
              {/* One hue for every bar: the bars differ in length, not in colour. */}
              <div
                role="meter"
                aria-valuemin={0}
                aria-valuemax={total}
                aria-valuenow={campus.feasible}
                aria-label={`Feasible areas for ${campus.campus.name}`}
                title={`${campus.feasible} of ${total} areas`}
                className="bg-accent-wash mt-1 h-2.5 overflow-hidden rounded-full"
              >
                <div
                  className="bg-accent h-full rounded-r-full"
                  style={{
                    width: `${total ? (campus.feasible / total) * 100 : 0}%`,
                  }}
                />
              </div>
              <p className="text-ink-2 mt-1 text-xs">
                {campus.excluded} outside your limits
                {campus.unchecked > 0 &&
                  ` · ${campus.unchecked} cannot be checked (a figure is missing)`}
              </p>
              <Link
                href={`/planner?${toSearchParams({
                  ...DEFAULT_STATE,
                  ...budget,
                  campusId: campus.campus.id,
                })}`}
                className="text-accent-strong mt-1 inline-block text-sm underline"
              >
                Plan for this campus
              </Link>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}

/** The university's photograph with its credit, which the licence requires. */
function UniversityPhoto({ shortName }: { shortName: string }) {
  const photo = photoFor(shortName);
  if (!photo) return null;
  return (
    <figure className="relative">
      <div className="halftone aspect-[16/7]">
        {/* eslint-disable-next-line @next/next/no-img-element -- a static export has no image optimiser */}
        <img
          src={photo.src}
          alt={photo.alt}
          loading="lazy"
          className="size-full object-cover"
        />
      </div>
      <figcaption className="bg-page/85 absolute right-1.5 bottom-1.5 rounded-[2px] px-1.5 py-0.5 text-[10px]">
        <a
          href={photo.source}
          target="_blank"
          rel="noopener noreferrer"
          className="underline"
        >
          Photo: {photo.credit}
        </a>
      </figcaption>
    </figure>
  );
}

function BudgetSlider({
  label,
  display,
  value,
  range,
  onChange,
}: {
  label: string;
  display: string;
  value: number;
  range: { min: number; max: number; step: number };
  onChange: (value: number) => void;
}) {
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
