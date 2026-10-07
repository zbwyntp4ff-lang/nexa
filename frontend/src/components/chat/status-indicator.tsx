"use client";
import { cn } from "@/lib/utils";
import { useUiStore } from "@/store/ui-store";
import { useT } from "@/lib/i18n";
import type { AppStatus } from "@/lib/types";
export function StatusIndicator({ className }: { className?: string }) {
  const t = useT();
  const status = useUiStore((s) => s.status);
  const activeTool = useUiStore((s) => s.activeTool);
  const STATUS_CONFIG: Record<AppStatus, { label: string; dot: string; pulse: boolean }> = {
    online: { label: t("status.online"), dot: "bg-success", pulse: false },
    offline: { label: t("status.offline"), dot: "bg-muted-foreground", pulse: false },
    thinking: { label: t("status.thinking"), dot: "bg-primary", pulse: true },
    using_tool: { label: t("status.usingTool"), dot: "bg-chart-3", pulse: true },
    researching: { label: t("status.researching"), dot: "bg-chart-3", pulse: true },
    generating: { label: t("status.generating"), dot: "bg-chart-4", pulse: true },
    error: { label: t("status.error"), dot: "bg-destructive", pulse: false },
  };
  const config = STATUS_CONFIG[status];
  const label = status === "using_tool" && activeTool ? `${t("status.usingTool")} — ${activeTool}` : config.label;
  return (
    <div
      className={cn("flex items-center gap-1.5 text-xs font-medium text-muted-foreground", className)}
      role="status"
      aria-live="polite"
    >
      <span className="relative flex size-2">
        {config.pulse && (
          <span
            className={cn("absolute inline-flex h-full w-full animate-ping rounded-full opacity-60", config.dot)}
            aria-hidden="true"
          />
        )}
        <span className={cn("relative inline-flex size-2 rounded-full", config.dot)} aria-hidden="true" />
      </span>
      <span>{label}</span>
    </div>
  );
}
