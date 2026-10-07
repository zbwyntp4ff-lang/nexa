import type { NextConfig } from "next";
// Only the Electron desktop packaging step (Part 8.5) sets this. Normal
// `next dev`/`next build`/`next start` (used by the web preview) are
// completely unaffected - this app has no Route Handlers, middleware, or
// server actions, so a static export is a safe, purely additive target.
const isElectronBuild = process.env.NEXA_TARGET === "electron";
const nextConfig: NextConfig = {
  agentRules: false,
  // Next.js 16 blocks cross-origin requests to dev-only assets/HMR by
  // default, checked against the exact hostname string. Preview tooling and
  // local testing sometimes navigate via 127.0.0.1 while `next dev` treats
  // "localhost" as its own origin (or vice versa) - without this, the page
  // shell loads but client-side hydration silently fails (buttons/inputs
  // stop working) because the JS chunks get blocked.
  allowedDevOrigins: ["localhost", "127.0.0.1", "0.0.0.0"],
  ...(isElectronBuild
    ? {
        output: "export",
        images: { unoptimized: true },
      }
    : {}),
};
export default nextConfig;
