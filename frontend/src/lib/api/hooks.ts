"use client";

import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { z } from "zod";

import { isDailyLimit } from "../ai-status";
import type { Overlay } from "../search-state";
import { apiGet, apiPost } from "./client";
import {
  aiStatusSchema,
  areaBriefingSchema,
  areaCommuteSchema,
  areaDetailSchema,
  areaLayerSchema,
  askSchema,
  cellLayerSchema,
  citySchema,
  comparisonSchema,
  dataSourceSchema,
  employerSchema,
  intentSchema,
  searchResultSchema,
  transitLayerSchema,
  universitySchema,
} from "./schemas";

// Reference data changes only when the backend's data is reloaded, so it is
// fetched once per page visit.
const REFERENCE = { staleTime: Infinity };

export function useCities() {
  return useQuery({
    queryKey: ["cities"],
    queryFn: () => apiGet("/cities", z.array(citySchema)),
    ...REFERENCE,
  });
}

export function useUniversities(city: string) {
  return useQuery({
    queryKey: ["universities", city],
    queryFn: () =>
      apiGet(`/cities/${city}/universities`, z.array(universitySchema)),
    ...REFERENCE,
  });
}

export function useEmployers(city: string) {
  return useQuery({
    queryKey: ["employers", city],
    queryFn: () => apiGet(`/cities/${city}/employers`, z.array(employerSchema)),
    ...REFERENCE,
  });
}

export function useSources(city: string) {
  return useQuery({
    queryKey: ["sources", city],
    queryFn: () => apiGet(`/cities/${city}/sources`, z.array(dataSourceSchema)),
    ...REFERENCE,
  });
}

export interface SearchRequest {
  campus_id: number;
  max_commute_minutes: number;
  max_rent_eur: number;
  weights: Record<string, number>;
  employer_id: number | null;
}

export function useSearch(request: SearchRequest | null) {
  return useQuery({
    queryKey: ["search", request],
    queryFn: () => apiPost("/search", searchResultSchema, request),
    enabled: request !== null,
    // While a slider moves, keep showing the previous result instead of a blank list.
    placeholderData: keepPreviousData,
  });
}

export function useAreaLayer(city: string, campusId: number | null) {
  return useQuery({
    queryKey: ["layer-areas", city, campusId],
    queryFn: () =>
      apiGet(`/cities/${city}/layers/areas`, areaLayerSchema, {
        campus_id: campusId,
      }),
    placeholderData: keepPreviousData,
    ...REFERENCE,
  });
}

export function useCellLayer(
  city: string,
  overlay: Overlay,
  campusId: number | null,
) {
  const needsCampus = overlay === "commute";
  return useQuery({
    queryKey: ["layer-cells", city, overlay, needsCampus ? campusId : null],
    queryFn: () =>
      apiGet(`/cities/${city}/layers/cells`, cellLayerSchema, {
        metric: overlay,
        campus_id: needsCampus ? campusId : null,
      }),
    enabled: overlay !== "none" && (!needsCampus || campusId !== null),
    ...REFERENCE,
  });
}

/** The city's U-Bahn, S-Bahn and tram lines, fetched when first shown. */
export function useTransitLayer(city: string, enabled: boolean) {
  return useQuery({
    queryKey: ["transit", city],
    queryFn: () => apiGet(`/cities/${city}/layers/transit`, transitLayerSchema),
    enabled,
    ...REFERENCE,
  });
}

/** How the commute from an area to a campus goes: spread and typical journey. */
export function useAreaCommute(
  areaId: number | null,
  campusId: number | null,
  employerId: number | null = null,
) {
  return useQuery({
    queryKey: ["area-commute", areaId, campusId, employerId],
    queryFn: () =>
      apiGet(`/areas/${areaId}/commute`, areaCommuteSchema, {
        campus_id: campusId,
        employer_id: employerId,
      }),
    enabled: areaId !== null && campusId !== null,
    ...REFERENCE,
  });
}

export function useAreaDetail(areaId: number | null, campusId: number | null) {
  return useQuery({
    queryKey: ["area", areaId, campusId],
    queryFn: () =>
      apiGet(`/areas/${areaId}`, areaDetailSchema, { campus_id: campusId }),
    enabled: areaId !== null,
    ...REFERENCE,
  });
}

export function useComparison(
  city: string,
  maxRentEur: number,
  maxCommuteMinutes: number,
) {
  return useQuery({
    queryKey: ["comparison", city, maxRentEur, maxCommuteMinutes],
    queryFn: () =>
      apiGet(`/cities/${city}/comparison`, comparisonSchema, {
        max_rent_eur: maxRentEur,
        max_commute_minutes: maxCommuteMinutes,
      }),
    placeholderData: keepPreviousData,
  });
}

// --- AI layer -----------------------------------------------------------------

/** Whether a language model is configured, and whether today's free allowance
 * is spent. While the model is unknown or off, the AI controls stay hidden and
 * the rest of the app is unaffected. */
export function useAiStatus() {
  return useQuery({
    queryKey: ["ai-status"],
    queryFn: () => apiGet("/ai/status", aiStatusSchema),
    ...REFERENCE,
  });
}

/** Sentence to settings. A mutation, not a query: it runs only when asked to. */
export function useIntent() {
  const refreshStatus = useRefreshStatusOnDailyLimit();
  return useMutation({
    onError: refreshStatus,
    mutationFn: (input: { sentence: string; city: string }) =>
      apiPost("/intent", intentSchema, {
        sentence: input.sentence,
        city_id: input.city,
      }),
  });
}

export function useAsk() {
  const refreshStatus = useRefreshStatusOnDailyLimit();
  return useMutation({
    onError: refreshStatus,
    mutationFn: (input: { question: string; city: string | null }) =>
      apiPost("/ask", askSchema, {
        question: input.question,
        city_id: input.city,
      }),
  });
}

/** When a request finds the allowance spent, every AI control on the page
 * learns it at once through a fresh status. */
function useRefreshStatusOnDailyLimit() {
  const client = useQueryClient();
  return (error: Error) => {
    if (isDailyLimit(error))
      void client.invalidateQueries({ queryKey: ["ai-status"] });
  };
}

/** The stored briefing of an area. Reading it never calls a model. */
export function useAreaBriefing(areaId: number | null) {
  return useQuery({
    queryKey: ["area-briefing", areaId],
    queryFn: () => apiGet(`/areas/${areaId}/briefing`, areaBriefingSchema),
    enabled: areaId !== null,
    ...REFERENCE,
  });
}
