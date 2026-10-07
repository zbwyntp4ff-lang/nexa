import { Lock, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { MODES, type AppMode } from "@/lib/types";
import { useT } from "@/lib/i18n";
import { useUiStore } from "@/store/ui-store";
export function ComingSoonBanner({ mode, reason = "soon" }: { mode: AppMode; reason?: "soon" | "plugin" }) {
  const t = useT();
  const openSettings = useUiStore((s) => s.openSettings);
  const definition = MODES.find((m) => m.id === mode);
  const isPluginOff = reason === "plugin";
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 px-6 text-center">
      <div className="flex size-12 items-center justify-center rounded-2xl bg-muted">
        {isPluginOff ? (
          <Lock className="size-6 text-muted-foreground" aria-hidden="true" />
        ) : (
          <Sparkles className="size-6 text-muted-foreground" aria-hidden="true" />
        )}
      </div>
      <div className="space-y-1.5">
        <h2 className="text-lg font-semibold">
          {definition?.label ?? mode} — {isPluginOff ? t("plugins.modeDisabled") : t("comingSoon.title")}
        </h2>
        <p className="max-w-sm text-sm text-muted-foreground">
          {definition ? t(`${"mode." + mode}.desc`) : ""}. {isPluginOff ? t("plugins.modeDisabledToast") : t("comingSoon.notConnected")}
        </p>
      </div>
      {isPluginOff && (
        <Button type="button" size="sm" onClick={() => openSettings("plugins")}>
          {t("settings.plugins")}
        </Button>
      )}
    </div>
  );
}
