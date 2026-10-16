// Copies the map library's worker files into public/, where the browser can
// load them. MapLibre runs tile parsing in a web worker that it loads from a
// separate file; a bundler does not pick that file up by itself.
import { copyFileSync, mkdirSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const dist = dirname(require.resolve("maplibre-gl/package.json")) + "/dist";
const target = join(
  dirname(fileURLToPath(import.meta.url)),
  "..",
  "public",
  "maplibre",
);

mkdirSync(target, { recursive: true });
// The worker imports the shared module from its own folder, so both are needed.
for (const file of ["maplibre-gl-worker.mjs", "maplibre-gl-shared.mjs"]) {
  copyFileSync(join(dist, file), join(target, file));
}
console.log(`copied the map worker files to ${target}`);
