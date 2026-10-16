"use client";

import { useCities, useSources } from "@/lib/api/hooks";
import { formatDate } from "@/lib/format";

/**
 * Every dataset behind each city, read from the API so the list can never
 * drift from what is actually loaded.
 */
export function LiveSources() {
  const cities = useCities();
  if (cities.isError) {
    return (
      <p>
        The list could not be loaded because the server is not reachable right
        now.
      </p>
    );
  }
  if (!cities.data) return <p>Loading the list of datasets…</p>;
  return (
    <>
      {cities.data.map((city) => (
        <CitySources key={city.id} id={city.id} name={city.name} />
      ))}
    </>
  );
}

function CitySources({ id, name }: { id: string; name: string }) {
  const sources = useSources(id);
  return (
    <>
      <h3>{name}</h3>
      {sources.data ? (
        <ul>
          {sources.data.map((source) => (
            <li key={`${source.used_for}-${source.name}`}>
              <strong>{source.used_for}</strong>
              {source.is_sample ? (
                ": placeholder, see above"
              ) : (
                <>
                  :{" "}
                  {source.url ? (
                    <a href={source.url} rel="noreferrer">
                      {source.publisher}
                    </a>
                  ) : (
                    source.publisher
                  )}
                  , {source.licence}
                </>
              )}
              , as of {formatDate(source.as_of)}
            </li>
          ))}
        </ul>
      ) : (
        <p>{sources.isError ? "Could not be loaded." : "Loading…"}</p>
      )}
    </>
  );
}
