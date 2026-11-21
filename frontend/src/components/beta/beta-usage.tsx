"use client";

import * as React from "react";
import { getBetaUsage } from "@/lib/api";

type Usage = {
  daily_remaining: number;
  daily_limit: number;
  hourly_remaining: number;
  hourly_limit: number;
};

export function BetaUsage() {
  const [usage, setUsage] = React.useState<Usage | null>(null);
  const refresh = React.useCallback(async () => {
    try { setUsage(await getBetaUsage()); } catch { /* chat remains available */ }
  }, []);
  React.useEffect(() => {
    void refresh();
    window.addEventListener("nexa:beta-usage-refresh", refresh);
    return () => window.removeEventListener("nexa:beta-usage-refresh", refresh);
  }, [refresh]);
  return (
    <div className="flex min-h-9 items-center justify-between gap-3 border-b border-border/60 px-4 py-2 text-xs text-muted-foreground sm:px-6">
      <span className="font-medium tracking-[0.12em]">HEXA BETA</span>
      <span className="text-right">
        Без регистрации
        {usage ? ` · Сегодня ${usage.daily_remaining}/${usage.daily_limit} · За час ${usage.hourly_remaining}/${usage.hourly_limit}` : " · Бесплатный тестовый доступ"}
      </span>
    </div>
  );
}
