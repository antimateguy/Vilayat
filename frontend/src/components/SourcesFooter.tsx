"use client";

import { SampleMark } from "@/components/ui";
import { useSources } from "@/lib/api/hooks";
import { formatDate } from "@/lib/format";

/**
 * Where every dataset comes from and how current it is. This is also where the
 * licence attributions are shown, which several of the sources require.
 */
export function SourcesFooter({ city }: { city: string }) {
  const sources = useSources(city);
  if (!sources.data) return null;

  return (
    <details className="border-hairline rounded-[2px] border px-3 py-2 text-sm">
      <summary className="cursor-pointer font-medium">
        Data sources and dates
      </summary>
      <ul className="mt-2 flex flex-col gap-2.5">
        {sources.data.map((source) => (
          <li key={`${source.used_for}-${source.name}`}>
            <p className="flex flex-wrap items-center gap-x-2 gap-y-1">
              <span className="font-medium">{source.used_for}</span>
              {source.is_sample && <SampleMark />}
            </p>
            <p className="text-ink-2">
              {source.is_sample
                ? "Placeholder"
                : `${source.publisher} · ${source.licence}`}{" "}
              · {formatDate(source.as_of)}
            </p>
          </li>
        ))}
      </ul>
      <p className="text-muted mt-2 text-xs">
        Rent figures are area-level estimates. Job access shows where employers
        that typically hire students cluster; it is not a count of vacancies.
        Base map © OpenStreetMap contributors, served by OpenFreeMap.
      </p>
    </details>
  );
}

/**
 * The publishers whose licences ask to be named wherever their data is shown:
 * the area boundaries and the timetables behind the travel times.
 */
export function MapCredits({ city }: { city: string }) {
  const sources = useSources(city);
  if (!sources.data) return null;
  const named = sources.data.filter(
    (source) =>
      source.used_for === "Area boundaries" ||
      (source.used_for === "Travel times" &&
        !/OpenStreetMap/.test(source.publisher)),
  );
  return (
    <p className="bg-surface/85 text-ink-2 rounded px-1.5 py-0.5 text-[10px] leading-tight">
      {named
        .map((source) => `${source.used_for}: ${source.publisher}`)
        .join(" · ")}
    </p>
  );
}
