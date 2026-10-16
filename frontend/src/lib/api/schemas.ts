import { z } from "zod";

// Every response is validated against one of these schemas when it arrives, so
// the rest of the app can trust its shape. If the backend changes a field, the
// failure shows up here and in the schema tests, not as a blank screen.

/** The API sends the string "UNKNOWN" for a figure it does not have. */
export const UNKNOWN = "UNKNOWN" as const;
const unknown = z.literal(UNKNOWN);
const orUnknown = <T extends z.ZodType>(schema: T) =>
  z.union([schema, unknown]);

export const citySchema = z.object({ id: z.string(), name: z.string() });

export const campusSchema = z.object({
  id: z.number(),
  university_id: z.number(),
  name: z.string(),
  lat: z.number(),
  lon: z.number(),
});

export const universitySchema = z.object({
  id: z.number(),
  name: z.string(),
  short_name: z.string(),
  campuses: z.array(campusSchema),
});

export const employerSchema = z.object({
  id: z.number(),
  name: z.string(),
  lat: z.number(),
  lon: z.number(),
  is_sample: z.boolean(),
});

export const dataSourceSchema = z.object({
  used_for: z.string(),
  name: z.string(),
  publisher: z.string(),
  licence: z.string(),
  as_of: orUnknown(z.string()),
  is_sample: z.boolean(),
  url: z.string().nullable(),
});

const areaRefSchema = z.object({ id: z.number(), name: z.string() });

export const rentSchema = z.object({
  monthly_eur: z.number(),
  basis: z.string(),
  source: z.string(),
  source_url: z.string().nullable(),
  as_of: z.string(),
  is_sample: z.boolean(),
});

const jobAccessSchema = z.object({
  score: z.number(),
  places_nearby: z.number(),
});

export const factsSchema = z.object({
  cell_count: z.number(),
  rent: orUnknown(rentSchema),
  commute_minutes: orUnknown(z.number()),
  amenities: orUnknown(z.record(z.string(), z.number())),
  job_access: orUnknown(jobAccessSchema),
});

const scoreComponentSchema = z.object({
  name: z.string(),
  value: orUnknown(z.number()),
  share: z.number(),
  reason: z.string(),
});

const fullDaySchema = z.object({
  employer: z.object({ id: z.number(), name: z.string() }),
  home_to_campus: orUnknown(z.number()),
  campus_to_job: orUnknown(z.number()),
  job_to_home: orUnknown(z.number()),
  campus_to_home: orUnknown(z.number()),
  total_minutes: orUnknown(z.number()),
  extra_minutes: orUnknown(z.number()),
});

export const rankedAreaSchema = z.object({
  rank: z.number(),
  area: areaRefSchema,
  facts: factsSchema,
  score: z.object({
    total: z.number(),
    components: z.array(scoreComponentSchema),
  }),
  reasons: z.array(z.string()),
  trade_off: z.string(),
  full_day: fullDaySchema.nullable(),
});

const excludedAreaSchema = z.object({
  area: areaRefSchema,
  facts: factsSchema,
  violations: z.array(z.string()),
});

const uncheckedAreaSchema = z.object({
  area: areaRefSchema,
  facts: factsSchema,
  missing: z.array(z.string()),
});

export const searchResultSchema = z.object({
  city_id: z.string(),
  campus: campusSchema,
  ranked: z.array(rankedAreaSchema),
  excluded: z.array(excludedAreaSchema),
  unchecked: z.array(uncheckedAreaSchema),
});

export const areaDetailSchema = z.object({
  area: areaRefSchema,
  city_id: z.string(),
  campus: campusSchema.nullable(),
  facts: factsSchema,
  return_minutes: orUnknown(z.number()),
  listing_portals: z.array(
    z.object({ name: z.string(), offers: z.string(), url: z.string() }),
  ),
  listing_hint: z.string(),
});

const campusFeasibilitySchema = z.object({
  campus: campusSchema,
  feasible: z.number(),
  excluded: z.number(),
  unchecked: z.number(),
  feasible_area_ids: z.array(z.number()),
});

export const comparisonSchema = z.object({
  city_id: z.string(),
  max_rent_eur: z.number(),
  max_commute_minutes: z.number(),
  total_areas: z.number(),
  universities: z.array(
    z.object({
      university: z.object({
        id: z.number(),
        name: z.string(),
        short_name: z.string(),
      }),
      feasible: z.number(),
      campuses: z.array(campusFeasibilitySchema),
    }),
  ),
});

// GeoJSON. The geometry is passed straight to the map library, which checks it.
const geometrySchema = z.object({
  type: z.string(),
  coordinates: z.array(z.unknown()),
});

export const areaLayerSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      id: z.number(),
      geometry: geometrySchema,
      properties: z.object({
        area_id: z.number(),
        name: z.string(),
        cell_count: z.number(),
        rent_eur: orUnknown(z.number()),
        rent_is_sample: z.boolean(),
        commute_minutes: orUnknown(z.number()),
        amenities_total: orUnknown(z.number()),
        job_access_score: orUnknown(z.number()),
      }),
    }),
  ),
});

export const cellLayerSchema = z.object({
  type: z.literal("FeatureCollection"),
  metric: z.string(),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      id: z.string(),
      geometry: geometrySchema,
      properties: z.object({
        cell: z.string(),
        area_id: z.number(),
        value: orUnknown(z.number()),
      }),
    }),
  ),
});

export const errorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    request_id: z.string(),
    details: z.array(z.object({ field: z.string(), problem: z.string() })),
  }),
});

export type City = z.infer<typeof citySchema>;
// --- The commute breakdown of an area -----------------------------------------

export const legModeSchema = z.enum([
  "walk",
  "bus",
  "tram",
  "subway",
  "rail",
  "ferry",
  "other",
]);

export const routeLegSchema = z.object({
  mode: legModeSchema,
  minutes: z.number(),
  wait_minutes: z.number(),
  distance_m: z.number(),
  line: z.string().nullable(),
  from_stop: z.string().nullable(),
  to_stop: z.string().nullable(),
  line_colour: z.string().nullable().default(null),
  path: z.object({
    type: z.literal("LineString"),
    coordinates: z.array(z.tuple([z.number(), z.number()])),
  }),
});

export const areaCommuteSchema = z.object({
  area: areaRefSchema,
  campus: campusSchema,
  spread: z
    .object({
      cells: z.number(),
      fastest_minutes: z.number(),
      median_minutes: z.number(),
      slowest_minutes: z.number(),
    })
    .nullable(),
  route: z
    .object({
      departs_at: z.string(),
      total_minutes: z.number(),
      start: z.array(z.number()),
      legs: z.array(routeLegSchema),
      computed_at: z.string(),
    })
    .nullable(),
  employer: z
    .object({ id: z.number(), name: z.string() })
    .nullable()
    .default(null),
  to_job: z
    .object({
      departs_at: z.string(),
      total_minutes: z.number(),
      start: z.array(z.number()),
      legs: z.array(routeLegSchema),
      computed_at: z.string(),
    })
    .nullable()
    .default(null),
});

// --- The rail and tram network, for the map --------------------------------

export const transitLayerSchema = z.object({
  type: z.literal("FeatureCollection"),
  features: z.array(
    z.object({
      type: z.literal("Feature"),
      geometry: z.object({
        type: z.literal("LineString"),
        coordinates: z.array(z.tuple([z.number(), z.number()])),
      }),
      properties: z.object({
        label: z.string(),
        mode: z.enum(["subway", "rail", "tram"]),
        colour: z.string().nullable(),
      }),
    }),
  ),
});

export type TransitLayer = z.infer<typeof transitLayerSchema>;

export type LegMode = z.infer<typeof legModeSchema>;
export type RouteLeg = z.infer<typeof routeLegSchema>;
export type AreaCommute = z.infer<typeof areaCommuteSchema>;
export type CommuteRoute = NonNullable<AreaCommute["route"]>;
export type CommuteSpread = NonNullable<AreaCommute["spread"]>;

export type Campus = z.infer<typeof campusSchema>;
export type University = z.infer<typeof universitySchema>;
export type Employer = z.infer<typeof employerSchema>;
export type DataSource = z.infer<typeof dataSourceSchema>;
export type Rent = z.infer<typeof rentSchema>;
export type Facts = z.infer<typeof factsSchema>;
export type RankedArea = z.infer<typeof rankedAreaSchema>;
export type SearchResult = z.infer<typeof searchResultSchema>;
export type AreaDetail = z.infer<typeof areaDetailSchema>;
export type Comparison = z.infer<typeof comparisonSchema>;
export type AreaLayer = z.infer<typeof areaLayerSchema>;
export type CellLayer = z.infer<typeof cellLayerSchema>;
export type OrUnknown<T> = T | typeof UNKNOWN;

// --- AI layer -----------------------------------------------------------------
// In these schemas null means "the sentence did not mention it", which is not
// the same as a figure the app lacks, so it is not written as "UNKNOWN".

export const aiStatusSchema = z.object({
  enabled: z.boolean(),
  daily_limit_reached: z.boolean().default(false),
  resets_at: z.string().nullable().default(null),
});

export const intentSchema = z.object({
  understood: z.boolean(),
  city_id: z.string().nullable(),
  campus: z
    .object({
      id: z.number(),
      name: z.string(),
      university_id: z.number(),
      university_short_name: z.string(),
    })
    .nullable(),
  max_rent_eur: z.number().nullable(),
  max_commute_minutes: z.number().nullable(),
  employer: z.object({ id: z.number(), name: z.string() }).nullable(),
  weights: z
    .object({
      commute: z.number(),
      rent: z.number(),
      amenities: z.number(),
      job_access: z.number(),
    })
    .nullable(),
  notes: z.array(z.string()),
});

export const citationSchema = z.object({
  number: z.number(),
  title: z.string(),
  section: z.string().nullable(),
  // Null when the source's licence does not allow showing its text.
  passage: z.string().nullable(),
  source_url: z.string(),
  retrieved_on: z.string(),
  city_id: z.string().nullable(),
  is_sample: z.boolean(),
});

export const askSchema = z.object({
  status: z.enum(["answered", "no_evidence", "sources_only"]),
  answer: z.string(),
  citations: z.array(citationSchema),
});

export const areaBriefingSchema = z.object({
  area: z.object({ id: z.number(), name: z.string() }),
  briefing: orUnknown(
    z.object({
      text: z.string(),
      model: z.string(),
      generated_at: z.string(),
      uses_sample_rent: z.boolean(),
    }),
  ),
});

export type Intent = z.infer<typeof intentSchema>;
export type Citation = z.infer<typeof citationSchema>;
export type Answer = z.infer<typeof askSchema>;
export type AreaBriefing = z.infer<typeof areaBriefingSchema>;
