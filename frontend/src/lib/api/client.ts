import { z } from "zod";

import { errorSchema } from "./schemas";

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const V1 = `${API_BASE_URL}/api/v1`;

/** An error the API reported in its standard shape, or a failure to reach it. */
export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId: string | null,
    readonly details: { field: string; problem: string }[] = [],
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function request<T extends z.ZodType>(
  url: string,
  schema: T,
  init?: RequestInit,
): Promise<z.infer<T>> {
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch {
    throw new ApiError(
      `Cannot reach the API at ${API_BASE_URL}.`,
      0,
      "unreachable",
      null,
    );
  }

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const parsed = errorSchema.safeParse(body);
    if (parsed.success) {
      const { code, message, request_id, details } = parsed.data.error;
      throw new ApiError(message, response.status, code, request_id, details);
    }
    throw new ApiError(
      `The API answered with status ${response.status}.`,
      response.status,
      "http_error",
      response.headers.get("X-Request-ID"),
    );
  }
  return schema.parse(body);
}

export function apiGet<T extends z.ZodType>(
  path: string,
  schema: T,
  params: Record<string, string | number | null | undefined> = {},
): Promise<z.infer<T>> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) query.set(key, String(value));
  }
  const suffix = query.size > 0 ? `?${query}` : "";
  return request(`${V1}${path}${suffix}`, schema);
}

export function apiPost<T extends z.ZodType>(
  path: string,
  schema: T,
  body: unknown,
): Promise<z.infer<T>> {
  return request(`${V1}${path}`, schema, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

// The health endpoint is unversioned.
const healthSchema = z.object({
  status: z.enum(["ok", "unavailable"]),
  checks: z.record(
    z.string(),
    z.object({ ok: z.boolean(), detail: z.string() }),
  ),
});

export type Health = z.infer<typeof healthSchema>;

export async function fetchHealth(): Promise<Health> {
  const response = await fetch(`${API_BASE_URL}/health`);
  // A 503 carries the same body as a 200, so it is parsed rather than thrown.
  return healthSchema.parse(await response.json());
}
