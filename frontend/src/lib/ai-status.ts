// Whether the AI features can be used right now. A configured model can still
// be off for the rest of the day: the free daily allowance is a hard limit, and
// once it is spent the features stay off until the provider's next day.

import { ApiError } from "@/lib/api/client";

export const DAILY_LIMIT_CODE = "ai_daily_limit";

export interface AiStatus {
  enabled: boolean;
  daily_limit_reached: boolean;
  resets_at: string | null;
}

export type AiState = "off" | "resting" | "on";

export function aiState(status: AiStatus | undefined): AiState | undefined {
  if (!status) return undefined;
  if (!status.enabled) return "off";
  return status.daily_limit_reached ? "resting" : "on";
}

export function isDailyLimit(error: unknown): boolean {
  return error instanceof ApiError && error.code === DAILY_LIMIT_CODE;
}

/** "Fri 17 Oct, 09:00" in the visitor's own time zone; "tomorrow" if unknown. */
export function formatReset(iso: string | null, locale = "en-GB"): string {
  if (!iso) return "tomorrow";
  const when = new Date(iso);
  if (Number.isNaN(when.getTime())) return "tomorrow";
  return when.toLocaleString(locale, {
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  });
}
