import { AppShell } from "@/components/layout/app-shell";

/**
 * AuthGate / registration UI is intentionally not mounted.
 * Keep `components/auth/*`, `auth-store`, and `/api/v1/auth` for a later release.
 */
export default function Home() {
  return <AppShell />;
}
