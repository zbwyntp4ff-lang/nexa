"use client";
import * as React from "react";
import { Moon, Sun, MonitorSmartphone } from "lucide-react";
import { useTheme } from "next-themes";
import { cn } from "@/lib/utils";
import { useT } from "@/lib/i18n";
export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const t = useT();
  const [mounted, setMounted] = React.useState(false);
  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setMounted(true);
  }, []);
  const OPTIONS = [
    { value: "light", label: t("appearance.light"), icon: Sun },
    { value: "dark", label: t("appearance.dark"), icon: Moon },
    { value: "system", label: t("appearance.system"), icon: MonitorSmartphone },
  ] as const;
  return (
    <div
      role="radiogroup"
      aria-label="Color theme"
      className="inline-flex items-center gap-1 rounded-lg border border-border bg-muted/50 p-1"
    >
      {OPTIONS.map(({ value, label, icon: Icon }) => {
        const isActive = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            role="radio"
            aria-checked={isActive}
            onClick={() => setTheme(value)}
            className={cn(
              "flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              isActive
                ? "bg-background text-foreground shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            <Icon className="size-4" aria-hidden="true" />
            {label}
          </button>
        );
      })}
    </div>
  );
}
