import { describe, expect, it } from "vitest";

import { aiState, formatReset, isDailyLimit } from "./ai-status";
import { ApiError } from "./api/client";

describe("aiState", () => {
  it("is unknown until the status has loaded", () => {
    expect(aiState(undefined)).toBeUndefined();
  });

  it("separates a missing model from a spent daily allowance", () => {
    const base = { daily_limit_reached: false, resets_at: null };
    expect(aiState({ ...base, enabled: false })).toBe("off");
    expect(aiState({ ...base, enabled: true })).toBe("on");
    expect(
      aiState({
        enabled: true,
        daily_limit_reached: true,
        resets_at: "2026-10-17T07:00:00Z",
      }),
    ).toBe("resting");
  });
});

describe("isDailyLimit", () => {
  it("recognises only the daily-limit error", () => {
    expect(
      isDailyLimit(new ApiError("spent", 503, "ai_daily_limit", null)),
    ).toBe(true);
    expect(
      isDailyLimit(new ApiError("down", 503, "ai_unavailable", null)),
    ).toBe(false);
    expect(isDailyLimit(new Error("other"))).toBe(false);
  });
});

describe("formatReset", () => {
  it("falls back to 'tomorrow' without a usable time", () => {
    expect(formatReset(null)).toBe("tomorrow");
    expect(formatReset("not a date")).toBe("tomorrow");
  });

  it("names the day and the time", () => {
    expect(formatReset("2026-10-17T07:00:00Z")).toMatch(/17 Oct/);
  });
});
