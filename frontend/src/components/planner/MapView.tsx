"use client";

import "maplibre-gl/dist/maplibre-gl.css";

import {
  type GeoJSONSource,
  Map as MapLibreMap,
  Marker,
  Popup,
  setWorkerUrl,
} from "maplibre-gl";
import {
  type Ref,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
} from "react";

import type {
  AreaLayer,
  CellLayer,
  CommuteRoute,
  SearchResult,
  TransitLayer,
} from "@/lib/api/schemas";
import { formatScore } from "@/lib/format";
import { chooseFocus, type Focus, focusKey, openSpace } from "@/lib/map-focus";
import {
  NEUTRAL,
  rankLabels,
  ROUTE_COLOUR,
  styleAreas,
  styleCells,
} from "@/lib/map-style";
import { journeyFeatures, MODE_COLOURS } from "@/lib/route";
import type { Overlay } from "@/lib/search-state";

// The map library parses tiles in a web worker loaded from its own file.
// scripts/copy-map-worker.mjs puts that file under public/maplibre/.
setWorkerUrl("/maplibre/maplibre-gl-worker.mjs");

// OpenFreeMap: a free base map built from OpenStreetMap, used without a key.
const BASE_MAP_STYLE = "https://tiles.openfreemap.org/styles/positron";
/** Whatever the map library accepts as the content of a GeoJSON source. */
type GeoJsonData = Parameters<GeoJSONSource["setData"]>[0];
const EMPTY = { type: "FeatureCollection", features: [] } as GeoJsonData;
const FOCUS_FILL = "#127a0a";
const EMPLOYER_COLOUR = "#9a5208";
const WIDE = "(min-width: 768px)";

export interface MapPin {
  name: string;
  lat: number;
  lon: number;
}

export interface MapPlace extends MapPin {
  id: number;
}

/** The optional overlays the student can switch on above the layer. */
export interface MapExtras {
  universities: boolean;
  employers: boolean;
  transit: boolean;
}

/** What the planner's own buttons can ask the map to do. */
export interface MapHandle {
  zoomIn: () => void;
  zoomOut: () => void;
  centre: () => void;
}

interface MapViewProps {
  ref?: Ref<MapHandle>;
  areaLayer: AreaLayer | undefined;
  result: SearchResult | undefined;
  overlay: Overlay;
  cellLayer: CellLayer | undefined;
  campus: MapPin | null;
  employer: MapPin | null;
  selectedAreaId: number | null;
  /** Trips to draw (home to campus, then campus to work). Drawn only on the
   * commute layer with an area selected, in place of the hexagon grid. */
  journey: CommuteRoute[];
  /** Whether the detail panel covers the right of the map. */
  rightPanelOpen: boolean;
  extras: MapExtras;
  campuses: MapPlace[];
  employers: MapPlace[];
  transit: TransitLayer | undefined;
  onSelectArea: (areaId: number) => void;
  onPickCampus: (campusId: number) => void;
  onPickEmployer: (employerId: number) => void;
}

export function MapView({
  ref,
  areaLayer,
  result,
  overlay,
  cellLayer,
  campus,
  employer,
  selectedAreaId,
  journey,
  rightPanelOpen,
  extras,
  campuses,
  employers,
  transit,
  onSelectArea,
  onPickCampus,
  onPickEmployer,
}: MapViewProps) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const [ready, setReady] = useState(false);

  const areas = useMemo(
    () => (areaLayer ? styleAreas(areaLayer, result) : null),
    [areaLayer, result],
  );
  // On the commute layer, choosing an area swaps the city-wide hexagons for
  // that area and its trip, so the route is not lost in the grid.
  const tripView = overlay === "commute" && selectedAreaId !== null;
  const shownJourney = useMemo(
    () => (tripView ? journey : []),
    [tripView, journey],
  );
  const cells = useMemo(
    () =>
      cellLayer && overlay !== "none" && !tripView
        ? styleCells(cellLayer, overlay)
        : null,
    [cellLayer, overlay, tripView],
  );
  const focus = useMemo(
    () => chooseFocus(overlay, selectedAreaId, shownJourney, areas),
    [overlay, selectedAreaId, shownJourney, areas],
  );
  const places = useMemo(
    () => placeFeatures(extras, campuses, employers, campus, employer),
    [extras, campuses, employers, campus, employer],
  );

  // The map's event handlers are registered once, so they read the latest
  // props through refs.
  const latest = useRef({
    onSelectArea,
    onPickCampus,
    onPickEmployer,
    overlay,
    tripView,
    total: 0,
    focus: null as Focus | null,
    rightPanelOpen,
  });
  useEffect(() => {
    latest.current = {
      onSelectArea,
      onPickCampus,
      onPickEmployer,
      overlay,
      tripView,
      total: result?.ranked.length ?? 0,
      focus,
      rightPanelOpen,
    };
  });

  const frameFocus = (duration: number) => {
    const map = mapRef.current;
    const target = latest.current.focus;
    if (!map || !target) return;
    const { clientWidth: width, clientHeight: height } = map.getContainer();
    map.fitBounds(target.bounds, {
      padding: openSpace(
        { width, height },
        latest.current.rightPanelOpen,
        window.matchMedia(WIDE).matches,
      ),
      maxZoom: target.maxZoom,
      duration,
    });
  };

  useImperativeHandle(ref, () => ({
    zoomIn: () => mapRef.current?.zoomIn({ duration: 250 }),
    zoomOut: () => mapRef.current?.zoomOut({ duration: 250 }),
    centre: () => frameFocus(600),
  }));

  useEffect(() => {
    if (!container.current) return;
    const map = new MapLibreMap({
      container: container.current,
      style: BASE_MAP_STYLE,
      center: [11.5756, 48.1372],
      zoom: 9.5,
      attributionControl: { compact: true },
    });
    mapRef.current = map;

    const popup = new Popup({
      closeButton: false,
      closeOnClick: false,
      offset: 12,
    });

    // "style.load" comes as soon as the base map's style is known. Waiting for
    // "load" would hold our own layers back until every background tile is in.
    map.once("style.load", () => {
      // Our layers go under the base map's labels, so place names stay readable.
      const firstLabel = map
        .getStyle()
        .layers.find((layer) => layer.type === "symbol")?.id;

      for (const source of [
        "areas",
        "cells",
        "ranks",
        "route",
        "transit",
        "places",
      ]) {
        map.addSource(source, { type: "geojson", data: EMPTY });
      }
      addAreaLayers(map, firstLabel);
      addTransitLayers(map);
      addRouteLayers(map);
      addTopLayers(map);

      map.on("click", "areas-hit", (event) => {
        // A pin on top of the area takes the click instead.
        if (
          map.queryRenderedFeatures(event.point, { layers: ["places-dot"] })
            .length
        )
          return;
        const id = event.features?.[0]?.properties?.area_id;
        if (typeof id === "number") latest.current.onSelectArea(id);
      });
      map.on("mousemove", "areas-hit", (event) => {
        const area = event.features?.[0]?.properties;
        if (!area) return;
        map.getCanvas().style.cursor = "pointer";
        const cell = map.queryRenderedFeatures(event.point, {
          layers: ["cells-fill"],
        })[0]?.properties;
        const { overlay: shown, tripView: trip, total } = latest.current;
        popup
          .setLngLat(event.lngLat)
          .setDOMContent(popupContent(area, cell, shown, trip, total))
          .addTo(map);
      });
      map.on("mouseleave", "areas-hit", () => {
        map.getCanvas().style.cursor = "";
        popup.remove();
      });
      map.on("click", "places-dot", (event) => {
        const place = event.features?.[0]?.properties;
        if (!place || typeof place.id !== "number") return;
        if (place.kind === "campus") latest.current.onPickCampus(place.id);
        else latest.current.onPickEmployer(place.id);
      });
      map.on("mouseenter", "places-dot", () => {
        map.getCanvas().style.cursor = "pointer";
      });

      setReady(true);
    });

    return () => {
      popup.remove();
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // The map follows the size of its box: when a side pane collapses or
  // opens, it redraws, and the framing below runs again.
  const [layoutTick, setLayoutTick] = useState(0);
  useEffect(() => {
    const element = container.current;
    if (!element) return;
    let timer: ReturnType<typeof setTimeout> | undefined;
    const observer = new ResizeObserver(() => {
      mapRef.current?.resize();
      clearTimeout(timer);
      timer = setTimeout(() => setLayoutTick((tick) => tick + 1), 150);
    });
    observer.observe(element);
    return () => {
      clearTimeout(timer);
      observer.disconnect();
    };
  }, []);

  // Frame what matters whenever the answer to "what should be in view"
  // changes: new results, another layer, a chosen area or trip, a pane opened,
  // closed or resized. Nothing moves while the student pans and nothing changes.
  const key = focusKey(focus);
  const framedOnce = useRef(false);
  useEffect(() => {
    if (!ready || key === "none") return;
    frameFocus(framedOnce.current ? 600 : 0);
    framedOnce.current = true;
    // frameFocus reads the latest focus and panel state from a ref.
  }, [ready, key, rightPanelOpen, layoutTick]);

  // Area outlines and their status.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "areas", areas);
    setData(map, "ranks", areas && rankLabels(areas));
  }, [ready, areas]);

  // The hexagon layer replaces the area shading while it is shown.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "cells", cells);
    const showAreas = overlay === "none" ? "visible" : "none";
    map.setLayoutProperty("areas-fill", "visibility", showAreas);
    map.setLayoutProperty("areas-rank", "visibility", showAreas);
    map.setLayoutProperty(
      "areas-focus",
      "visibility",
      tripView ? "visible" : "none",
    );
  }, [ready, cells, overlay, tripView]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const filter = ["==", ["get", "area_id"], selectedAreaId ?? -1];
    map.setFilter("areas-selected", filter as never);
    map.setFilter("areas-focus", filter as never);
  }, [ready, selectedAreaId]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(
      map,
      "route",
      shownJourney.length > 0 ? journeyFeatures(shownJourney) : null,
    );
  }, [ready, shownJourney]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "transit", extras.transit && transit ? transit : null);
  }, [ready, extras.transit, transit]);

  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    setData(map, "places", places);
  }, [ready, places]);

  // The chosen campus and employer: labelled pins.
  useEffect(() => {
    const map = mapRef.current;
    if (!ready || !map) return;
    const markers = [
      campus && pin(campus, "Campus", true),
      employer && pin(employer, "Employer", false),
    ]
      .filter((marker) => marker !== null)
      .map((marker) => marker.addTo(map));
    return () => markers.forEach((marker) => marker.remove());
  }, [ready, campus, employer]);

  return (
    <div
      ref={container}
      role="application"
      aria-label="Map of the city's areas"
      className="h-full w-full"
    />
  );
}

function addAreaLayers(map: MapLibreMap, beforeLabels: string | undefined) {
  map.addLayer(
    {
      id: "cells-fill",
      type: "fill",
      source: "cells",
      filter: ["==", ["get", "known"], true],
      paint: {
        "fill-color": ["get", "colour"],
        "fill-opacity": 0.78,
        // A thin line in the surface colour separates neighbouring cells.
        "fill-outline-color": NEUTRAL.surface,
      },
    },
    beforeLabels,
  );
  map.addLayer(
    {
      id: "areas-fill",
      type: "fill",
      source: "areas",
      paint: {
        "fill-color": ["get", "colour"],
        "fill-opacity": [
          "match",
          ["get", "status"],
          "ranked",
          0.78,
          "excluded",
          0.4,
          0,
        ],
      },
    },
    beforeLabels,
  );
  map.addLayer(
    {
      id: "areas-focus",
      type: "fill",
      source: "areas",
      filter: ["==", ["get", "area_id"], -1],
      layout: { visibility: "none" },
      paint: { "fill-color": FOCUS_FILL, "fill-opacity": 0.22 },
    },
    beforeLabels,
  );
  map.addLayer(
    {
      id: "areas-outline",
      type: "line",
      source: "areas",
      paint: { "line-color": NEUTRAL.outline, "line-width": 1 },
    },
    beforeLabels,
  );
}

/** The U-Bahn, S-Bahn and tram network, like the maps at stations: each line
 * in its colour (or its kind's), trams thinner, names along the lines. */
function addTransitLayers(map: MapLibreMap) {
  const colour = [
    "coalesce",
    ["get", "colour"],
    [
      "match",
      ["get", "mode"],
      "subway",
      MODE_COLOURS.subway,
      "rail",
      MODE_COLOURS.rail,
      MODE_COLOURS.tram,
    ],
  ];
  const width = ["match", ["get", "mode"], "tram", 1.6, 3.2];
  map.addLayer({
    id: "transit-casing",
    type: "line",
    source: "transit",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": "#ffffff",
      "line-width": ["+", width, 2] as never,
      "line-opacity": 0.8,
    },
  });
  map.addLayer({
    id: "transit-lines",
    type: "line",
    source: "transit",
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": colour as never,
      "line-width": width as never,
      "line-opacity": 0.9,
    },
  });
  map.addLayer({
    id: "transit-labels",
    type: "symbol",
    source: "transit",
    layout: {
      "symbol-placement": "line",
      "text-field": ["get", "label"],
      "text-font": ["Noto Sans Bold"],
      "text-size": 10,
      "symbol-spacing": 280,
    },
    paint: {
      "text-color": colour as never,
      "text-halo-color": "#ffffff",
      "text-halo-width": 2,
    },
  });
}

/** The trip, drawn the way journey planners draw one: rides in their line's
 * colour on a white edge, walking as dots, a ring at every stop, the line's
 * name on the ride and a dot where the trip starts. */
function addRouteLayers(map: MapLibreMap) {
  map.addLayer({
    id: "areas-selected",
    type: "line",
    source: "areas",
    filter: ["==", ["get", "area_id"], -1],
    paint: { "line-color": NEUTRAL.ink, "line-width": 3 },
  });
  map.addLayer({
    id: "route-casing",
    type: "line",
    source: "route",
    filter: ["==", ["get", "part"], "ride"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": "#ffffff", "line-width": 10 },
  });
  map.addLayer({
    id: "route-ride",
    type: "line",
    source: "route",
    filter: ["==", ["get", "part"], "ride"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: { "line-color": ["get", "colour"], "line-width": 6 },
  });
  map.addLayer({
    id: "route-walk",
    type: "line",
    source: "route",
    filter: ["==", ["get", "part"], "walk"],
    layout: { "line-cap": "round", "line-join": "round" },
    paint: {
      "line-color": ["get", "colour"],
      "line-width": 4.5,
      // Zero-length dashes with round caps draw a row of dots.
      "line-dasharray": [0, 1.8],
    },
  });
  map.addLayer({
    id: "route-stop",
    type: "circle",
    source: "route",
    filter: ["==", ["get", "part"], "stop"],
    paint: {
      "circle-radius": 5,
      "circle-color": "#ffffff",
      "circle-stroke-color": ["get", "colour"],
      "circle-stroke-width": 3,
    },
  });
  map.addLayer({
    id: "route-start",
    type: "circle",
    source: "route",
    filter: ["==", ["get", "part"], "start"],
    paint: {
      "circle-radius": 7,
      "circle-color": ROUTE_COLOUR,
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 3,
    },
  });
  map.addLayer({
    id: "route-label",
    type: "symbol",
    source: "route",
    filter: ["==", ["get", "part"], "label"],
    layout: {
      "text-field": ["get", "label"],
      "text-font": ["Noto Sans Bold"],
      "text-size": 12,
      "text-allow-overlap": true,
    },
    paint: {
      "text-color": ["get", "text"],
      "text-halo-color": ["get", "colour"],
      "text-halo-width": 4,
    },
  });
}

function addTopLayers(map: MapLibreMap) {
  map.addLayer({
    id: "areas-rank",
    type: "symbol",
    source: "ranks",
    layout: {
      "text-field": ["to-string", ["get", "rank"]],
      "text-font": ["Noto Sans Bold"],
      "text-size": 14,
      "text-allow-overlap": true,
    },
    paint: {
      "text-color": NEUTRAL.ink,
      "text-halo-color": NEUTRAL.surface,
      "text-halo-width": 2,
    },
  });
  // An invisible layer takes clicks and hovers whatever is drawn below it.
  map.addLayer({
    id: "areas-hit",
    type: "fill",
    source: "areas",
    paint: { "fill-opacity": 0 },
  });
  // Universities and employers the student can switch on and click.
  map.addLayer({
    id: "places-dot",
    type: "circle",
    source: "places",
    paint: {
      "circle-radius": 6,
      "circle-color": [
        "match",
        ["get", "kind"],
        "campus",
        NEUTRAL.ink,
        EMPLOYER_COLOUR,
      ],
      "circle-stroke-color": "#ffffff",
      "circle-stroke-width": 2,
    },
  });
  map.addLayer({
    id: "places-label",
    type: "symbol",
    source: "places",
    layout: {
      "text-field": ["get", "name"],
      "text-font": ["Noto Sans Regular"],
      "text-size": 11,
      "text-offset": [0, 1.1],
      "text-anchor": "top",
      "text-max-width": 12,
      // A pin the student asked for is always named, even over place names.
      "text-allow-overlap": true,
      "text-ignore-placement": true,
    },
    paint: {
      "text-color": NEUTRAL.ink,
      "text-halo-color": "#ffffff",
      "text-halo-width": 1.5,
    },
  });
}

/** Points for the universities and employers overlays. The chosen campus and
 * employer already have their own labelled pins, so they are left out. */
function placeFeatures(
  extras: MapExtras,
  campuses: MapPlace[],
  employers: MapPlace[],
  campus: MapPin | null,
  employer: MapPin | null,
) {
  const point = (kind: string, place: MapPlace) => ({
    type: "Feature" as const,
    properties: { kind, id: place.id, name: place.name },
    geometry: { type: "Point" as const, coordinates: [place.lon, place.lat] },
  });
  const notPinned = (pinned: MapPin | null) => (place: MapPlace) =>
    !pinned || place.lat !== pinned.lat || place.lon !== pinned.lon;
  return {
    type: "FeatureCollection" as const,
    features: [
      ...(extras.universities
        ? campuses
            .filter(notPinned(campus))
            .map((place) => point("campus", place))
        : []),
      ...(extras.employers
        ? employers
            .filter(notPinned(employer))
            .map((place) => point("employer", place))
        : []),
    ],
  };
}

/** Replace what a GeoJSON source holds; null empties it. */
function setData(map: MapLibreMap, sourceId: string, data: object | null) {
  const source = map.getSource<GeoJSONSource>(sourceId);
  source?.setData((data ?? EMPTY) as GeoJsonData);
}

/** A labelled pin. The label carries the meaning; the shape only supports it. */
function pin(place: MapPin, kind: string, filled: boolean): Marker {
  const element = document.createElement("div");
  element.className = "flex flex-col items-center";
  const label = document.createElement("span");
  label.className =
    "rounded bg-[#f3f2f2] px-1.5 py-0.5 text-[11px] font-medium text-[#201e1d] shadow-sm whitespace-nowrap";
  label.textContent = `${kind}: ${place.name}`;
  const dot = document.createElement("span");
  dot.className = filled
    ? "mt-0.5 size-3 rounded-full border-2 border-[#f3f2f2] bg-[#201e1d]"
    : "mt-0.5 size-3 rotate-45 border-2 border-[#201e1d] bg-[#f3f2f2]";
  element.append(label, dot);
  return new Marker({ element, anchor: "bottom" }).setLngLat([
    place.lon,
    place.lat,
  ]);
}

/** Popup text. Names come from data, so they are set as text, never as HTML. */
function popupContent(
  area: Record<string, unknown>,
  cell: Record<string, unknown> | undefined,
  overlay: Overlay,
  tripView: boolean,
  total: number,
): HTMLElement {
  const root = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = String(area.name);
  const line = document.createElement("div");
  line.style.color = "#605d5d";
  // In the trip view the hexagons are hidden, so the area's own status is told.
  line.textContent =
    overlay === "none" || tripView
      ? areaLine(area, total)
      : cellLine(cell, overlay);
  root.append(title, line);
  return root;
}

function areaLine(area: Record<string, unknown>, total: number): string {
  if (area.status === "ranked") return `Rank ${area.rank} of ${total}`;
  if (area.status === "excluded") return "Outside your limits";
  if (area.status === "unchecked") return "Cannot be checked";
  return "";
}

function cellLine(
  cell: Record<string, unknown> | undefined,
  overlay: Overlay,
): string {
  const value = cell?.value;
  if (typeof value !== "number") return "No figure for this cell";
  if (overlay === "commute") return `${value} min to campus`;
  if (overlay === "amenities") {
    return `${value} everyday ${value === 1 ? "amenity" : "amenities"} in this cell`;
  }
  return `Job access ${formatScore(value)} / 100`;
}
