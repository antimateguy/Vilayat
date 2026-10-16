"use client";

import { useSearchParams } from "next/navigation";
import { type ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { InfoLinks } from "@/components/brand";
import { Header } from "@/components/Header";
import {
  ChevronLeft,
  ChevronRight,
  Crosshair,
  Minus,
  Plus,
} from "@/components/icons";
import { MapCredits, SourcesFooter } from "@/components/SourcesFooter";
import { ErrorMessage } from "@/components/ui";
import {
  useAreaCommute,
  useAreaLayer,
  useCellLayer,
  useCities,
  useEmployers,
  useSearch,
  useTransitLayer,
  useUniversities,
} from "@/lib/api/hooks";
import type { CommuteRoute } from "@/lib/api/schemas";
import {
  DEFAULT_STATE,
  hasUsableWeights,
  parseSearchState,
  type SearchState,
  searchChanged,
  toSearchParams,
  toSearchRequest,
} from "@/lib/search-state";
import { useDebouncedValue } from "@/lib/use-debounced-value";

import { AreaDetailPanel } from "./AreaDetailPanel";
import { ConstraintPanel } from "./ConstraintPanel";
import { LayerSwitch, Legend, MapExtrasBar } from "./MapControls";
import { type MapExtras, type MapHandle, MapView } from "./MapView";
import { ResultsList } from "./ResultsList";
import { SentenceSearch } from "./SentenceSearch";

const NO_EXTRAS: MapExtras = {
  universities: false,
  employers: false,
  transit: false,
};

export function Planner() {
  const initialParams = useSearchParams();
  const [state, setState] = useState<SearchState>(() =>
    parseSearchState(new URLSearchParams(initialParams.toString())),
  );
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [extras, setExtras] = useState<MapExtras>(NO_EXTRAS);
  const map = useRef<MapHandle>(null);

  const change = (changes: Partial<SearchState>) => {
    // A newly chosen area opens its panel, even if the last one was folded away.
    if (changes.areaId != null) setRightCollapsed(false);
    setState((current) => {
      const next = { ...current, ...changes };
      // A new question is answered on the Ranking layer, framed afresh.
      return searchChanged(current, changes) && !("overlay" in changes)
        ? { ...next, overlay: "none" }
        : next;
    });
  };

  // Sliders update the screen at once; the address bar and the API follow when
  // the value has settled.
  const settled = useDebouncedValue(state, 250);
  useEffect(() => {
    const query = toSearchParams(settled).toString();
    window.history.replaceState(
      null,
      "",
      query ? `?${query}` : window.location.pathname,
    );
  }, [settled]);

  const cities = useCities();
  const universities = useUniversities(state.city);
  const employers = useEmployers(state.city);

  // Until the student picks a campus, the first one of the city is used.
  const campuses = useMemo(
    () =>
      (universities.data ?? []).flatMap((university) =>
        university.campuses.map((campus) => ({ ...campus, university })),
      ),
    [universities.data],
  );
  const campus =
    campuses.find((item) => item.id === state.campusId) ?? campuses[0] ?? null;
  const campusId = campus?.id ?? null;
  const employer =
    employers.data?.find((item) => item.id === state.employerId) ?? null;
  const employerId = employer?.id ?? null;

  const request = useMemo(
    () =>
      hasUsableWeights(settled.weights)
        ? toSearchRequest({ ...settled, campusId, employerId })
        : null,
    [settled, campusId, employerId],
  );
  const search = useSearch(request);
  // A result kept from the previous city must not be shown for the new one.
  const result = search.data?.city_id === state.city ? search.data : undefined;

  const areaLayer = useAreaLayer(state.city, null);
  const cellLayer = useCellLayer(state.city, state.overlay, campusId);
  const commute = useAreaCommute(state.areaId, campusId, employerId);
  const transit = useTransitLayer(state.city, extras.transit);
  const journey = useMemo(
    () =>
      [commute.data?.route, commute.data?.to_job].filter(
        (route): route is CommuteRoute => route != null,
      ),
    [commute.data],
  );

  const campusPin = useMemo(
    () =>
      campus && {
        name: `${campus.university.short_name}, ${campus.name}`,
        lat: campus.lat,
        lon: campus.lon,
      },
    [campus],
  );
  const employerPin = useMemo(
    () =>
      employer && { name: employer.name, lat: employer.lat, lon: employer.lon },
    [employer],
  );
  const campusPlaces = useMemo(
    () =>
      campuses.map((item) => ({
        id: item.id,
        name: `${item.university.short_name}, ${item.name}`,
        lat: item.lat,
        lon: item.lon,
      })),
    [campuses],
  );
  const employerPlaces = useMemo(() => employers.data ?? [], [employers.data]);

  const budgetQuery = toSearchParams({
    ...DEFAULT_STATE,
    city: state.city,
    maxRentEur: state.maxRentEur,
    maxCommuteMinutes: state.maxCommuteMinutes,
  }).toString();
  const loadError = cities.error ?? universities.error ?? employers.error;
  const panelShown = state.areaId !== null && !rightCollapsed;

  return (
    <div className="flex min-h-dvh flex-col md:h-dvh">
      <Header current="planner" query={budgetQuery} />
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <main className="border-hairline sticky top-0 z-10 h-[42dvh] shrink-0 overflow-hidden border-b md:relative md:order-2 md:h-auto md:flex-1 md:border-b-0">
          <MapView
            ref={map}
            areaLayer={areaLayer.isPlaceholderData ? undefined : areaLayer.data}
            result={result}
            overlay={state.overlay}
            cellLayer={cellLayer.data}
            campus={campusPin}
            employer={employerPin}
            selectedAreaId={state.areaId}
            journey={state.areaId !== null ? journey : []}
            rightPanelOpen={panelShown}
            extras={extras}
            campuses={campusPlaces}
            employers={employerPlaces}
            transit={transit.data}
            onSelectArea={(areaId) => change({ areaId })}
            onPickCampus={(id) => change({ campusId: id })}
            onPickEmployer={(id) =>
              change({ employerId: id === employerId ? null : id })
            }
          />

          {/* Top left: what the map shows. The map's own controls sit at
              z-index 2, so these are raised above them. */}
          <div
            className={`absolute top-2 z-10 flex max-w-[calc(100%-1rem)] flex-col items-start gap-1.5 ${
              leftCollapsed ? "left-8" : "left-2"
            }`}
          >
            <LayerSwitch
              overlay={state.overlay}
              commuteAvailable={campusId !== null}
              onChange={(overlay) => change({ overlay })}
            />
            <MapExtrasBar
              extras={extras}
              onToggle={(key) =>
                setExtras((current) => ({ ...current, [key]: !current[key] }))
              }
            />
          </div>

          {leftCollapsed && (
            <PaneTab
              side="left"
              label="Show the search pane"
              onClick={() => setLeftCollapsed(false)}
            />
          )}
          {state.areaId !== null && rightCollapsed && (
            <PaneTab
              side="right"
              label="Show the area's details"
              onClick={() => setRightCollapsed(false)}
            />
          )}

          {/* Bottom left: the legend and the map's own buttons, where no pane
              can cover them. */}
          <div
            className={`absolute bottom-2 z-10 flex items-end gap-2 ${
              leftCollapsed ? "left-8" : "left-2"
            }`}
          >
            <div className="hidden sm:block">
              <Legend overlay={state.overlay} />
            </div>
            <div className="flex flex-col gap-1.5">
              <MapButton
                label="Centre the map on what matters now"
                onClick={() => map.current?.centre()}
              >
                <Crosshair />
              </MapButton>
              {/* Phones zoom with two fingers, and their short map has no
                  room for these. */}
              <div className="bg-page hidden flex-col overflow-hidden rounded-[2px] shadow-(--shadow-float) sm:flex">
                <MapButton
                  label="Zoom in"
                  onClick={() => map.current?.zoomIn()}
                  joined
                >
                  <Plus />
                </MapButton>
                <span aria-hidden className="bg-hairline mx-1.5 h-px" />
                <MapButton
                  label="Zoom out"
                  onClick={() => map.current?.zoomOut()}
                  joined
                >
                  <Minus />
                </MapButton>
              </div>
            </div>
          </div>
          <div
            className={`absolute bottom-8 max-w-[60%] ${
              panelShown ? "right-2 md:right-[388px]" : "right-2"
            }`}
          >
            <MapCredits city={state.city} />
          </div>

          {panelShown && (
            <div className="border-hairline fixed inset-0 z-30 md:absolute md:inset-y-0 md:right-0 md:left-auto md:w-[380px] md:border-l md:shadow-lg">
              <AreaDetailPanel
                areaId={state.areaId!}
                campusId={campusId}
                employerId={employerId}
                overlay={state.overlay}
                result={result}
                onClose={() => change({ areaId: null })}
                onCollapse={() => setRightCollapsed(true)}
              />
            </div>
          )}
        </main>

        {/* relative: the screen-reader-only labels inside are positioned and
            would otherwise stretch the page beyond the window. */}
        <aside
          className={`border-hairline bg-page relative md:w-[380px] md:shrink-0 md:overflow-y-auto md:border-r ${
            leftCollapsed ? "md:hidden" : ""
          }`}
        >
          <div className="flex flex-col gap-5 p-4">
            <button
              type="button"
              onClick={() => setLeftCollapsed(true)}
              className="text-ink-2 hover:text-accent-strong -mb-3 hidden items-center gap-1 self-end text-xs md:inline-flex"
            >
              <ChevronLeft size={14} /> Hide this pane
            </button>
            {loadError ? (
              <ErrorMessage error={loadError} />
            ) : (
              <>
                <SentenceSearch
                  state={state}
                  cities={cities.data ?? []}
                  onApply={change}
                />
                <ConstraintPanel
                  state={state}
                  campusId={campusId}
                  cities={cities.data ?? []}
                  universities={universities.data ?? []}
                  employers={employers.data ?? []}
                  onChange={change}
                />
              </>
            )}

            <div className="sm:hidden">
              <Legend overlay={state.overlay} />
            </div>

            {search.isError && <ErrorMessage error={search.error} />}
            {result ? (
              <ResultsList
                result={result}
                selectedAreaId={state.areaId}
                isRefreshing={search.isPlaceholderData}
                onSelect={(areaId) => change({ areaId })}
              />
            ) : (
              !search.isError &&
              !loadError && <p className="text-ink-2 text-sm">Loading areas…</p>
            )}

            <SourcesFooter city={state.city} />
            <InfoLinks />
          </div>
        </aside>
      </div>
    </div>
  );
}

function MapButton({
  label,
  onClick,
  joined = false,
  children,
}: {
  label: string;
  onClick: () => void;
  joined?: boolean;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={`text-ink hover:text-accent-strong grid size-9 place-items-center ${
        joined ? "" : "bg-page rounded-[2px] shadow-(--shadow-float)"
      }`}
    >
      {children}
      <span className="sr-only">{label}</span>
    </button>
  );
}

/** A tab on the map's edge that brings a folded pane back. */
function PaneTab({
  side,
  label,
  onClick,
}: {
  side: "left" | "right";
  label: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      title={label}
      className={`bg-page text-ink hover:text-accent-strong border-hairline absolute top-1/2 z-20 grid h-14 w-6 -translate-y-1/2 place-items-center border shadow-(--shadow-float) ${
        side === "left"
          ? "left-0 rounded-r-[2px] border-l-0"
          : "right-0 rounded-l-[2px] border-r-0"
      }`}
    >
      {side === "left" ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
      <span className="sr-only">{label}</span>
    </button>
  );
}
