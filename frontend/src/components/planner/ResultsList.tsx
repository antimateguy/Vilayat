"use client";

import { Meter, SampleMark, Unknown } from "@/components/ui";
import type { RankedArea, SearchResult } from "@/lib/api/schemas";
import { formatEur, formatMinutes, formatScore, isKnown } from "@/lib/format";

interface ResultsListProps {
  result: SearchResult;
  selectedAreaId: number | null;
  /** True while a newer result is being fetched; the old one stays, dimmed. */
  isRefreshing: boolean;
  onSelect: (areaId: number) => void;
}

export function ResultsList({
  result,
  selectedAreaId,
  isRefreshing,
  onSelect,
}: ResultsListProps) {
  const { ranked, excluded, unchecked } = result;

  return (
    <div
      className={`flex flex-col gap-3 transition-opacity ${isRefreshing ? "opacity-60" : ""}`}
    >
      <p aria-live="polite" className="text-sm">
        <strong>{ranked.length}</strong>{" "}
        {ranked.length === 1 ? "area fits" : "areas fit"} your limits
        <span className="text-ink-2">
          {" "}
          · {excluded.length} outside · {unchecked.length} cannot be checked
        </span>
      </p>

      {ranked.length === 0 ? (
        <p className="border-hairline text-ink-2 rounded-[2px] border px-3 py-4 text-sm">
          No area is within both limits. Raise the rent ceiling or allow a
          longer commute.
        </p>
      ) : (
        <ol className="flex flex-col gap-2">
          {ranked.map((item) => (
            <li key={item.area.id}>
              <RankedCard
                item={item}
                selected={item.area.id === selectedAreaId}
                onSelect={onSelect}
              />
            </li>
          ))}
        </ol>
      )}

      {excluded.length > 0 && (
        <details className="border-hairline rounded-[2px] border px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium">
            Outside your limits ({excluded.length})
          </summary>
          <ul className="mt-2 flex flex-col gap-2">
            {excluded.map((item) => (
              <li key={item.area.id} className="text-sm">
                <button
                  type="button"
                  onClick={() => onSelect(item.area.id)}
                  className="font-medium underline-offset-2 hover:underline"
                >
                  {item.area.name}
                </button>
                <span className="text-ink-2 block">
                  {item.violations.join(" ")}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}

      {unchecked.length > 0 && (
        <details className="border-hairline rounded-[2px] border px-3 py-2">
          <summary className="cursor-pointer text-sm font-medium">
            Cannot be checked ({unchecked.length})
          </summary>
          <p className="text-ink-2 mt-2 text-sm">
            A figure needed to check these areas is missing. They are not ranked
            and not ruled out.
          </p>
          <ul className="mt-2 flex flex-col gap-2">
            {unchecked.map((item) => (
              <li key={item.area.id} className="text-sm">
                <button
                  type="button"
                  onClick={() => onSelect(item.area.id)}
                  className="font-medium underline-offset-2 hover:underline"
                >
                  {item.area.name}
                </button>
                <span className="text-ink-2 block">
                  {item.missing.join(" ")}
                </span>
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  );
}

function RankedCard({
  item,
  selected,
  onSelect,
}: {
  item: RankedArea;
  selected: boolean;
  onSelect: (areaId: number) => void;
}) {
  const { rent, commute_minutes: commute } = item.facts;
  return (
    <button
      type="button"
      onClick={() => onSelect(item.area.id)}
      aria-pressed={selected}
      className={`bg-page w-full rounded-[2px] border px-3 py-2.5 text-left transition-colors ${
        selected ? "border-ink" : "border-hairline hover:border-axis"
      }`}
    >
      <div className="flex items-baseline justify-between gap-3">
        <p className="min-w-0 truncate font-medium">
          <span className="text-ink-2 mr-1.5 tabular-nums">{item.rank}.</span>
          {item.area.name}
        </p>
        <p className="shrink-0 text-sm tabular-nums">
          <span className="font-semibold">{formatScore(item.score.total)}</span>
          <span className="text-muted"> / 100</span>
        </p>
      </div>
      <div className="mt-1.5">
        <Meter value={item.score.total} label={`Score of ${item.area.name}`} />
      </div>
      <p className="text-ink-2 mt-2 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
        <span>
          {isKnown(rent) ? (
            <>
              {formatEur(rent.monthly_eur)}
              {rent.is_sample && <SampleMark what="placeholder rent" />}
            </>
          ) : (
            <Unknown what="rent" />
          )}
        </span>
        <span aria-hidden>·</span>
        <span>
          {isKnown(commute) ? (
            `${formatMinutes(commute)} to campus`
          ) : (
            <Unknown what="commute" />
          )}
        </span>
        {item.full_day && (
          <>
            <span aria-hidden>·</span>
            <span>
              {isKnown(item.full_day.total_minutes) ? (
                `${formatMinutes(item.full_day.total_minutes)} a day with the job`
              ) : (
                <Unknown what="day with the job" />
              )}
            </span>
          </>
        )}
      </p>
      <p className="text-ink-2 mt-1.5 text-xs">{item.trade_off}</p>
    </button>
  );
}
