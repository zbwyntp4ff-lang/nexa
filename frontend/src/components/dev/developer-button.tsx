"use client";
import * as React from "react";
import { Bug, Terminal } from "lucide-react";
import { Button } from "@/components/ui/button";
import { toggleDesktopDevTools, isDesktopApp, getDesktopBackendStatus } from "@/lib/electron-bridge";
import { API_BASE_URL } from "@/lib/api";
import { useT } from "@/lib/i18n";
import { useAuthStore } from "@/store/auth-store";
import { cn } from "@/lib/utils";

/**
 * Visible only for AUTH_OWNER_EMAILS accounts. Never rendered for normal users
 * on the main/public build (is_owner is false when the env list is empty).
 */
export function DeveloperButton({ className }: { className?: string }) {
  const t = useT();
  const user = useAuthStore((s) => s.user);
  const [open, setOpen] = React.useState(false);
  const [backendOk, setBackendOk] = React.useState<boolean | null>(null);
  const [devtoolsOpen, setDevtoolsOpen] = React.useState(false);

  if (!user?.is_owner) return null;

  async function refresh() {
    if (isDesktopApp()) {
      const st = await getDesktopBackendStatus();
      setBackendOk(st?.reachable ?? null);
    } else {
      try {
        const r = await fetch(`${API_BASE_URL}/health`, { credentials: "include" });
        setBackendOk(r.ok);
      } catch {
        setBackendOk(false);
      }
    }
  }

  React.useEffect(() => {
    if (open) void refresh();
  }, [open]);

  return (
    <div className={cn("relative", className)}>
      <Button
        type="button"
        variant="outline"
        size="sm"
        className="border-amber-500/40 text-amber-700 dark:text-amber-300"
        aria-label={t("dev.button")}
        onClick={() => setOpen((v) => !v)}
      >
        <Bug className="size-4" aria-hidden="true" />
        <span className="hidden sm:inline">{t("dev.button")}</span>
      </Button>
      {open && (
        <div className="absolute right-0 z-50 mt-2 w-64 rounded-xl border border-border bg-popover p-3 text-popover-foreground shadow-xl">
          <p className="mb-2 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
            {t("dev.panel")}
          </p>
          <p className="mb-2 text-xs text-muted-foreground">
            {t("dev.backend")}:{" "}
            <span className="font-medium text-foreground">
              {backendOk == null ? "…" : backendOk ? t("dev.backendOk") : t("dev.backendFail")}
            </span>
          </p>
          <p className="mb-3 truncate text-[11px] text-muted-foreground">{API_BASE_URL}</p>
          {isDesktopApp() && (
            <Button
              type="button"
              size="sm"
              className="mb-2 w-full"
              onClick={async () => {
                const next = await toggleDesktopDevTools();
                setDevtoolsOpen(next);
              }}
            >
              <Terminal className="size-4" aria-hidden="true" />
              {devtoolsOpen ? t("dev.closeTools") : t("dev.openTools")}
            </Button>
          )}
          <Button type="button" variant="ghost" size="sm" className="w-full" onClick={() => void refresh()}>
            {t("dev.refresh")}
          </Button>
        </div>
      )}
    </div>
  );
}
