"use client";

import { type RefObject, useEffect, useRef } from "react";

import {
  ErrorMessage,
  Meter,
  SampleMark,
  SectionTitle,
  Unknown,
} from "@/components/ui";
import { ChevronRight } from "@/components/icons";
import {
  useAreaBriefing,
  useAreaCommute,
  useAreaDetail,
} from "@/lib/api/hooks";
import type {
  CommuteRoute,
  Facts,
  RankedArea,
  SearchResult,
} from "@/lib/api/schemas";
import {
  formatAmenities,
  formatDate,
  formatEur,
  formatMinutes,
  formatPercent,
  formatScore,
  isKnown,
  PREFERENCE_LABELS,
} from "@/lib/format";
import {
  describeSteps,
  legColour,
  spreadSentence,
  summariseLines,
  textOn,
} from "@/lib/route";
import type { Overlay } from "@/lib/search-state";

interface AreaDetailPanelProps {
  areaId: number;
  campusId: number | null;
  employerId: number | null;
  overlay: Overlay;
  result: SearchResult | undefined;
  onClose: () => void;
  /** Folds the panel away to show the whole map; a tab brings it back. */
  onCollapse: () => void;
}

export function AreaDetailPanel({
  areaId,
  campusId,
  employerId,
  overlay,
  result,
  onClose,
  onCollapse,
}: AreaDetailPanelProps) {
  const detail = useAreaDetail(areaId, campusId);
  const commute = useAreaCommute(areaId, campusId, employerId);
  const body = useRef<HTMLDivElement>(null);
  useFocusOnLayer(body, overlay, areaId, [detail.data, commute.data, result]);
  const ranked = result?.ranked.find((item) => item.area.id === areaId);
  const excluded = result?.excluded.find((item) => item.area.id === areaId);
  const unchecked = result?.unchecked.find((item) => item.area.id === areaId);
  const name =
    detail.data?.area.name ??
    (ranked ?? excluded ?? unchecked)?.area.name ??
    "Area";

  return (
    <section
      aria-label={`Details of ${name}`}
      className="bg-surface flex h-full flex-col"
    >
      <div className="border-hairline flex items-start justify-between gap-3 border-b px-4 py-3">
        <div className="min-w-0">
          <h2 className="truncate text-lg font-semibold">{name}</h2>
          <p className="text-ink-2 text-sm">
            {ranked && `Rank ${ranked.rank} of ${result?.ranked.length}`}
            {excluded && "Outside your limits"}
            {unchecked && "Cannot be checked"}
          </p>
        </div>
        <div className="flex shrink-0 gap-1.5">
          <button
            type="button"
            onClick={onCollapse}
            title="Fold the panel away to see the whole map"
            className="btn btn-secondary px-2 py-1.5"
          >
            <ChevronRight size={16} />
            <span className="sr-only">Fold the panel away</span>
          </button>
          <button
            type="button"
            onClick={onClose}
            className="btn btn-secondary shrink-0 px-3 py-1.5 text-sm"
          >
            Close
          </button>
        </div>
      </div>

      <div
        ref={body}
        className="flex flex-1 flex-col gap-5 overflow-y-auto px-4 py-4"
      >
        {excluded && (
          <Verdict title="Why it is excluded" lines={excluded.violations} />
        )}
        {unchecked && (
          <Verdict title="What is missing" lines={unchecked.missing} />
        )}
        {ranked && <ScoreBreakdown item={ranked} />}
        {ranked?.full_day && <FullDay item={ranked} />}
        {campusId !== null && (
          <Journey
            areaId={areaId}
            campusId={campusId}
            employerId={employerId}
          />
        )}
        <Briefing areaId={areaId} />

        {detail.isError && <ErrorMessage error={detail.error} />}
        {detail.data && (
          <>
            <FactsTable
              facts={detail.data.facts}
              returnMinutes={detail.data.return_minutes}
              hasCampus={detail.data.campus !== null}
            />
            <div>
              <SectionTitle>Find a place here</SectionTitle>
              <p className="text-ink-2 mt-1 text-sm">
                This app ranks areas and lists no flats.{" "}
                {detail.data.listing_hint}
              </p>
              <ul className="mt-2 flex flex-col gap-1.5">
                {detail.data.listing_portals.map((portal) => (
                  <li key={portal.name} className="text-sm">
                    <a
                      href={portal.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-accent-strong font-medium underline"
                    >
                      {portal.name}
                    </a>
                    <span className="text-ink-2">
                      {" "}
                      · {portal.offers} · opens in a new tab
                    </span>
                  </li>
                ))}
              </ul>
            </div>
          </>
        )}
        {detail.isPending && <p className="text-ink-2 text-sm">Loading…</p>}
      </div>
    </section>
  );
}

/**
 * The stored summary of the area, if there is a current one. It is read from
 * the database; no model is called when the panel opens.
 */
function Briefing({ areaId }: { areaId: number }) {
  const { data } = useAreaBriefing(areaId);
  if (!data || !isKnown(data.briefing)) return null;
  const { text, model, generated_at, uses_sample_rent } = data.briefing;
  return (
    <div>
      <div className="flex flex-wrap items-center gap-2">
        <SectionTitle>In short</SectionTitle>
        {uses_sample_rent && (
          <SampleMark what="written from a placeholder rent" />
        )}
      </div>
      <p className="mt-1 text-sm leading-relaxed">{text}</p>
      <p className="text-muted mt-1 text-xs">
        Written by an AI model ({model}) on{" "}
        {formatDate(generated_at.slice(0, 10))} from the figures under Facts. It
        adds no information of its own.
      </p>
    </div>
  );
}

function Verdict({ title, lines }: { title: string; lines: string[] }) {
  return (
    <div>
      <SectionTitle>{title}</SectionTitle>
      <ul className="mt-1 flex flex-col gap-1 text-sm">
        {lines.map((line) => (
          <li key={line}>{line}</li>
        ))}
      </ul>
    </div>
  );
}

function ScoreBreakdown({ item }: { item: RankedArea }) {
  return (
    <div>
      <div className="flex items-baseline justify-between">
        <SectionTitle>Why it ranks here</SectionTitle>
        <p className="text-sm tabular-nums">
          <span className="text-base font-semibold">
            {formatScore(item.score.total)}
          </span>
          <span className="text-muted"> / 100</span>
        </p>
      </div>
      <ul className="mt-2 flex flex-col gap-3">
        {item.score.components.map((component) => (
          <li key={component.name} data-focus={component.name}>
            <div className="flex items-baseline justify-between gap-2 text-sm">
              <span className="font-medium">
                {PREFERENCE_LABELS[component.name] ?? component.name}
              </span>
              <span className="text-ink-2 tabular-nums">
                {isKnown(component.value)
                  ? `${formatScore(component.value)} / 100`
                  : "Unknown"}
                {" · counts "}
                {formatPercent(component.share)}
              </span>
            </div>
            {isKnown(component.value) && (
              <div className="mt-1">
                <Meter
                  value={component.value}
                  label={PREFERENCE_LABELS[component.name] ?? component.name}
                />
              </div>
            )}
            <p className="text-ink-2 mt-1 text-sm">{component.reason}</p>
          </li>
        ))}
      </ul>
      <p className="border-hairline mt-3 border-t pt-3 text-sm">
        <span className="font-medium">Trade-off. </span>
        {item.trade_off}
      </p>
    </div>
  );
}

function FullDay({ item }: { item: RankedArea }) {
  const day = item.full_day;
  if (!day) return null;
  const legs: [string, typeof day.total_minutes][] = [
    ["Home to campus (morning)", day.home_to_campus],
    [`Campus to ${day.employer.name}`, day.campus_to_job],
    ["Job to home (evening)", day.job_to_home],
  ];
  return (
    <div>
      <SectionTitle>A day with the job</SectionTitle>
      <table className="mt-1 w-full text-sm">
        <tbody>
          {legs.map(([label, minutes]) => (
            <tr key={label}>
              <th
                scope="row"
                className="text-ink-2 py-0.5 text-left font-normal"
              >
                {label}
              </th>
              <td className="py-0.5 text-right tabular-nums">
                {isKnown(minutes) ? formatMinutes(minutes) : <Unknown />}
              </td>
            </tr>
          ))}
          <tr className="border-hairline border-t">
            <th scope="row" className="py-1 text-left font-medium">
              Total travel
            </th>
            <td className="py-1 text-right font-medium tabular-nums">
              {isKnown(day.total_minutes) ? (
                formatMinutes(day.total_minutes)
              ) : (
                <Unknown />
              )}
            </td>
          </tr>
        </tbody>
      </table>
      <p className="text-ink-2 mt-1 text-sm">
        {isKnown(day.extra_minutes)
          ? `${formatMinutes(day.extra_minutes)} more than a day without the job.`
          : "A leg of this day has no stored travel time, so the total is unknown."}
      </p>
    </div>
  );
}

function FactsTable({
  facts,
  returnMinutes,
  hasCampus,
}: {
  facts: Facts;
  returnMinutes: number | "UNKNOWN";
  hasCampus: boolean;
}) {
  const { rent, amenities, job_access: jobs } = facts;
  return (
    <div>
      <SectionTitle>Facts</SectionTitle>
      <dl className="mt-1 flex flex-col gap-2.5 text-sm">
        <div>
          <dt className="text-ink-2">Rent</dt>
          <dd>
            {isKnown(rent) ? (
              <>
                <span className="font-medium">
                  {formatEur(rent.monthly_eur)} a month
                </span>
                {rent.is_sample ? (
                  // The asterisk explains a placeholder; its made-up basis
                  // and source label would only repeat it as a warning.
                  <SampleMark what="placeholder rent" />
                ) : (
                  <span className="text-ink-2 block">
                    {rent.basis}. Source: {rent.source},{" "}
                    {formatDate(rent.as_of)}.
                  </span>
                )}
              </>
            ) : (
              <Unknown />
            )}
          </dd>
        </div>
        {hasCampus && (
          <div data-focus="commute-fact">
            <dt className="text-ink-2">Commute by public transport</dt>
            <dd>
              {isKnown(facts.commute_minutes) ? (
                <span className="font-medium">
                  {formatMinutes(facts.commute_minutes)} to campus
                </span>
              ) : (
                <Unknown what="to campus" />
              )}
              <span className="text-ink-2">
                {" · "}
                {isKnown(returnMinutes) ? (
                  `${formatMinutes(returnMinutes)} back in the evening`
                ) : (
                  <Unknown what="back" />
                )}
              </span>
            </dd>
          </div>
        )}
        <div data-focus="amenities-fact">
          <dt className="text-ink-2">Everyday amenities in the area</dt>
          <dd>
            {isKnown(amenities) ? (
              formatAmenities(amenities).join(", ")
            ) : (
              <Unknown />
            )}
          </dd>
        </div>
        <div data-focus="job_access-fact">
          <dt className="text-ink-2">Part-time job access</dt>
          <dd>
            {isKnown(jobs) ? (
              <>
                <span className="font-medium">
                  {formatScore(jobs.score)} / 100
                </span>
                <span className="text-ink-2">
                  {" "}
                  · about {jobs.places_nearby} cafes, restaurants, bars and
                  shops within 2 km
                </span>
              </>
            ) : (
              <Unknown />
            )}
            <span className="text-muted block text-xs">
              A proxy for where such employers cluster, not a count of
              vacancies.
            </span>
          </dd>
        </div>
      </dl>
    </div>
  );
}

/**
 * How the commute goes: one typical journey step by step, and how much the
 * time varies across the area; with an employer pinned, the afternoon leg from
 * campus to work as well. All of it was worked out offline; nothing is routed
 * while the student waits. On the commute layer the map draws the same trips.
 */
function Journey({
  areaId,
  campusId,
  employerId,
}: {
  areaId: number;
  campusId: number;
  employerId: number | null;
}) {
  const commute = useAreaCommute(areaId, campusId, employerId);
  if (!commute.data) return null;
  const { route, spread, campus, employer, to_job } = commute.data;
  if (!route && !spread) return null;

  return (
    <div data-focus="commute-trip">
      <SectionTitle>Getting to {campus.name}</SectionTitle>
      {route && <Trip route={route} when="leaving at" destination="campus" />}
      {spread && (
        <p className="text-ink-2 mt-2 text-sm">
          {spreadSentence(spread)}
          {route &&
            " The trip above starts in the part of the area closest to that value; switch the map to Commute to see it drawn."}
        </p>
      )}
      {!route && (
        <p className="text-ink-2 mt-1 text-xs">
          The step-by-step trip for this area has not been worked out yet.
        </p>
      )}
      {employer && to_job && (
        <div className="mt-4">
          <SectionTitle>Then on to {employer.name}</SectionTitle>
          <Trip
            route={to_job}
            when="leaving campus at"
            destination={employer.name}
          />
        </div>
      )}
    </div>
  );
}

function Trip({
  route,
  when,
  destination,
}: {
  route: CommuteRoute;
  when: string;
  destination: string;
}) {
  return (
    <>
      <p className="mt-1 text-sm">
        <span className="font-medium">
          A typical trip: {route.total_minutes} min
        </span>
        <span className="text-ink-2">
          {" "}
          by {summariseLines(route)}, {when} {route.departs_at}
        </span>
      </p>
      <ol className="border-hairline mt-2 flex flex-col gap-2 border-l-2 pl-3 text-sm">
        {describeSteps(route.legs, destination).map((step, index) => {
          const leg = route.legs[index];
          const colour = legColour(leg);
          return (
            <li key={index}>
              {step.wait > 0 && (
                <span className="text-ink-2 block text-xs">
                  Wait about {step.wait} min
                </span>
              )}
              {step.line && (
                <span
                  className="mr-1.5 rounded-[2px] px-1.5 py-0.5 text-xs font-semibold"
                  style={{ background: colour, color: textOn(colour) }}
                >
                  {step.line}
                </span>
              )}
              {step.text}
            </li>
          );
        })}
      </ol>
    </>
  );
}

/** Where each layer's information sits in the panel, best first. */
const FOCUS_TARGETS: Record<Overlay, string[]> = {
  none: [],
  commute: ["commute-trip", "commute", "commute-fact"],
  amenities: ["amenities", "amenities-fact"],
  job_access: ["job_access", "job_access-fact"],
};

/**
 * When the map switches to a layer, the panel scrolls to what that layer is
 * about (the trip, the amenities, the job access) and marks it for a moment,
 * so the map and the panel tell the same story. On the Ranking layer the panel
 * starts from the top. It happens once per layer and area; scrolling by hand
 * afterwards is left alone.
 */
function useFocusOnLayer(
  body: RefObject<HTMLDivElement | null>,
  overlay: Overlay,
  areaId: number,
  loaded: unknown[],
) {
  const done = useRef("");
  useEffect(() => {
    const container = body.current;
    const key = `${overlay}:${areaId}`;
    if (!container || done.current === key) return;
    if (overlay === "none") {
      container.scrollTo({ top: 0 });
      done.current = key;
      return;
    }
    const target = FOCUS_TARGETS[overlay]
      .map((name) =>
        container.querySelector<HTMLElement>(`[data-focus="${name}"]`),
      )
      .find((element) => element !== null);
    // The block may not have loaded yet; this runs again when it has.
    if (!target) return;
    done.current = key;
    const offset =
      target.getBoundingClientRect().top -
      container.getBoundingClientRect().top +
      container.scrollTop;
    const centred = offset - (container.clientHeight - target.offsetHeight) / 2;
    container.scrollTo({ top: Math.max(0, centred), behavior: "smooth" });
    target.classList.remove("focus-flash");
    // Restart the animation even if the same block was marked before.
    void target.offsetWidth;
    target.classList.add("focus-flash");
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [body, overlay, areaId, ...loaded]);
}
