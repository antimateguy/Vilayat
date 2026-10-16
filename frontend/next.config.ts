import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Build to plain HTML, CSS and JS in out/, so the site can be served from a
  // CDN (Cloudflare Pages) with no Node server.
  output: "export",
  // The image optimiser needs a server, which a static export does not have.
  images: { unoptimized: true },
};

export default nextConfig;
