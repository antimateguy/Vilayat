import { describe, expect, it } from "vitest";

import { baseUrl } from "./client";

describe("baseUrl", () => {
  it("drops a trailing slash and falls back to the local API", () => {
    expect(baseUrl("https://vilayat.onrender.com/")).toBe(
      "https://vilayat.onrender.com",
    );
    expect(baseUrl(" https://vilayat.onrender.com ")).toBe(
      "https://vilayat.onrender.com",
    );
    expect(baseUrl(undefined)).toBe("http://localhost:8000");
    expect(baseUrl("")).toBe("http://localhost:8000");
  });
});
