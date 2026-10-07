"use client";
import * as React from "react";
import { Check, ChevronDown, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { cn } from "@/lib/utils";
import { ApiError, getGatewayModels, updateModelSelection } from "@/lib/api";
import { useT } from "@/lib/i18n";
import type { GatewayModelsResponse } from "@/lib/types";

function providerLabel(provider: string): string {
  if (provider === "openai") return "OpenAI";
  if (provider === "anthropic") return "Anthropic";
  if (provider === "ollama") return "Ollama";
  return provider;
}

/**
 * Compact model switcher shown right next to the composer's send button.
 * Mirrors Settings → Models, but lets the user flip the active model
 * without leaving the chat. The selection it writes is persisted on the
 * backend (see ``app/gateway/gateway.py``), so it survives app restarts.
 */
export function ModelQuickSwitch() {
  const t = useT();
  const [data, setData] = React.useState<GatewayModelsResponse | null>(null);
  const [loading, setLoading] = React.useState(true);
  const [switching, setSwitching] = React.useState(false);

  const load = React.useCallback(async (signal?: AbortSignal) => {
    try {
      const payload = await getGatewayModels(signal);
      setData(payload);
    } catch (err) {
      if ((err as Error)?.name === "AbortError") return;
    } finally {
      setLoading(false);
    }
  }, []);

  React.useEffect(() => {
    const controller = new AbortController();
    void load(controller.signal);
    return () => controller.abort();
  }, [load]);

  async function choose(next: { provider: string; model: string }) {
    if (!data || switching) return;
    if (data.selection_mode === (next.model === "auto" ? "auto" : "manual") && data.model === next.model) return;
    setSwitching(true);
    try {
      const updated = await updateModelSelection({ ...next, allow_fallback: data.allow_fallback });
      setData(updated);
      toast(t("models.saved"));
    } catch (err) {
      toast(err instanceof ApiError ? err.message : t("models.switchFailed"));
    } finally {
      setSwitching(false);
    }
  }

  if (loading && !data) {
    return (
      <Button type="button" variant="ghost" size="sm" disabled aria-label={t("models.switchModel")}>
        <Loader2 className="size-3.5 animate-spin" aria-hidden="true" />
      </Button>
    );
  }
  if (!data) return null;

  const currentValue = data.selection_mode === "auto" ? "auto" : (data.model ?? "auto");
  const currentLabel =
    data.selection_mode === "auto"
      ? `${t("models.auto")} · ${data.active_display_name ?? data.active_model}`
      : (data.active_display_name ?? data.active_model);

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button
            type="button"
            variant="ghost"
            size="sm"
            aria-label={t("models.switchModel")}
            title={t("models.switchModel")}
            className="max-w-40 gap-1 px-2 text-xs text-muted-foreground hover:text-foreground sm:max-w-56"
          >
            {switching ? (
              <Loader2 className="size-3.5 shrink-0 animate-spin" aria-hidden="true" />
            ) : (
              <Sparkles className="size-3.5 shrink-0" aria-hidden="true" />
            )}
            <span className="truncate">{currentLabel}</span>
            <ChevronDown className="size-3 shrink-0" aria-hidden="true" />
          </Button>
        }
      />
      <DropdownMenuContent align="start" side="top" className="max-h-72 w-64 overflow-y-auto">
        <DropdownMenuLabel>{t("models.switchModel")}</DropdownMenuLabel>
        <DropdownMenuItem onClick={() => void choose({ provider: "auto", model: "auto" })}>
          {currentValue === "auto" ? (
            <Check className="size-3.5 shrink-0" aria-hidden="true" />
          ) : (
            <span className="size-3.5 shrink-0" />
          )}
          <span className="truncate">{t("models.auto")}</span>
        </DropdownMenuItem>
        <DropdownMenuSeparator />
        {data.models.map((item) => (
          <DropdownMenuItem
            key={`${item.provider}:${item.model_id}`}
            disabled={item.availability !== "available"}
            onClick={() => void choose({ provider: item.provider, model: item.model_id })}
          >
            {currentValue === item.model_id ? (
              <Check className="size-3.5 shrink-0" aria-hidden="true" />
            ) : (
              <span className="size-3.5 shrink-0" />
            )}
            <span className="truncate">{item.display_name}</span>
            <span className={cn("ml-auto shrink-0 text-[10px] text-muted-foreground")}>
              {providerLabel(item.provider)}
            </span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
