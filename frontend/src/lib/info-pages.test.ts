import { existsSync, readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import { INFO_PAGES } from "./info-pages";

const app = (path: string) =>
  fileURLToPath(new URL(`../app${path}/page.tsx`, import.meta.url));

describe("information pages", () => {
  it("has a page behind every footer link", () => {
    for (const page of INFO_PAGES) {
      expect(existsSync(app(page.href)), page.href).toBe(true);
    }
  });

  it("explains the asterisk where the asterisks link to", () => {
    // SampleMark and the footers link to /data#placeholder.
    expect(readFileSync(app("/data"), "utf-8")).toContain('id="placeholder"');
  });
});
