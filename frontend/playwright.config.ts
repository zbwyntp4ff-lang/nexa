import { defineConfig, devices } from "@playwright/test";
const PORT = 4821;
export default defineConfig({
  testDir: "./e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: "list",
  use: {
    // Must match the dev server's own origin ("localhost") - Next.js 16
    // blocks cross-origin requests to its dev asset/HMR endpoints by
    // default, which would otherwise silently break client-side hydration
    // if the browser navigated to 127.0.0.1 instead.
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "webkit-ipad",
            testMatch: /chat-flow\.spec\.ts/,
      use: { ...devices["iPad (gen 7)"], viewport: { width: 1024, height: 1366 }, browserName: "webkit" },
    },
  ],
  webServer: {
    command: `npx next dev -p ${PORT}`,
    url: `http://localhost:${PORT}`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
    env: {
      // Deliberately points at a port nothing listens on - the E2E test
      // mocks every backend call via page.route(), so NEXA must work without
      // a real backend reachable at this URL.
      NEXT_PUBLIC_API_BASE_URL: "http://127.0.0.1:8499",
    },
  },
});
